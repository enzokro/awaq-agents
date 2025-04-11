# File: prompt_manager_guide.py
# Purpose: Literate programming guide for a database-backed Prompt Management System
# Style: Inspired by Jeremy Howard - practical, minimal, database-centric using fastlite concepts.

# %% Introduction
# =================
# Goal: Manage prompts (system, prefill, regular, tool schemas) for LLM agents in a structured,
# versioned way, stored in a simple SQLite database. This allows AgentProfiles to reference
# specific prompt versions, enabling systematic evaluation and iteration.
#
# Philosophy:
# 1. Database as the Source of Truth: Store prompts centrally.
# 2. Versioning is Key: Explicitly track changes to prompts.
# 3. Simple Schema: Use a minimal SQLite table.
# 4. Pythonic Interface: Leverage fastlite's dataclass integration for easy interaction.
# 5. Integration with ADEF: AgentProfiles will fetch prompts from this system.
#
# We'll use pseudo-code focusing on the design and interaction patterns.

# %% Imports (Conceptual)
# =======================
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path
import json
import enum

# Assume fastlite and claudette are available
# from fastlite import database, UNSET # Need actual imports
# from apswutils.db import NotFoundError # Need actual import

# %% Constants and Enums
# ======================
DB_FILENAME = "prompts.db" # Default database file name

# Define prompt types clearly using an Enum (better than raw strings)
class PromptType(enum.Enum):
    SYSTEM = "system"
    PREFILL = "prefill"
    REGULAR = "regular" # For few-shot examples or specific turn instructions?
    TOOL_SCHEMA = "tool_schema" # Storing the JSON schema string for a tool

# %% Database Schema & Dataclass (`PromptRecord`)
# ==============================================
# We need one main table to store all prompts.
# Fastlite uses dataclasses to define table schemas.

# --- Dataclass Definition (Maps to 'prompts' table) ---
# @dataclass # Placeholder for decorator
class PromptRecord:
    """
    Dataclass representing a single prompt record in the database.
    Maps directly to the 'prompts' table schema via fastlite.
    """
    prompt_id: Optional[int] = None # Primary Key, auto-incremented by SQLite. Optional in Python.
    name: str = ""                  # Logical name for the prompt (e.g., 'concierge_greeting', 'calculator_tool_schema'). REQUIRED.
    version: str = ""               # Version identifier (e.g., 'v1.0', 'v2.1-beta', '20240726'). REQUIRED. Combined with name for uniqueness.
    prompt_type: str = ""           # Type of prompt, using PromptType enum values (e.g., 'system', 'tool_schema'). REQUIRED.
    content: str = ""               # The actual text content or JSON schema string. REQUIRED.
    metadata: Optional[str] = None  # Store additional info (description, author, etc.) as a JSON string. Optional.
    created_at: Optional[str] = None # Timestamp (ISO format string), auto-set by DB default. Optional in Python.

    # We might add methods here later if needed, but keep it mostly data for now.
    def get_metadata(self) -> dict:
        """Helper to parse the metadata JSON string."""
        # try:
        #     return json.loads(self.metadata) if self.metadata else {}
        # except json.JSONDecodeError:
        #     return {"error": "Invalid JSON metadata"}
        pass # Placeholder

# %% Prompt Manager Class (`PromptManager`)
# ========================================
# This class encapsulates interaction with the prompts database.
# It handles connecting, creating the table, adding, and retrieving prompts.

