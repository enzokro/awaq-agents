"""Runs an agent."""

import datetime
import uuid
import traceback
from typing import Optional, List

from claudette import *
from anthropic.types import ToolUseBlock, Message

from profiles.base_profile import AgentProfile
from framework.logging import get_log_path, format_log_entry, log_to_file


class AgentRunner:
    """
    Runs interactive sessions with an agent defined by an AgentProfile.
    Maintains conversation state (`claudette.Chat` instance) across turns.
    Logs each turn comprehensively.
    Version: Phase 2 - Using toolloop and logging tool calls.
    """
    def __init__(
            self, 
            profile: AgentProfile, 
            log_dir: str = "results", 
            run_name_prefix: str = "interactive",
            use_toolloop: bool = True,
            session_id: str = None,
            chats: dict = {}
        ):
        """Initializes with a profile, sets up logging for the session."""
        self.profile = profile
        self.session_id = session_id or str(uuid.uuid4())
        self.run_name = f"{run_name_prefix}_{self.profile.profile_id}_{self.session_id[:8]}"
        self.log_path = get_log_path(log_dir, self.run_name)
        self.use_toolloop = use_toolloop

        # manage multiple chats
        self.chats = chats
        # self.chat = profile.create_chat()

        print(f"AgentRunner initialized (Session: {self.session_id}), logging to {self.log_path}")

        self.turn_count = 0

    def _tracer(self, history_slice: List[Message]):
        """
        This function will be called by toolloop *during* its execution
        It receives the history slice added in one tool request/response cycle
        """
        self.tool_calls_in_turn = getattr(self, 'tool_calls_in_turn', [])
        # Basic Tracer: Look for ToolUseBlock and subsequent ToolResult
        tool_use_msg = None
        tool_result_msg = None

        # The slice usually contains [assistant_tool_use, user_tool_result]
        if len(history_slice) >= 1 and history_slice[0].role == 'assistant':
                tool_use_msg = history_slice[0]
        if len(history_slice) >= 2 and history_slice[1].role == 'user':
                tool_result_msg = history_slice[1]

        if tool_use_msg and tool_result_msg:
            # Extract details from ToolUseBlock(s)
            for block in tool_use_msg.content:
                if isinstance(block, ToolUseBlock):
                    tool_name = block.name
                    tool_args = block.input
                    tool_use_id = block.id
                    tool_result = "[Result Not Found in Tracer]" # Default
                    
                    # Find corresponding result in the user message
                    for res_block in tool_result_msg.content:
                        if res_block.type == 'tool_result' and res_block.tool_use_id == tool_use_id:
                            tool_result = res_block.content
                            break # Found the result for this tool_use_id
                    
                    self.tool_calls_in_turn.append({
                        "tool_name": tool_name,
                        "tool_args": tool_args,
                        "tool_result": tool_result,
                        "tool_use_id": tool_use_id # Log the ID for correlation
                    })
                    print(f"-- Tracer captured tool: {tool_name}({tool_args}) -> {tool_result[:100]}...") # Debug print

    def create_chat(self, chat_id: str):
        """Create a new chat and add it to the chats dictionary."""
        if chat_id not in self.chats:
            chat = self.profile.create_chat()
            self.chats[chat_id] = chat
        else:
            print(f"Chat {chat_id} already exists")


    def run_turn(self, user_input: str, chat_id: str = None, **call_overrides) -> Optional[str]:
        """
        Processes a single turn of user input using the persistent chat instance.
        Uses toolloop to handle potential tool calls.
        Logs the details of this specific turn, including tool calls.
        """
        self.chat = self.chats[chat_id]

        self.turn_count += 1
        interaction_id = f"{self.session_id}_turn_{self.turn_count}"
        final_output_text = None
        run_error = None

        # Get final parameters for the LLM call (profile defaults + overrides)
        # Filter for parameters relevant to toolloop/chat call if necessary
        call_params = self.profile.get_call_params(**call_overrides)

        # --- Execute Turn using Toolloop --- 
        input_data = {'user_input': user_input}
        try:
            if self.use_toolloop:
                # parse out the prefill for the first call
                prefill = call_params.pop('prefill', '')
                # Call toolloop (synchronous)
                response_msg = self.chat.toolloop(
                    pr=user_input,
                    trace_func=self._tracer, 
                    first_call_prefill=prefill,
                    **call_params # Pass relevant overrides like temp, maxtok
                )
            else:
                print("WARNING! claudette.toolloop could not be imported, defaulting to regular call....")
                _ = call_params.pop('max_steps', None)
                response_msg = self.chat(user_input, **call_params)
            
            # Get final text content and log the turn
            final_output_text = contents(response_msg)
            self.log_turn(interaction_id, input_data, final_output_text)

            return final_output_text

        except Exception as e:
            run_error = traceback.format_exc()
            final_output_text = f"[Error during generation: {e}]"
            print(run_error)

        return final_output_text

    def log_turn(self, interaction_id, input_data, final_output_text):
        """Prepare and store log data"""
        log_entry_data = {
            "run_name": self.run_name,
            "profile_id": self.profile.profile_id,
            "interaction_id": interaction_id,
            "run_type": 'interactive',
            "timestamp": datetime.datetime.now().isoformat(),
            "input_data": input_data,
            "chat_history": [msg.model_dump() if hasattr(msg, 'model_dump') else msg for msg in self.chat.h],
            "tool_calls": getattr(self, 'tool_calls_in_turn', None), # Pass captured calls
            "final_output_text": final_output_text,
            # Add placeholders...
        }
        
        log_entry = format_log_entry(**log_entry_data)
        log_to_file(log_entry, self.log_path)

    def reset_session(self):
        """Resets the chat history, starting a new logical conversation."""
        print("Resetting session...")
        try:
            self.chat = self.profile.create_chat()
            self.session_id = str(uuid.uuid4())
            # Update run_name and log_path for the new session
            self.run_name = f"{self.run_name.split('_')[0]}_{self.profile.profile_id}_{self.session_id[:8]}"
            self.log_path = get_log_path(self.log_path.parent, self.run_name)
            self.turn_count = 0 
            print(f"New session started: {self.session_id}. Logging to: {self.log_path}")
        except Exception as e:
            print(f"ERROR: Failed to reset AgentRunner Chat instance: {e}")
            self.chat = None # Ensure runner knows chat is invalid
