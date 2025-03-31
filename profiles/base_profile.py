"""Base profile for an LLM claudette agent."""

from dataclasses import dataclass, field
from typing import List, Callable, Dict, Any
from claudette.core import Chat


@dataclass
class AgentProfile:
    """
    Defines an agent.
    Version: Phase 2 - Added tools and default_params.
    """
    profile_id: str          # Unique identifier (e.g., 'basic_agent_v1').
    model: str               # The specific claudette model string.
    system_prompt: str = ""  # The core instructions.
    prefill_prompt: str = "" # The prefill prompt.
    tools: List[Callable] = field(default_factory=list)
    default_params: Dict[str, Any] = field(default_factory=dict)

    def create_chat(self, **override_chat_params) -> Chat:
        """
        Creates a Chat object based on this profile.
        Phase 2: Passes tools to Chat constructor. Assumes tools are pre-decorated.
        """
        print(f"Creating Chat for profile: {self.profile_id} with model: {self.model}")
        # Combine default profile params with any overrides for Chat initialization
        # Primarily 'temp' for now, others might be relevant later
        chat_init_params = self.default_params.copy()
        chat_init_params.update(override_chat_params)
        
        temp = chat_init_params.get('temp', 0.0) # Get temperature, default 0

        # create a chat with tools
        return Chat(
            model=self.model,
            sp=self.system_prompt,
            tools=self.tools,
            temp=temp,
            # Add other relevant Chat init args as framework evolves
        )

    def get_call_params(self, **call_overrides) -> Dict[str, Any]:
        """
        Helper to get the final dict of parameters for a specific LLM call.
        Merges profile defaults with run-time overrides. Useful for logging.
        (Phase 5 refinement) - Basic version for now.
        """
        params = self.default_params.copy()
        params.update(call_overrides)
        # TODO: cleaner way of handling prefill
        params.update({'prefill': self.prefill_prompt})
        return params

    def __repr__(self):
        tool_names = [getattr(t, '__name__', str(t)) for t in self.tools]
        return f"AgentProfile(profile_id='{self.profile_id}', model='{self.model}', tools={len(tool_names)})"