class PromptManager:
    """
    Manages storing and retrieving versioned prompts from an SQLite database.
    Uses fastlite-style interaction via the PromptRecord dataclass.
    """
    def __init__(self, db_path: str = DB_FILENAME):
        """
        Initializes the manager, connects to the database, and ensures the table exists.
        """
        self.db_path = Path(db_path)
        print(f"Initializing PromptManager with database: {self.db_path}")
        # self.db = database(self.db_path) # Connect using fastlite's helper
        self.db = None # Placeholder for Database object
        self._create_table_if_not_exists()

    def _create_table_if_not_exists(self):
        """
        Creates the 'prompts' table based on the PromptRecord dataclass if it doesn't exist.
        Uses fastlite's `db.create()` which maps the dataclass to SQL.
        Also ensures a unique index on (name, version).
        """
        print("Ensuring 'prompts' table exists...")
        try:
            # prompts_table = self.db.create(
            #     PromptRecord, # The dataclass defines the schema
            #     pk='prompt_id', # Specify the primary key
            #     # Define the unique constraint on name and version
            #     # Note: sqlite-utils/fastlite syntax for complex constraints might require raw SQL execute
            #     # or specific handling in db.create if supported directly.
            #     # Let's assume we might need to add the index separately.
            #     if_not_exists=True # Don't error if table is already there
            # )
            # # Ensure the unique index exists (idempotent)
            # self.db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_prompt_name_version ON prompts(name, version);")
            # self.prompts_table = prompts_table # Store reference if needed
            self.prompts_table = self.db['prompts'] # Or just get it by name
            # Map the class for automatic conversion in queries
            self.prompts_table.cls = PromptRecord
            print("'prompts' table ensured.")
        except Exception as e:
            print(f"Error creating/ensuring 'prompts' table: {e}")
            # Handle error appropriately
            raise

    def add_prompt(self,
                   name: str,
                   version: str,
                   prompt_type: PromptType,
                   content: str,
                   metadata: Optional[Dict] = None,
                   overwrite: bool = False) -> Optional[PromptRecord]:
        """
        Adds a new prompt version to the database.

        Args:
            name: Logical name of the prompt.
            version: Version identifier string.
            prompt_type: Type of the prompt (use PromptType enum).
            content: The actual prompt text or JSON schema string.
            metadata: Optional dictionary for additional info (will be stored as JSON string).
            overwrite: If True, will replace an existing prompt with the same name and version.

        Returns:
            The saved PromptRecord instance or None if an error occurred (e.g., unique constraint violation without overwrite=True).
        """
        print(f"Adding prompt: name='{name}', version='{version}', type='{prompt_type.value}'")
        if not all([name, version, prompt_type, content]):
             print("Error: Name, version, prompt_type, and content are required.")
             return None

        metadata_str = json.dumps(metadata) if metadata else None
        record_data = PromptRecord(
            name=name,
            version=version,
            prompt_type=prompt_type.value, # Store the enum value string
            content=content,
            metadata=metadata_str
            # prompt_id and created_at are handled by DB
        )

        try:
            if overwrite:
                # Use fastlite's upsert. It needs the primary key for update condition.
                # Here, we want to update based on the UNIQUE key (name, version).
                # We might need a custom query or check-then-update logic if upsert by unique index isn't direct.
                # Simpler approach for now: try delete then insert, or rely on unique index failure.
                # Let's assume upsert based on unique key needs custom handling or we use insert with conflict resolution.

                # Option 1: Delete if exists, then insert (less atomic)
                # existing = self.get_prompt(name, version, raise_error=False)
                # if existing: self.prompts_table.delete(...) # Delete by prompt_id

                # Option 2: Use INSERT ... ON CONFLICT (requires raw SQL or specific fastlite support)
                # self.db.execute(
                #     "INSERT INTO prompts (name, version, prompt_type, content, metadata) VALUES (?, ?, ?, ?, ?) "
                #     "ON CONFLICT(name, version) DO UPDATE SET prompt_type=excluded.prompt_type, content=excluded.content, metadata=excluded.metadata;",
                #     (name, version, prompt_type.value, content, metadata_str)
                # )
                # Need to retrieve the inserted/updated record afterwards if we want to return it.

                # Option 3: Rely on fastlite's upsert if it supports unique keys other than PK (check docs)
                # Assume for pseudo-code it might require PK, so we get PK first if exists.
                # existing_id = self.db.q("SELECT prompt_id FROM prompts WHERE name = ? AND version = ?", (name, version))
                # if existing_id: record_data.prompt_id = existing_id[0]['prompt_id']
                # saved_record = self.prompts_table.upsert(record_data, pk='prompt_id') # Assuming upsert works

                # Let's simplify: use insert and catch unique error unless overwrite is True
                print("Overwrite=True: Attempting insert with replace (conceptual).")
                # In real sqlite-utils, `replace=True` on insert handles this based on PK.
                # For unique index, we might need the ON CONFLICT strategy shown above.
                # For this guide, assume a mechanism exists or use try/except.
                # saved_record = self.prompts_table.insert(record_data, replace=True) # Assumes replace works on unique key, might not!
                pass # Placeholder for upsert/replace logic

            else:
                # Standard insert, will fail if name/version combo exists due to unique index.
                # saved_record = self.prompts_table.insert(record_data)
                pass # Placeholder for insert

            # After insert/upsert, retrieve the record to return it with ID and timestamp
            # Use the name and version to get the potentially just-inserted/updated record.
            # return self.get_prompt(name, version)
            print(f"Successfully added/updated prompt '{name}' version '{version}'.")
            return record_data # Return input data as placeholder

        # except IntegrityError as e: # Catch specific unique constraint error
        #     print(f"Error adding prompt '{name}' version '{version}': Already exists (and overwrite=False). {e}")
        #     return None
        except Exception as e:
            print(f"Error adding prompt '{name}' version '{version}': {e}")
            # print(traceback.format_exc()) # For debugging
            return None

    def get_prompt(self, name: str, version: str, raise_error: bool = True) -> Optional[PromptRecord]:
        """
        Retrieves a specific prompt version by name and version.
        Uses fastlite's table calling convention for querying.
        """
        print(f"Getting prompt: name='{name}', version='{version}'")
        try:
            # Use fastlite's __call__ on the table object with `where` clause
            # The table object `self.prompts_table` should already have `cls=PromptRecord` set.
            # record = self.prompts_table(
            #     where="name = :name AND version = :version",
            #     where_args={"name": name, "version": version},
            #     fetchone=True, # We only expect one
            #     as_cls=True # Ensure it returns PromptRecord instance
            # )
            record = None # Placeholder for query result
            if record:
                return record
            else:
                # fetchone returns None if not found
                if raise_error:
                    # raise NotFoundError(f"Prompt '{name}' version '{version}' not found.")
                    pass # Placeholder
                else:
                    return None
        except Exception as e: # Catch potential query errors
            print(f"Error getting prompt '{name}' version '{version}': {e}")
            if raise_error:
                raise # Re-raise the original error
            else:
                return None

    def get_latest_prompt(self, name: str, raise_error: bool = True) -> Optional[PromptRecord]:
        """
        Retrieves the 'latest' version of a prompt by name.
        'Latest' is determined by sorting versions descending. Assumes comparable version strings (e.g., 'v1.0', 'v1.1', 'v2.0').
        """
        print(f"Getting latest prompt for name='{name}'")
        try:
            # Query for the name, order by version descending, limit to 1.
            # record = self.prompts_table(
            #     where="name = :name",
            #     where_args={"name": name},
            #     order_by="version DESC", # Assumes string sort works for version scheme
            #     limit=1,
            #     fetchone=True,
            #     as_cls=True
            # )
            record = None # Placeholder
            if record:
                return record
            else:
                if raise_error:
                    # raise NotFoundError(f"No prompts found for name '{name}'.")
                    pass # Placeholder
                else:
                    return None
        except Exception as e:
            print(f"Error getting latest prompt for '{name}': {e}")
            if raise_error: raise
            else: return None

    def list_prompts(self, name_filter: Optional[str] = None) -> List[Tuple[str, str]]:
        """Lists available prompt names and their versions."""
        print(f"Listing prompts (Filter: {name_filter})...")
        query = "SELECT DISTINCT name, version FROM prompts"
        params = {}
        if name_filter:
            query += " WHERE name LIKE :filter"
            params["filter"] = f"%{name_filter}%"
        query += " ORDER BY name, version" # Order consistently

        # results = self.db.q(query, params) # Use fastlite's query shortcut
        # return [(r['name'], r['version']) for r in results]
        return [] # Placeholder

    def get_prompts_by_type(self, prompt_type: PromptType, name_filter: Optional[str] = None) -> List[PromptRecord]:
        """Retrieves all prompts matching a specific type."""
        print(f"Getting prompts of type='{prompt_type.value}' (Filter: {name_filter})")
        where_clauses = ["prompt_type = :ptype"]
        params = {"ptype": prompt_type.value}
        if name_filter:
            where_clauses.append("name LIKE :filter")
            params["filter"] = f"%{name_filter}%"

        # records = self.prompts_table(
        #     where=" AND ".join(where_clauses),
        #     where_args=params,
        #     order_by="name, version",
        #     as_cls=True
        # )
        # return records
        return [] # Placeholder

