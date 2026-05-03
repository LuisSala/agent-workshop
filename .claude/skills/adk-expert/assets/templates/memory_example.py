"""
Agent with Memory Service Template

Demonstrates long-term memory across sessions using MemoryService.
"""

from google.adk.agents import Agent
from google.adk.tools import FunctionTool, ToolContext
from google.adk.runners import Runner
from google.adk.services import InMemorySessionService, MemoryService


def remember_fact(fact: str, category: str, tool_context: ToolContext) -> dict:
    """
    Store a fact in long-term memory.

    Use this when user wants to save information for future reference.

    Args:
        fact: The information to remember
        category: Category of the fact (e.g., "preference", "personal", "work")
        tool_context: Tool context for memory access

    Returns:
        Dict with status and confirmation
    """
    try:
        tool_context.memory_service.add(
            content=fact,
            metadata={
                "category": category,
                "source": "user_input"
            }
        )

        return {
            "status": "success",
            "message": f"Remembered: {fact} (category: {category})"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to store memory: {str(e)}"
        }


def recall_facts(query: str, tool_context: ToolContext) -> dict:
    """
    Retrieve relevant facts from long-term memory.

    Use this when user asks about previously saved information.

    Args:
        query: What to search for in memories
        tool_context: Tool context for memory access

    Returns:
        Dict with status and retrieved memories
    """
    try:
        memories = tool_context.memory_service.search(
            query=query,
            top_k=5
        )

        if not memories:
            return {
                "status": "success",
                "message": "No relevant memories found.",
                "memories": []
            }

        memory_list = [
            {
                "content": m.content,
                "metadata": m.metadata
            }
            for m in memories
        ]

        return {
            "status": "success",
            "memories": memory_list,
            "count": len(memories)
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to retrieve memories: {str(e)}"
        }


def create_agent_with_memory():
    """Create an agent with memory capabilities."""
    agent = Agent(
        name="memory_agent",
        model="gemini-2.5-flash",
        instruction="""You are a helpful assistant with long-term memory.

        You can:
        - Remember facts using remember_fact tool
        - Recall information using recall_facts tool

        When user shares information they want you to remember, use remember_fact.
        When user asks about previously saved information, use recall_facts.

        Categories for facts:
        - "preference": User preferences and likes/dislikes
        - "personal": Personal information
        - "work": Work-related information
        - "general": General knowledge

        Always confirm what you've remembered and proactively recall relevant info.""",

        tools=[
            FunctionTool(remember_fact),
            FunctionTool(recall_facts)
        ],

        description="An assistant with long-term memory capabilities"
    )
    return agent


def main():
    """Run the agent with memory."""
    agent = create_agent_with_memory()

    # Create services
    session_service = InMemorySessionService()
    memory_service = MemoryService()

    # Create runner with services
    runner = Runner(
        agent=agent,
        session_service=session_service,
        memory_service=memory_service,
        session_id="demo_session",
        user_id="demo_user"
    )

    print("Agent with Memory ready!")
    print("Try: 'Remember that I like coffee' or 'What do you know about my preferences?'")
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


if __name__ == "__main__":
    main()
