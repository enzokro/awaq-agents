# File: cck_agents_framework_guide.py
# Purpose: Literate programming guide for the Agent Development & Evaluation Framework (`cck-agents`)
# Style: Inspired by Jeremy Howard - practical, minimal, iterative, focused on clarity and usability.

# %% Introduction
# =================
# This file outlines the core structure and design philosophy for `cck-agents`.
# It's not meant to be runnable code directly, but rather a guide for implementation,
# potentially used by a human developer or an LLM coding assistant.
# We prioritize simplicity, clear data flow, and robust logging/evaluation hooks.
# The goal is a framework that *enables* rapid experimentation and reliable measurement,
# leveraging the `claudette` library without adding unnecessary complexity.
# Think: start simple, log everything useful, measure what matters, iterate quickly.

# %% Imports (Conceptual)
# =======================
# We'll need basic types, dataclasses, path handling, time, json, etc.
# Crucially, we depend on `claudette` for the core LLM interaction.
# Assume these imports are available where needed.
from typing import List, Callable, Dict, Any, Optional, Iterable
from dataclasses import dataclass, field
from pathlib import Path
import datetime
import time
import json
import traceback
import uuid

# Assume claudette is installed and accessible
# from claudette.core import Chat, tool, contents, Usage, usage as claudette_usage
# Placeholder for actual imports - the real code needs these.

# %% Component 1: Agent Profile Definition (`profiles/`)
# =======================================================
# The `AgentProfile` is the heart of defining *what* an agent is.
# It's just configuration data - model, prompt, tools, default params.
# Keep it simple (dataclass is great), versionable (`profile_id`), and easy to load.
# Store these as separate Python files in a `profiles/` directory for discoverability.

# --- File: profiles/base_profile.py ---
@dataclass
class AgentProfile:
    """
    Defines the static configuration and identity of a Claudette-based Agent.

    Think of this as the recipe for an agent. It's just data, no runtime state.
    Crucially includes `profile_id` for versioning and tracking experiments.
    Tools are just Python functions; we'll handle wrapping them if needed.
    """
    profile_id: str          # IMPORTANT: Unique identifier (e.g., 'concierge_v2.1-haiku'). Use for versioning!
    model: str               # The specific `claudette` model string.
    system_prompt: str = ""  # The core instructions defining the agent's persona and goals. Keep it clear.
    tools: List[Callable] = field(default_factory=list) # List of Python functions to be used as tools.
    default_params: Dict[str, Any] = field(default_factory=dict) # Default kwargs for claudette calls (e.g., temp, maxtok). Promotes consistency.
    cache_enabled: bool = False # Whether to enable claudette's built-in caching for this agent. Useful for dev.
    metadata: Dict[str, Any] = field(default_factory=dict) # Optional: Store extra info like description, author, creation date.

    def create_chat(self, **override_chat_params) -> 'Chat': # Type hint requires Chat import
        """
        Instantiates a ready-to-use `claudette.Chat` object based on this profile.

        This is the factory method. It takes the profile data and spins up
        a live `Chat` instance. Handles applying the `@tool` decorator if needed.
        Allows overriding things like temperature at instantiation time if desired,
        though usually overrides happen at call time.
        """
        # Pseudo-code for tool processing:
        processed_tools = []
        for t in self.tools:
            # Check if 't' looks like it needs the @tool decorator.
            # A simple check might be if it lacks `__wrapped__` attribute that `functools.wraps` (used by @tool) adds.
            is_already_wrapped = hasattr(t, '__wrapped__') # Basic heuristic
            if not is_already_wrapped:
                try:
                    # from claudette.core import tool # Need actual import
                    # processed_tools.append(tool(t))
                    pass # Placeholder: Apply @tool decorator
                except Exception as e:
                    print(f"Warning: Failed to wrap tool {getattr(t,'__name__','?')}: {e}")
                    # processed_tools.append(t) # Keep original if wrapping fails
                    pass # Placeholder: Keep original tool
            else:
                # processed_tools.append(t) # Assume already wrapped
                pass # Placeholder: Add already wrapped tool
        processed_tools = self.tools # Simplification for pseudo-code

        # Combine default profile params with any overrides
        chat_init_params = self.default_params.copy()
        chat_init_params.update(override_chat_params)

        # Extract specific params Chat needs at init (like temp)
        temp = chat_init_params.pop('temp', 0) # Default to 0 if not set
        # ... (handle other Chat init params like cont_pr) ...

        # from claudette.core import Chat # Need actual import
        # return Chat(
        #     model=self.model,
        #     sp=self.system_prompt,
        #     tools=processed_tools,
        #     temp=temp,
        #     cache=self.cache_enabled
        #     # Other relevant Chat init args...
        # )
        pass # Placeholder: Return actual Chat instance

    def get_call_params(self, **call_overrides) -> Dict[str, Any]:
        """
        Helper to get the final dict of parameters for a specific LLM call.
        Merges profile defaults with run-time overrides. Useful for logging.
        """
        params = self.default_params.copy()
        params.update(call_overrides)
        return params

    # __repr__ is useful for quick inspection
    def __repr__(self):
        tool_names = [getattr(t, '__name__', str(t)) for t in self.tools]
        return f"AgentProfile(profile_id='{self.profile_id}', model='{self.model}', tools={len(tool_names)})"

