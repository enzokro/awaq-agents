
from dotenv import load_dotenv

# Attempt to import necessary components
from profiles.agents.example_agent.agent import profile as agent_profile
from framework.agent_runner import AgentRunner

# Load environment variables
load_dotenv()


def run_interactive_session():
    """Runs the main interactive command-line session."""
    print("Initializing AgentRunner...")
    try:
        runner = AgentRunner(
            profile=agent_profile,
            # use_toolloop=False,
        )
    except Exception as e:
        print(f"Failed to initialize AgentRunner: {e}")
        print("Exiting.")
        return

    if runner.chat is None:
        print("AgentRunner could not start a chat session. Check previous errors. Exiting.")
        return

    print("\n--- Starting Interactive Session ---")
    print(f"Agent Profile: {runner.profile.profile_id}")
    print(f"Model: {runner.profile.model}")
    print(f"Logging to: {runner.log_path}")
    print("(Type 'quit' or 'exit' to end, 'reset' to clear history)")
    print("-" * 20)

    while True:
        try:
            user_input = input("You: ")
        except EOFError: # Handle Ctrl+D
            print("\nExiting.")
            break

        cleaned_input = user_input.strip().lower()
        if cleaned_input in ['quit', 'exit']:
            print("Exiting.")
            break
        if cleaned_input == 'reset':
            runner.reset_session() # Basic reset for now
            print("\n--- Session Reset --- \n")
            continue
        if not user_input.strip(): # Ignore empty input
            continue

        print("Agent: Thinking...") # Provide feedback
        try:
            agent_response = runner.run_turn(user_input=user_input)
            print(f"Agent: {agent_response}")
        except Exception as e:
            print(f"\n--- ERROR DURING TURN --- ")
            print(f"{e}")
            print("Continuing session, but an error occurred.")
            print("-" * 20)
            # Optionally log this error more formally if needed

if __name__ == "__main__":
    print("Starting interactive agent runner...")
    try:
        run_interactive_session()
    except KeyboardInterrupt:
        print("\nCaught interrupt, exiting cleanly.")
    except Exception as e:
        print(f"\n--- UNEXPECTED ERROR IN MAIN LOOP --- ")
        print(f"{e}")
