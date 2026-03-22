import asyncio
import json
import os
import google.auth
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools import google_search
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

_, project_id = google.auth.default()
os.environ["GOOGLE_CLOUD_PROJECT"] = project_id
os.environ["GOOGLE_CLOUD_LOCATION"] = "global"

async def introspective_callback(callback_context: CallbackContext) -> None:
    session = callback_context._invocation_context.session
    print("\n" + "=" * 80)
    print("🔍 CALLBACK INTROSPECTION:")
    
    latest_event = None
    for event in reversed(session.events):
        if event.author == "research_bot" and hasattr(event, "grounding_metadata") and event.grounding_metadata:
            latest_event = event
            break
            
    if not latest_event:
        print("No grounding event from 'research_bot' found.")
        return

    print("\n1. Event Grounding Metadata Structure:")
    chunks = getattr(latest_event.grounding_metadata, "grounding_chunks", [])
    print(f"  Found {len(chunks)} grounding chunks.")
    for i, chunk in enumerate(chunks[:5]): # Print first 5
        if hasattr(chunk, "web") and chunk.web:
            print(f"  Chunk {i} [WEB]: title='{getattr(chunk.web, 'title', '')}', uri='{getattr(chunk.web, 'uri', '')}'")
        elif hasattr(chunk, "retrieved_context") and chunk.retrieved_context:
            print(f"  Chunk {i} [CONTEXT]: {getattr(chunk.retrieved_context, 'title', '')}")
        else:
            print(f"  Chunk {i} [OTHER]: {chunk}")
    if len(chunks) > 5:
        print(f"  ... and {len(chunks)-5} more chunks.")
        
    print("=" * 80 + "\n")

research_agent = Agent(
    name="research_bot",
    model="gemini-3-flash-preview",
    instruction="Research the query using google_search. Do not include URLs or citations in your text output.",
    tools=[google_search],
    output_key="research_output",
    after_agent_callback=introspective_callback,
)

async def main():
    print("Starting ADK introspective runner...")
    session_service = InMemorySessionService()
    runner = Runner(app_name="test_app", agent=research_agent, session_service=session_service)
    
    await session_service.create_session(app_name="test_app", user_id="test_user", session_id="test_session")
    user_message = types.Content(role="user", parts=[types.Part(text="What is the latest news regarding Google ADK Agent Development Kit?")])
    
    async for event in runner.run_async(user_id="test_user", session_id="test_session", new_message=user_message):
        if hasattr(event, "content") and event.content:
            for part in getattr(event.content, "parts", []):
                if getattr(part, "function_call", None):
                    print(f"[Model -> Tool]: Call {part.function_call.name}")
                if getattr(part, "text", None):
                    print(f"[Model -> User]: {part.text}")

if __name__ == "__main__":
    asyncio.run(main())
