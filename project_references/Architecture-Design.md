Architecture Design Document (ADD): Agent Development & Evaluation Framework (`cck-agents`)

1. Introduction

This document describes the architecture for the Agent Development & Evaluation Framework (`cck-agents`), designed to support the systematic development, evaluation, and logging of claudette-based LLM agents as outlined in PRD v1.0. The architecture emphasizes modularity, clear separation of concerns, and leverages the claudette library effectively.

2. Architectural Goals

Provide a clear and maintainable structure for agent definition and execution logic.

Ensure consistent and comprehensive logging across different execution modes.

Facilitate easy extension with new agents, tools, and evaluators.

Maintain low coupling between components.

Support isolated evaluation runs and stateful interactive sessions.

3. Core Components

AgentProfile (Dataclass - profiles/base_profile.py):

Responsibility: Represents the static blueprint of an agent. Holds configuration data (profile_id, model, system_prompt, tools, default_params, metadata). Does not hold runtime state.

Key Methods: create_chat(): Instantiates a configured claudette.Chat object. get_call_params(): Merges default and override parameters.

Interaction: Loaded by EvalLoop and AgentRunner to configure agent behavior. Specific profiles (e.g., profiles/calculator_agent_v1.py) inherit from or conform to this structure.

EvalLoop (Class - framework/eval_loop.py):

Responsibility: Orchestrates batch evaluation of an AgentProfile against a dataset.

Workflow:

Initializes with an AgentProfile, dataset, evaluators, and run configuration.

Generates a unique run_name and log file path.

Iterates through the dataset.

For each dataset item:

Creates a fresh, isolated claudette.Chat instance using profile.create_chat().

Determines final call parameters (profile defaults + run overrides).

Executes the interaction using chat.toolloop() or chat().

Calls registered Evaluator functions with the item, completed Chat instance, and ground truth.

Formats and logs the complete interaction details (input, output, history, tools, params, usage, latency, evals, errors) using framework/logging.py.

State: Primarily holds configuration for the run; runtime state is isolated per dataset item via fresh Chat instances.

AgentRunner (Class - framework/agent_runner.py):

Responsibility: Manages single-turn or multi-turn interactive sessions with an agent.

Workflow:

Initializes with an AgentProfile.

Creates a persistent claudette.Chat instance for the session.

Generates a session_id and log file path.

run_turn() method:

Accepts user input.

Determines final call parameters.

Executes the interaction using chat.toolloop() or chat() on the persistent Chat instance (maintaining history).

Formats and logs the details for that specific turn (input, output, history state after turn, tools used in turn, params, usage delta, latency, errors).

State: Maintains the stateful claudette.Chat instance across multiple run_turn() calls within a session. Provides reset_session().

Logging Utilities (framework/logging.py):

Responsibility: Provides standardized functions for formatting log entries (format_log_entry) according to a defined schema and appending them (log_to_file) to the correct JSONL file.

Format: JSONL (one JSON object per line/interaction). Schema defined in format_log_entry.

Storage: results/ directory, named by run_name.

Evaluation Utilities (framework/evaluation.py):

Responsibility: Defines the Evaluator function type signature and holds implementations of various evaluation metrics (e.g., exact match, regex, length, potentially LLM-as-judge wrappers).

Interface: Callable[[DatasetItem, Chat, Optional[Any]], EvaluationResult] - Takes input item, completed Chat, ground truth; returns dict of metrics.

Directory Structure (profiles/, framework/, data/, results/):

Responsibility: Organizes code, data, and results logically for clarity and discoverability. profiles/ contains agent definitions, framework/ contains core logic.

4. Data Flow Diagram (Mermaid)