# --- File: profiles/common_tools.py ---
# Define reusable tools here. Keep them simple, focused Python functions.
# The `@tool` decorator (from claudette) will handle schema generation.

# from claudette.core import tool # Need actual import

# @tool # Placeholder for decorator
def get_current_time() -> str:
    """Returns the current date and time. Simple, common utility."""
    # print("Tool: Getting current time") # Good practice for debugging tool calls
    # import datetime
    # return datetime.datetime.now().isoformat()
    pass # Placeholder

# @tool # Placeholder for decorator
def end_call(reason: str = "Completed request") -> str:
    """
    Signals the end of the conversation. Crucial for session control.
    The framework (AgentRunner/EvalLoop) should check if this tool was called.
    """
    # print(f"Tool: Ending call. Reason: {reason}")
    # return "Okay, ending the call. Goodbye!"
    pass # Placeholder

common_tool_list = [get_current_time, end_call]

# --- File: profiles/calculator_agent_v1.py ---
# Example of a specific agent profile definition. Imports base and tools.

# from .base_profile import AgentProfile
# from .common_tools import common_tool_list # Optional: Include common tools
# from claudette.core import tool # Need actual import

# Define tools specific to this agent
# @tool # Placeholder
def add(a: float, b: float) -> float:
    """Adds two numbers."""
    # print(f"Tool: Adding {a} + {b}")
    # return a + b
    pass # Placeholder

# @tool # Placeholder
def multiply(a: float, b: float) -> float:
    """Multiplies two numbers."""
    # print(f"Tool: Multiplying {a} * {b}")
    # return a * b
    pass # Placeholder

calculator_tools = [add, multiply]

# Use the base AgentProfile dataclass
# @dataclass # Placeholder
class CalculatorAgentProfile(AgentProfile): # Inherit behavior if needed, or just instantiate
    profile_id: str = "calculator_v1.0" # Version explicitly
    model: str = "claude-3-haiku-20240307" # Choose appropriate model
    system_prompt: str = "You are a calculator. Use tools `add` and `multiply`."
    tools: list = field(default_factory=lambda: calculator_tools) # Assign the specific tools
    default_params: Dict[str, Any] = field(default_factory=lambda: {"temp": 0.0}) # Set defaults for this agent

# Instantiate the profile so it can be imported directly
# profile = CalculatorAgentProfile() # This makes it easy: `from profiles.calculator_agent_v1 import profile`

# %% Component 2: Logging Utilities (`framework/logging.py`)
# ===========================================================
# Logging is CRITICAL. We need structured, comprehensive logs for every interaction.
# JSONL is a good choice: append-friendly, easy to parse later (e.g., with pandas).
# Define a clear schema (`format_log_entry`) and stick to it.

# --- File: framework/logging.py ---
LOG_SCHEMA_VERSION = "1.0" # Version the schema itself!

def get_log_path(log_dir: str = "results", run_name: str = None) -> Path:
    """Determines where to save the log file. Consistent naming is key."""
    # Use timestamps and run names for organization.
    # Ensure the directory exists.
    # Implementation uses pathlib, datetime.
    pass # Placeholder