# %% Integration with AgentProfile & ADEF Framework
# ================================================
# How does AgentProfile use PromptManager?
# Option 1: Profile stores references (name, version), fetches content at Chat creation.
# Option 2: Profile stores actual content, loaded from PromptManager when profile is defined.
#
# Option 1 is more flexible for evaluation (can swap versions easily) but requires
# passing the PromptManager instance around or having a global one.
# Let's refine AgentProfile for Option 1.

# --- Modified profiles/base_profile.py (Conceptual Snippets) ---
# @dataclass # Placeholder
class AgentProfile_WithRefs:
    profile_id: str
    model: str
    # Store REFERENCES (name, version or just name for 'latest') instead of raw text
    system_prompt_ref: Tuple[str, Optional[str]] = None # (name, version or None for latest)
    # prefill_prompt_ref: Tuple[str, Optional[str]] = None
    # tool_schema_refs: Dict[str, Tuple[str, Optional[str]]] = field(default_factory=dict) # tool_name -> (schema_name, version)
    tools: List[Callable] = field(default_factory=list) # Actual tool functions still live here
    # ... other fields ...

    def _get_prompt_content(self, manager: PromptManager, ref: Tuple[str, Optional[str]]) -> str:
        """Helper to fetch prompt content using the manager."""
        if not ref: return ""
        name, version = ref
        try:
            if version:
                record = manager.get_prompt(name, version)
            else:
                record = manager.get_latest_prompt(name)
            return record.content if record else ""
        except Exception as e: # Catch NotFoundError etc.
            print(f"Warning: Failed to retrieve prompt ref {ref}: {e}")
            return "" # Return empty string or raise? Empty seems safer for defaults.

    def create_chat(self, prompt_manager: PromptManager, **override_chat_params) -> 'Chat':
        """ Instantiates Chat, fetching prompts from the PromptManager. """
        # Fetch prompt content using self._get_prompt_content
        system_prompt_content = self._get_prompt_content(prompt_manager, self.system_prompt_ref)
        # prefill_content = self._get_prompt_content(prompt_manager, self.prefill_prompt_ref)
        # tool_schemas = { # Fetch tool schemas if storing them
        #    tool_name: self._get_prompt_content(prompt_manager, ref)
        #    for tool_name, ref in self.tool_schema_refs.items()
        # }

        # Process tool *functions* (as before)
        processed_tools = self.tools # Placeholder for actual processing

        # Combine params
        chat_init_params = self.default_params.copy()
        chat_init_params.update(override_chat_params)
        temp = chat_init_params.pop('temp', 0)
        # ...

        # Instantiate Chat with the *fetched content*
        # return Chat(
        #     model=self.model,
        #     sp=system_prompt_content, # Use fetched content
        #     tools=processed_tools, # Tool functions
        #     # Potentially pass tool_schemas if claudette supports/needs them separately
        #     temp=temp,
        #     cache=self.cache_enabled,
        #     # Pass prefill_content if Chat accepts it directly
        # )
        pass # Placeholder

