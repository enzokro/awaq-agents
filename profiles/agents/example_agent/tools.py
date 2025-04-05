"""Example agent tools."""

import datetime
from claudette.core import tool

@tool
def get_current_time() -> str:
    """Returns the current date and time as an ISO 8601 formatted string."""
    now = datetime.datetime.now().isoformat()
    print(f"Tool Execution: get_current_time() -> {now}") # note: this prints in the chat session
    return now

@tool
def think(
    thought: str, # the thought or idea to think about to solve the user request
    ) -> str: # do not worry about returning anything, only think
    """Use this tool to think about the user's request. You will not obtain new information or change the user's input. It only helps you think about the task and problem to maximally, accurately, and completely solve the user's request."""
    print(f"Tool Execution: think() -> {thought}")
    return thought

# group up the tools for easy import
tools = [get_current_time, think]