def format_log_entry(
    # **kwargs representing all the fields defined in the Architecture doc (REQ-LG-003) **
    # run_name: str, profile_id: str, interaction_id: str, run_type: str, timestamp: str,
    # input_data: Dict, call_params: Dict, chat_history: List, tool_calls: List,
    # latency_ms: float, final_output_text: Optional[str], final_output_raw: Optional[Any],
    # usage_info: Optional[Dict], cost_info: Optional[float], evaluation_results: Optional[Dict],
    # error_info: Optional[str], metadata: Optional[Dict]
    **log_data
) -> Dict[str, Any]:
    """
    Creates the structured log dictionary according to the schema.
    Includes schema version. Removes keys with None values for tidiness.
    Make sure all data passed in is JSON serializable (or handle serialization here).
    """
    # log_entry = {"log_schema_version": LOG_SCHEMA_VERSION, **log_data}
    # return {k: v for k, v in log_entry.items() if v is not None}
    pass # Placeholder

def log_to_file(log_entry: Dict, file_path: Path):
    """
    Appends a formatted log entry (dict) as a JSON line to the specified file.
    Handle potential file I/O errors gracefully. Use `default=str` in `json.dumps`
    as a fallback for non-serializable objects, but ideally ensure serializability earlier.
    """
    # try:
    #     with open(file_path, "a") as f:
    #         f.write(json.dumps(log_entry, default=str) + "\n")
    # except Exception as e:
    #     print(f"ERROR logging to {file_path}: {e}")
    pass # Placeholder

# %% Component 3: Evaluation Utilities (`framework/evaluation.py`)
# ================================================================
# Defines the *interface* for evaluators and holds specific implementations.
# Keep evaluators as simple functions where possible. They take context, return metrics.

# --- File: framework/evaluation.py ---
# Define type hints for clarity
DatasetItem = Dict[str, Any] # e.g., {'id': '...', 'prompt': '...', 'ground_truth': '...'}
# from claudette.core import Chat # Need import
EvaluationResult = Dict[str, Any] # e.g., {'accuracy': 1.0, 'contains_word_X': True}
# Evaluator = Callable[[DatasetItem, Chat, Optional[Any]], EvaluationResult] # The function signature

# Example Evaluator:
def exact_match_evaluator(item: DatasetItem, chat: 'Chat', ground_truth: Optional[Any]) -> EvaluationResult:
    """Checks if the final agent text output exactly matches the ground truth."""
    # Safely get final text output from `chat.c.result`. Handle errors/missing output.
    # Compare with `ground_truth` if available.
    # Return a dict like {'exact_match': 1.0} or {'exact_match': 0.0} or {'exact_match': 'N/A'}.
    pass # Placeholder

def contains_keywords_evaluator(item: DatasetItem, chat: 'Chat', ground_truth: Optional[Any]) -> EvaluationResult:
    """Checks if the output text contains specific keywords (e.g., from ground_truth)."""
    # Safely get output text.
    # Check for keywords (maybe passed via item['keywords'] or derived from ground_truth).
    # Return a dict like {'contains_keywords': True/False}.
    pass # Placeholder

# Placeholder for potential LLM-as-judge evaluator
def llm_judge_evaluator(item: DatasetItem, chat: 'Chat', ground_truth: Optional[Any]) -> EvaluationResult:
    """Uses another LLM call to evaluate the quality/correctness based on criteria."""
    # This is more complex. Needs another LLM call (maybe a dedicated 'judge' Chat instance).
    # Formulate a prompt for the judge LLM including input, output, and criteria.
    # Parse the judge's response to extract metrics (e.g., score, pass/fail, critique).
    # Return a dict with the judge's assessment. Handle errors carefully.
    pass # Placeholder

# %% Component 4: Agent Runner (`framework/agent_runner.py`)
# ============================================================
# Handles interactive sessions. Key difference from EvalLoop: maintains a *persistent*
# Chat instance to keep conversation history across turns. Logs each turn individually.

