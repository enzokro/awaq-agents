import json
import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List

LOG_SCHEMA_VERSION = "0.2" # Incremented for tool_calls addition
DEFAULT_LOG_DIR = "results"

def get_log_path(log_dir: str = DEFAULT_LOG_DIR, run_name: Optional[str] = None) -> Path:
    """Determines the log file path. Ensures the directory exists."""
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True) # Ensure directory exists

    if not run_name:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        run_name = f"run_{timestamp}"

    file_name = f"{run_name}.jsonl"
    return log_path / file_name

def format_log_entry(
    run_name: str,
    profile_id: str,
    interaction_id: str,
    timestamp: str,
    run_type: str,
    input_data: Dict[str, Any],
    final_output_text: Optional[str],
    chat_history: List[Dict[str, Any]], # Expecting list of claudette message dicts
    tool_calls: Optional[List[Dict[str, Any]]] = None, # <-- Added
) -> Dict[str, Any]:
    """
    Creates the structured log dictionary.
    Version: Phase 2 - Added tool_calls field.
    """
    log_entry = {
        "log_schema_version": LOG_SCHEMA_VERSION,
        "run_name": run_name,
        "profile_id": profile_id,
        "interaction_id": interaction_id,
        "run_type": run_type,
        "timestamp": timestamp,
        "input_data": input_data,
        "chat_history": chat_history, # Full history up to this point
        "tool_calls": tool_calls, # <-- Included
        "final_output_text": final_output_text,
        # Add placeholders for future fields if desired, e.g., "call_params": None, "usage_info": None, "cost_info": None, "error_info": None, "metadata": None
    }
    # Minimal cleanup: remove keys with None values
    return {k: v for k, v in log_entry.items() if v is not None}

def log_to_file(log_entry: Dict[str, Any], file_path: Path):
    """
    Appends a formatted log entry (dict) as a JSON line to the specified file.
    Handles basic serialization; assumes input dict is mostly serializable.
    """
    try:
        with open(file_path, "a", encoding='utf-8') as f:
            # Use default=str as a basic fallback for non-serializable types
            f.write(json.dumps(log_entry, default=str) + "\n")
    except Exception as e:
        print(f"ERROR: Failed logging to {file_path}: {e}")
        # Consider more robust error handling in later phases