# --- Impact on EvalLoop / AgentRunner ---
# - They need access to a PromptManager instance. This could be passed during init
#   or assumed to be globally available (less ideal).
# - When creating the Chat instance inside EvalLoop/AgentRunner, they pass the
#   PromptManager to `profile.create_chat(prompt_manager=...)`.
# - Logging: The `profile_id` already links the run to the agent definition. The
#   profile definition implicitly contains the prompt *references* (name/version) used.
#   We could explicitly log the resolved `prompt_id` from the DB for absolute clarity.

# %% Mermaid Diagram: Data Flow with PromptManager
# ================================================
"""
graph LR
    subgraph Definition & Storage
        Define(Developer Defines Prompt <br> e.g., system_v1) --> PM_Add(PromptManager.add_prompt);
        PM_Add -- Writes --> DB[(prompts.db <br> SQLite)];
        DB -- Reads --> PM_Get(PromptManager.get_prompt / get_latest);

        ProfDef(Developer Defines AgentProfile <br> Stores Prompt Refs <br> e.g., system_prompt_ref=('sys', 'v1'));
    end

    subgraph Execution Framework (ADEF)
        PM(PromptManager Instance) -- Passed To --> RunnerLoop{AgentRunner / EvalLoop};
        ProfDef -- Loaded By --> RunnerLoop;
        Dataset(Dataset / User Input) --> RunnerLoop;

        RunnerLoop -- Calls --> ProfCreateChat(AgentProfile.create_chat);
        ProfCreateChat -- Uses --> PM_Get;
        PM_Get -- Returns Content --> ProfCreateChat;
        ProfCreateChat -- Creates --> Chat(claudette.Chat Instance <br> with resolved prompts);

        RunnerLoop -- Uses --> Chat;
        Chat -- Interaction --> LLM(LLM API);
        LLM -- Response --> Chat;
        Chat -- Result --> RunnerLoop;

        RunnerLoop -- Logs --> LogFmt(Logging Framework);
        LogFmt -- Writes --> LogFile(results/*.jsonl);
    end

    subgraph Analysis
        LogFile -- Analyzed By --> Analysis(Analysis & Comparison);
        Analysis -- Feedback --> Define;
        Analysis -- Feedback --> ProfDef;
    end

    style DB fill:#dbf,stroke:#333,stroke-width:2px
    style PM fill:#lightblue,stroke:#333,stroke-width:1px
    style ProfDef fill:#lightcyan,stroke:#333,stroke-width:1px
    style RunnerLoop fill:#lightgreen,stroke:#333,stroke-width:2px
    style LogFile fill:#orange,stroke:#333,stroke-width:2px
    style Analysis fill:#thistle,stroke:#333,stroke-width:1px
"""

# %% Conclusion & Next Steps
# ===========================
# This design provides a robust way to manage prompts using a simple database.
#
# Key Implementation Points:
# 1. Implement `PromptManager` using `fastlite.database` and `db.create`/`table()` calls.
# 2. Handle the unique constraint (name, version) carefully in `add_prompt` (e.g., using raw SQL `ON CONFLICT` or try/except).
# 3. Implement version comparison logic if `get_latest_prompt` needs more than string sorting.
# 4. Modify `AgentProfile` to store references (Tuple[str, Optional[str]]) instead of raw strings for prompts.
# 5. Update `AgentProfile.create_chat` to accept a `PromptManager` and fetch content using it.
# 6. Update `EvalLoop` and `AgentRunner` to instantiate/pass the `PromptManager` to `create_chat`.
# 7. Consider adding the resolved `prompt_id`(s) from the DB to the log entry in `format_log_entry` for explicit traceability.
#
# This approach keeps prompt definitions separate and versioned, making it easy to run evaluations
# across different prompt versions simply by changing the references in the `AgentProfile` or
# creating new profiles pointing to different versions.