# --- File: framework/agent_runner.py ---
class AgentRunner:
    """
    Runs interactive sessions with an agent defined by an AgentProfile.
    Maintains conversation state (`claudette.Chat` instance) across turns.
    Logs each turn comprehensively.
    """
    def __init__(self, profile: AgentProfile, log_dir: str = "results", run_name_prefix: str = "interactive"):
        """Initializes with a profile, sets up logging for the session."""
        self.profile = profile
        self.chat = profile.create_chat() # Create the persistent Chat instance for the session.
        self.session_id = str(uuid.uuid4()) # Unique ID for this interactive session.
        self.log_path = self._setup_logging(log_dir, run_name_prefix) # Use logging utilities
        print(f"AgentRunner initialized (Session: {self.session_id}), logging to {self.log_path}")

    def _setup_logging(self, log_dir, run_name_prefix):
        # Use framework.logging.get_log_path to determine file path
        # Log initial setup? (Optional)
        # return log_path
        pass # Placeholder

    async def run_turn(self, user_input: str, use_toolloop: bool = True, **call_overrides) -> str:
        """
        Processes a single turn of user input using the persistent chat instance.
        Logs the details of this specific turn.
        """
        interaction_id = f"{self.session_id}_{len(self.chat.h)//2 + 1}" # Unique ID for this turn
        start_time = time.monotonic()
        run_error = None
        tool_calls_in_turn = [] # Collect tool calls *during this turn*
        initial_usage = self.chat.use # Usage *before* this turn's API call

        # Get final parameters for the LLM call (profile defaults + overrides)
        call_params = self.profile.get_call_params(**call_overrides)

        try:
            # Decide whether to use toolloop or standard call based on `use_toolloop` flag
            if use_toolloop:
                # Define a simple tracer to capture tool calls *within this turn's loop*
                def _tracer(history_slice):
                    # Basic parsing of history_slice to identify tool name, args, result
                    # Append to tool_calls_in_turn list
                    pass # Placeholder

                # response = await self.chat.toolloop(pr=user_input, trace_func=_tracer, **call_params)
                pass # Placeholder
            else:
                # response = await self.chat(pr=user_input, **call_params)
                pass # Placeholder

            # Safely extract final text output from self.chat.c.result
            # final_output_text = contents(...)
            # final_output_raw = self.chat.c.result.model_dump() # Or relevant parts
            final_output_text = "Placeholder response" # Placeholder
            final_output_raw = {} # Placeholder

        except Exception as e:
            run_error = traceback.format_exc()
            final_output_text = f"[Error: {e}]"
            final_output_raw = None
            print(run_error) # Show error in interactive mode

        latency_ms = (time.monotonic() - start_time) * 1000

        # Calculate usage *delta* for this turn
        current_usage = self.chat.use
        # usage_delta = calculate_usage_delta(initial_usage, current_usage) # Need helper or direct calc
        usage_delta_dict = {} # Placeholder
        # cost_delta = calculate_cost(usage_delta, self.profile.model) # Need pricing info

        # Prepare log entry using framework.logging.format_log_entry
        log_entry_data = {
            "run_name": f"{run_name_prefix}_{self.profile.profile_id}", # Group interactive runs
            "profile_id": self.profile.profile_id,
            "interaction_id": interaction_id,
            "run_type": 'interactive',
            "timestamp": datetime.datetime.now().isoformat(),
            "input_data": {'user_input': user_input},
            "call_params": call_params,
            "chat_history": [msg for msg in self.chat.h], # Log full history state *after* turn
            "tool_calls": tool_calls_in_turn, # Tools used *just now*
            "latency_ms": latency_ms,
            "final_output_text": final_output_text,
            "final_output_raw": final_output_raw,
            "usage_info": usage_delta_dict, # Log the *delta* for the turn
            "cost_info": None, # Placeholder for cost delta
            "evaluation_results": None, # No auto-eval in interactive
            "error_info": run_error,
            "metadata": {'session_id': self.session_id}
        }
        # log_entry = format_log_entry(**log_entry_data) # Need actual import
        # log_to_file(log_entry, self.log_path) # Need actual import

        # Check if 'end_call' tool was triggered within tool_calls_in_turn
        # if end_call_detected: print("--- End Call Triggered ---")

        return final_output_text

    def reset_session(self):
        """Resets the chat history, starting a new logical conversation."""
        print("Resetting session...")
        self.chat = self.profile.create_chat() # Get a fresh Chat instance
        self.session_id = str(uuid.uuid4()) # Assign a new session ID
        # Update log path maybe? Or keep logging to the same file? Decide on strategy.
        print(f"New session started: {self.session_id}")


# %% Component 5: Evaluation Loop (`framework/eval_loop.py`)
# ==========================================================
# Handles batch evaluation. Key difference from AgentRunner: creates a *fresh*
# Chat instance for *each* dataset item to ensure isolation. Logs results per item.

