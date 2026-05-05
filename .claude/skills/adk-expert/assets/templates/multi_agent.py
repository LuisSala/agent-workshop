"""
Multi-Agent Coordinator Template

A coordinator agent that routes requests to specialist agents.
"""

from google.adk.agents import Agent
from google.adk.runners import Runner


def create_multi_agent_system():
    """Create a multi-agent system with coordinator and specialists."""

    # Specialist 1: Technical questions
    tech_specialist = Agent(
        name="tech_specialist",
        model="gemini-2.5-flash",
        instruction="""You are a technical specialist.

        Answer questions about:
        - Programming and software development
        - Technology and computing
        - APIs and systems design

        Be precise and provide code examples when relevant.""",

        description="Handles technical and programming questions"
    )

    # Specialist 2: General knowledge
    knowledge_specialist = Agent(
        name="knowledge_specialist",
        model="gemini-2.5-flash",
        instruction="""You are a general knowledge specialist.

        Answer questions about:
        - History, science, and culture
        - Current events and news
        - General information

        Be informative and cite sources when possible.""",

        description="Handles general knowledge and information queries"
    )

    # Coordinator: Routes to appropriate specialist
    coordinator = Agent(
        name="coordinator",
        model="gemini-2.5-flash",
        instruction="""You are a coordinator agent that routes user queries to specialists.

        Routing rules:
        - Technical/programming questions → tech_specialist
        - General knowledge/information → knowledge_specialist

        If unsure, handle the query yourself or ask for clarification.

        Always be helpful and ensure the user gets the best answer.""",

        sub_agents=[tech_specialist, knowledge_specialist],

        description="Routes queries to appropriate specialist agents"
    )

    return coordinator


def main():
    """Run the multi-agent system."""
    coordinator = create_multi_agent_system()
    runner = Runner(coordinator)

    print("Multi-Agent System Ready!")
    print("Ask technical questions or general knowledge questions.")
    print("Type 'quit' to exit.\n")

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
                print(event.content.text, end="", flush=True)
            elif event.is_final_response():
                print(event.content.text)
                # Show which agent handled the request
                if event.author != "coordinator":
                    print(f"\n[Handled by: {event.author}]")


if __name__ == "__main__":
    main()
