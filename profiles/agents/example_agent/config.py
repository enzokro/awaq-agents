"""Basic configuration for our example agent."""

from .tools import tools

profile_id = "example_agent_v0"
model = "claude-3-haiku-20240307"
system_prompt = """You are a helpful assistant."""
prefill_prompt = "I will now use the appropriate tools to fully complete the user's request."

# good defaults for claudette tool-calling, we want temp = 0
DEFAULT_PARAMS = {
    'temp': 0.,
    'maxtok': 4096,
    'max_steps': 10,
}

base_config = {
    "profile_id": profile_id,
    "model": model,
    "system_prompt": system_prompt,
    "prefill_prompt": prefill_prompt,
    "tools": tools,
    "default_params": DEFAULT_PARAMS
}