graph TD
    subgraph Configuration
        PBase[AgentProfile Definition <br> profiles/base_profile.py]
        CT[Common Tools <br> profiles/common_tools.py]
        Prof[Specific Profile <br> profiles/*.py]

        PBase <-.- Prof
        CT <-.- Prof
    end

    subgraph Execution
        User(User Input) --> AR[AgentRunner <br> framework/agent_runner.py]
        Dataset(Dataset <br> data/*.jsonl) --> EL[EvalLoop <br> framework/eval_loop.py]

        Prof -- Creates Chat --> AR
        Prof -- Creates Chat (per item) --> EL

        AR -- Runs Turn --> ChatAR(claudette.Chat - Persistent)
        EL -- Runs Item --> ChatEL(claudette.Chat - Fresh)

        ChatAR -- Calls --> Tools(Tool Functions)
        ChatEL -- Calls --> Tools

        Tools -- Returns --> ChatAR
        Tools -- Returns --> ChatEL

        EvalFuncs(Evaluator Functions <br> framework/evaluation.py) -- Called By --> EL
        EvalFuncs -- Input: ChatEL State --> EL
        EL -- Output: Metrics --> LogFmt

        ChatAR -- Turn Output --> AR
        ChatEL -- Item Output --> EL

        AR -- Data for Logging --> LogFmt(Log Formatting <br> framework/logging.py)
        EL -- Data for Logging --> LogFmt
    end

    subgraph Output & Analysis
        LogFmt -- Writes --> LogFile(JSONL Log File <br> results/*.jsonl)
        AR -- Output --> UserTerm(User Terminal)
        LogFile -- Read By --> Analysis(Analysis Scripts / Notebooks)
    end

    style Prof fill:#lightcyan
    style AR fill:#lightgreen
    style EL fill:#lightgreen
    style LogFile fill:#orange
    style Analysis fill:#thistle

Mermaid
5. Key Design Decisions

AgentProfile as Central Definition: Encapsulates static configuration, promoting reuse and clear versioning. Separates definition from runtime state.

JSONL Logging: Chosen for its append-friendliness, ease of parsing line-by-line, and suitability for structured data. Captures comprehensive context for each interaction.

Separate EvalLoop and AgentRunner: Addresses different state management needs. EvalLoop requires isolation per item (fresh Chat), while AgentRunner requires persistence (single Chat per session).

Fresh Chat per Item in EvalLoop: Guarantees evaluation isolation, preventing history from one item affecting the next. Critical for reliable batch evaluation.

Pluggable Evaluators: Simple function-based interface allows easy addition of custom metrics without modifying the core EvalLoop.

Minimal Abstraction: Primarily uses claudette's Chat and tool directly, avoiding complex intermediate layers. Focuses on orchestration, logging, and evaluation structure.

6. Technology Stack

Language: Python 3.x

Core Libraries: claudette, dataclasses, fastcore (implicitly via claudette), asyncio (for async operations in claudette).

Data Handling: Standard Python libraries for file I/O, json. (Analysis might use pandas).

7. Directory Structure

.
├── profiles/
│   ├── base_profile.py       # AgentProfile dataclass definition
│   ├── common_tools.py       # Shared tool functions
│   ├── calculator_agent_v1.py # Example specific profile
│   └── ...                   # Other agent profiles
├── framework/
│   ├── agent_runner.py       # Interactive execution logic
│   ├── eval_loop.py          # Batch evaluation logic
│   ├── logging.py            # Logging formatters and writers
│   ├── evaluation.py         # Evaluator function definitions/types
│   └── __init__.py
├── data/
│   └── sample_eval_dataset.jsonl # Example evaluation data
├── results/
│   └── (Log files generated here...)
├── run_eval.py               # Example script to run EvalLoop
├── run_interactive.py        # Example script to run AgentRunner
└── requirements.txt          # Project dependencies

8. Future Development / Scalability

The component-based structure allows individual parts (logging, evaluation, profiles) to be enhanced independently.

Logging to databases or observability platforms could replace/supplement JSONL files by modifying framework/logging.py.

Analysis can be scaled using distributed processing frameworks reading from the log files or a database.

Configuration management could be introduced for handling multiple environments or complex run parameters.