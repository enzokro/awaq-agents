from profiles.base_profile import AgentProfile
from .config import base_config

# creating a basic agent with tools
profile = AgentProfile(**base_config)
