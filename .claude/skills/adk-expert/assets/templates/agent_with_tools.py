"""
ADK Agent with Custom Tools Template

An agent with custom tools for specific capabilities.
"""

from google.adk.agents import Agent
from google.adk.tools import FunctionTool, ToolContext
from google.adk.runners import Runner
import datetime


# Define custom tools
def get_current_time() -> dict:
    """
    Get the current date and time.

    Use this when user asks about the current time or date.

    Returns:
        Dict with status and current datetime information
    """
    now = datetime.datetime.now()
    return {
        "status": "success",
        "datetime": now.isoformat(),
        "formatted": now.strftime("%Y-%m-%d %H:%M:%S")
    }


def calculator(expression: str) -> dict:
    """
    Evaluate a mathematical expression.

    Use this when user needs to perform calculations.

    Args:
        expression: Mathematical expression (e.g., "2 + 2", "10 * 5")

    Returns:
        Dict with status and calculation result
    """
    try:
        # Safe evaluation (only allow basic math)
        result = eval(expression, {"__builtins__": {}}, {})
        return {
            "status": "success",
            "expression": expression,
            "result": result
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Invalid expression: {str(e)}"
        }


def store_note(note: str, tool_context: ToolContext) -> dict:
    """
    Store a note in the session state.

    Use this when user wants to save information for later.

    Args:
        note: The note content to store
        tool_context: Tool context for state access

    Returns:
        Dict with status and confirmation
    """
    # Get existing notes
    notes = tool_context.state.get('user:notes', [])

    # Add new note with timestamp
    notes.append({
        'content': note,
        'timestamp': datetime.datetime.now().isoformat()
    })

    # Store back
    tool_context.state['user:notes'] = notes

    return {
        "status": "success",
        "message": f"Stored note. Total notes: {len(notes)}"
    }


def retrieve_notes(tool_context: ToolContext) -> dict:
    """
    Retrieve all stored notes.

    Use this when user wants to see their saved notes.

    Args:
        tool_context: Tool context for state access

    Returns:
        Dict with status and notes list
    """
    notes = tool_context.state.get('user:notes', [])

    if not notes:
        return {
            "status": "success",
            "message": "No notes stored yet."
        }

    return {
        "status": "success",
        "notes": notes,
        "count": len(notes)
    }


def create_agent():
    """Create an agent with custom tools."""
    agent = Agent(
        name="tool_agent",
        model="gemini-2.5-flash",
        instruction="""You are a helpful assistant with access to tools.

        You can:
        - Tell the current time/date
        - Perform calculations
        - Store and retrieve notes

        Use tools when appropriate to help the user.""",

        tools=[
            FunctionTool(get_current_time),
            FunctionTool(calculator),
            FunctionTool(store_note),
            FunctionTool(retrieve_notes)
        ],

        description="An assistant with time, calculator, and note-taking capabilities"
    )
    return agent


def main():
    """Run the agent."""
    agent = create_agent()
    runner = Runner(agent)

    print("Agent with tools ready!")
    print("Try asking: 'What time is it?', 'Calculate 15 * 23', 'Save a note'")
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