# --- File: framework/eval_loop.py ---
class EvalLoop:
    """
    Runs batch evaluation of an AgentProfile against a dataset.
    Ensures isolation between items by using fresh Chat instances.
    Applies evaluators and logs results comprehensively per item.
    """
    def __init__(self,
                 profile: AgentProfile,
                 dataset: Iterable[DatasetItem], # Expects dicts like {'id': '...', 'prompt': '...', 'ground_truth': '...'}
                 evaluators: List[Callable], # List of evaluator functions
                 run_name: str = None,
                 log_dir: str = "results"):
        """Initializes with profile, data, evaluators. Sets up run name and logging."""
        self.profile = profile
        self.dataset = dataset
        self.evaluators = evaluators
        self.run_name = run_name or self._generate_run_name() # Use helper
        self.log_path = self._setup_logging(log_dir)
        self.results_summary = [] # Store key metrics per item for quick summary
        print(f"EvalLoop initialized (Run: {self.run_name}), logging to {self.log_path}")

    def _generate_run_name(self):
        # return f"eval_{self.profile.profile_id}_{datetime...}"
        pass # Placeholder

    def _setup_logging(self, log_dir):
        # Use framework.logging.get_log_path
        # return log_path
        pass # Placeholder

    async def run(self, use_toolloop: bool = True, **call_overrides) -> List[Dict]:
        """Executes the evaluation loop over the dataset."""
        print(f"Starting evaluation run: {self.run_name}")
        run_start_time = time.monotonic()

        for i, item in enumerate(self.dataset):
            item_id = item.get('id', f"item_{i}")
            interaction_id = f"{self.run_name}_{item_id}"
            print(f"  Processing item: {item_id}")

            # --- ISOLATION: Create FRESH Chat instance PER ITEM ---
            chat = self.profile.create_chat()
            initial_usage = chat.use # Should be ~zero

            start_time = time.monotonic()
            run_error = None
            eval_results = {}
            tool_calls_in_item = []

            # Get final parameters for the LLM call for this item
            call_params = self.profile.get_call_params(**call_overrides)

            try:
                prompt = item.get("prompt")
                if not prompt: raise ValueError(f"Item {item_id} missing 'prompt'")

                # Decide whether to use toolloop or standard call
                if use_toolloop:
                    def _tracer(history_slice):
                        # Basic parsing of history_slice to identify tool name, args, result
                        # Append to tool_calls_in_item list
                        pass # Placeholder
                    # _ = await chat.toolloop(pr=prompt, trace_func=_tracer, **call_params)
                    pass # Placeholder
                else:
                    # _ = await chat(pr=prompt, **call_params)
                    pass # Placeholder

                # Safely extract final output text and raw response
                # final_output_text = contents(...)
                # final_output_raw = chat.c.result.model_dump()
                final_output_text = "Placeholder result" # Placeholder
                final_output_raw = {} # Placeholder

                # --- Apply Evaluators ---
                if self.evaluators:
                    for evaluator in self.evaluators:
                        try:
                            # Pass item, the *completed* chat instance for this item, and ground truth
                            # eval_output = evaluator(item, chat, item.get("ground_truth"))
                            # eval_results.update(eval_output)
                            pass # Placeholder evaluation call
                        except Exception as e:
                            eval_results[f"eval_{evaluator.__name__}_error"] = traceback.format_exc()
                            print(f"    Evaluator error: {e}")

            except Exception as e:
                run_error = traceback.format_exc()
                final_output_text = "[Error]"
                final_output_raw = None
                print(f"    Item processing error: {e}")

            latency_ms = (time.monotonic() - start_time) * 1000

            # Calculate usage delta for this isolated item run
            current_usage = chat.use
            # usage_delta = calculate_usage_delta(initial_usage, current_usage)
            usage_delta_dict = {} # Placeholder
            # cost_delta = calculate_cost(...)

            # Prepare log entry using framework.logging.format_log_entry
            log_entry_data = {
                "run_name": self.run_name,
                "profile_id": self.profile.profile_id,
                "interaction_id": interaction_id,
                "run_type": 'eval',
                "timestamp": datetime.datetime.now().isoformat(),
                "input_data": item, # Log the full dataset item
                "call_params": call_params,
                "chat_history": [msg for msg in chat.h], # History *just for this item*
                "tool_calls": tool_calls_in_item,
                "latency_ms": latency_ms,
                "final_output_text": final_output_text,
                "final_output_raw": final_output_raw,
                "usage_info": usage_delta_dict, # Log usage for this item
                "cost_info": None, # Placeholder for cost
                "evaluation_results": eval_results,
                "error_info": run_error,
                "metadata": self.profile.metadata
            }
            # log_entry = format_log_entry(**log_entry_data)
            # log_to_file(log_entry, self.log_path)

            # Store key results for summary
            summary = {"item_id": item_id, "latency_ms": latency_ms, "error": bool(run_error), **eval_results}
            self.results_summary.append(summary)

        total_run_time_s = time.monotonic() - run_start_time
        print("-" * 20)
        print(f"Evaluation run {self.run_name} finished.")
        print(f"Processed {len(self.results_summary)} items in {total_run_time_s:.2f}s.")
        print(f"Detailed logs: {self.log_path}")
        # TODO: Add aggregation of results_summary (avg accuracy, error rate, avg latency etc.)
        print("-" * 20)
        return self.results_summary # Return the summary list for immediate analysis


