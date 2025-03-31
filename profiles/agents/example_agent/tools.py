"""Example agent tools."""

import datetime
from claudette.core import tool

@tool
def get_current_time() -> str:
    """Returns the current date and time as an ISO 8601 formatted string."""
    now = datetime.datetime.now().isoformat()
    print(f"Tool Execution: get_current_time() -> {now}") # note: this prints in the chat session
    return now

# group up the tools for easy import
tools = [get_current_time]
