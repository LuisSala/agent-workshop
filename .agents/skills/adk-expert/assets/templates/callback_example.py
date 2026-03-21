"""
Agent with Callbacks Template

Demonstrates lifecycle callbacks for monitoring and logging.
"""

from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.runners import InvocationContext
import datetime


# Define callback functions
def before_agent_callback(context: InvocationContext):
    """Called before agent starts processing."""
    print(f"\n[{datetime.datetime.now().strftime('%H:%M:%S')}] Agent '{context.agent.name}' starting")
    print(f"[Events in context: {len(context.events)}]")


def after_agent_callback(context: InvocationContext):
    """Called after agent completes processing."""
    print(f"\n[{datetime.datetime.now().strftime('%H:%M:%S')}] Agent '{context.agent.name}' finished")


def before_model_callback(context: InvocationContext):
    """Called before each LLM call."""
    print(f"[Calling LLM: {context.agent.model}]")


def after_model_callback(context: InvocationContext):
    """Called after each LLM response."""
    # Access token usage if available
    if hasattr(context, 'usage') and context.usage:
        print(f"[Tokens used: {getattr(context.usage, 'total_tokens', 'N/A')}]")


def create_agent_with_callbacks():
    """Create an agent with lifecycle callbacks."""
    agent = Agent(
        name="monitored_agent",
        model="gemini-2.5-flash",
        instruction="You are a helpful assistant.",

        # Register callbacks
        before_agent_callback=before_agent_callback,
        after_agent_callback=after_agent_callback,
        before_model_callback=before_model_callback,
        after_model_callback=after_model_callback
    )
    return agent


def main():
    """Run the agent with callbacks."""
    agent = create_agent_with_callbacks()
    runner = Runner(agent)

    print("Agent with callbacks ready!")
    print("Watch for callback logs during execution.")
    print("Type 'quit' to exit.\n")

    while True:
        user_input = input("\nYou: ").strip()

        if user_input.lower() in ('quit', 'exit', 'q'):
            print("Goodbye!")
            break

        if not user_input:
            continue

        print("\nAgent: ", end="", flush=True)

        for event in runner.run(user_input):
            if event.partial:
                print(event.content.text, end="", flush=True)
            elif event.is_final_response():
                print(event.content.text)


if __name__ == "__main__":
    main()