# %% Component 6: Execution Scripts (`run_eval.py`, `run_interactive.py`)
# =======================================================================
# These scripts tie everything together. They import profiles, datasets, evaluators,
# instantiate `EvalLoop` or `AgentRunner`, and trigger the execution.

# --- File: run_eval.py (Conceptual) ---
async def run_evaluation():
    # 1. Import the specific agent profile to test
    # from profiles.calculator_agent_v1 import profile as calculator_profile_v1
    # from profiles.calculator_agent_v2 import profile as calculator_profile_v2 # Example for comparison
    target_profile = None # Placeholder: Assign the imported profile

    # 2. Load the dataset
    # dataset = load_my_dataset('data/calculator_tests.jsonl') # Implement data loading
    dataset = [{'id': 'calc1', 'prompt': 'What is 2+2?', 'ground_truth': '4'}] # Simple example

    # 3. Import or define evaluators
    # from framework.evaluation import exact_match_evaluator # Need import
    evaluators = [] # Placeholder: Add evaluator functions

    # 4. Initialize EvalLoop
    # eval_loop = EvalLoop(
    #     profile=target_profile,
    #     dataset=dataset,
    #     evaluators=evaluators,
    #     run_name=f"eval_{target_profile.profile_id}_on_calc_tests" # Explicit run name
    # )

    # 5. Run the evaluation
    # summary = await eval_loop.run(
    #     use_toolloop=True, # Or False
    #     # Override specific params for this run if needed, e.g., temp=0.1
    # )

    # 6. Perform basic analysis on the summary (or load the JSONL for deeper analysis)
    # print("Evaluation Summary:", summary)
    pass # Placeholder

# if __name__ == "__main__":
#     import asyncio
#     asyncio.run(run_evaluation())


# --- File: run_interactive.py (Conceptual) ---
async def run_interactive_session():
    # 1. Import the specific agent profile
    # from profiles.concierge_agent_v1 import profile as concierge_profile
    target_profile = None # Placeholder

    # 2. Initialize AgentRunner
    # runner = AgentRunner(profile=target_profile)

    print("Starting interactive session (type 'quit' to exit, 'reset' for new convo)...")
    while True:
        user_input = input("You: ")
        if user_input.lower() == 'quit':
            break
        if user_input.lower() == 'reset':
            # runner.reset_session()
            print("\n--- Session Reset ---")
            continue

        # 3. Run a turn
        # agent_response = await runner.run_turn(
        #     user_input=user_input,
        #     use_toolloop=True # Usually True for tool agents
        #     # Add overrides if needed: temp=0.6
        # )
        agent_response = f"Agent: You said '{user_input}' (Placeholder)" # Placeholder
        print(agent_response)

# if __name__ == "__main__":
#     import asyncio
#     asyncio.run(run_interactive_session())


# %% Conclusion
# ==============
# This structure provides a solid foundation. Key next steps for implementation:
# 1. Implement the actual `claudette` calls within `AgentRunner` and `EvalLoop`.
# 2. Flesh out the logging details in `format_log_entry`, ensuring all necessary data is captured and serializable. Pay attention to extracting tool call details accurately from `toolloop` traces.
# 3. Implement robust dataset loading.
# 4. Implement more sophisticated evaluators (LLM-as-judge is important but tricky).
# 5. Build analysis scripts/notebooks to read the `.jsonl` logs and compare runs effectively. Focus on surfacing key metrics and identifying regressions quickly.
# 6. Implement cost calculation based on token usage and model pricing.
# Remember to keep iterating! Start with the simplest working version and add complexity only as needed, always guided by measurement.