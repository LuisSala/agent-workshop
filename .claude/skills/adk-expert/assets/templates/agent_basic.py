"""
Basic ADK Agent Template

A simple LLM agent with minimal configuration.
"""

from google.adk.agents import Agent
from google.adk.runners import Runner


def create_agent():
    """Create a basic agent."""
    agent = Agent(
        name="my_agent",
        model="gemini-2.5-flash",
        instruction="""You are a helpful assistant.

        Be concise and accurate in your responses.""",
        description="A simple assistant agent"
    )
    return agent


def main():
    """Run the agent."""
    agent = create_agent()
    runner = Runner(agent)

    print("Agent ready. Type 'quit' to exit.")

    while True:
        user_input = input("\nYou: ").strip()

        if user_input.lower() in ('quit', 'exit', 'q'):
            print("Goodbye!")
            break

        if not user_input:
            continue

        print("Agent: ", end="", flush=True)

        for event in runner.run(user_input):
            if event.partial:
                # Stream partial responses
                print(event.content.text, end="", flush=True)
            elif event.is_final_response():
                # Final response
                print(event.content.text)


if __name__ == "__main__":
    main()
