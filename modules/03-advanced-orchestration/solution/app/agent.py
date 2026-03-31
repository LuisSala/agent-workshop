# MODULE 04-VECTOR-SEARCH: START

import asyncio
import datetime
import json
import os
import google.auth
from pydantic import BaseModel, Field

from google.adk.agents import Agent, SequentialAgent, BaseAgent, ParallelAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.agents.callback_context import CallbackContext
from google.adk.events import Event
from google.adk.apps import App
from google.adk.tools import AgentTool
from google.adk.tools import google_search
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from typing import AsyncGenerator


worker_model = "gemini-3-flash-preview"
pro_model = "gemini-3.1-pro-preview"
image_generation_model = "gemini-3.1-flash-image-preview"

generate_content_config = types.GenerateContentConfig(
    tool_config=types.ToolConfig(function_calling_config=types.FunctionCallingConfig())
)

# --- Structured Pydantic Schemas ---


class Citation(BaseModel):
    title: str = Field(description="Title of the source")
    url: str = Field(description="URL of the source")


class SearchResult(BaseModel):
    content: str = Field(description="The factual content found")


class ArticleDraft(BaseModel):
    title: str = Field(description="Catchy headline")
    teaser: str = Field(description="Short engaging teaser in markdown format")
    content: str = Field(description="Full article content in markdown format")


class Article(ArticleDraft):
    citations: list[Citation] = Field(description="Sources used in this article")


class NewspaperPage(BaseModel):
    articles: list[Article] = Field(
        description="Collection of articles for the front page"
    )


class TopicPlan(BaseModel):
    topics: list[str] = Field(
        description="A list of specific beats or topics to investigate."
    )


def get_current_server_time() -> str:
    now = datetime.datetime.now().astimezone()
    return f"The current server time is {now.strftime('%Y-%m-%d %H:%M:%S %Z (UTC%z)')}"


# --- Native Grounding Callbacks ---


def make_citations_callback(agent_name: str, output_key: str):
    async def extract_citations_callback(callback_context: CallbackContext) -> None:
        """
        Extracts citations from the LLM's grounding metadata.

        THE PROBLEM: LLMs are notoriously bad at generating accurate URLs. If you ask
        an LLM to output a `Citation` Pydantic object, it will likely invent a fake URL
        that looks plausible but returns a 404 error.

        THE SOLUTION: When using Vertex AI Search via ADK's `google_search` tool, the
        underlying Vertex API attaches highly accurate, deterministic `grounding_metadata`
        to the ADK Event stream.

        This `after_agent_callback` runs immediately after the LLM finishes drafting the
        article. It traverses the Event stream, finds the true URLs supplied by Google
        Search, and forcefully overwrites the LLM's hallucinated citations in the
        structured Pydantic state with the verified URLs.
        """
        session = callback_context._invocation_context.session
        citations = []
        seen_urls = set()

        # Traverse events in reverse to find the latest grounding chunks for this agent
        for event in reversed(session.events):
            if not getattr(event, "grounding_metadata", None):
                continue
            if not getattr(event.grounding_metadata, "grounding_chunks", None):
                continue
            if event.author != agent_name:
                continue

            for chunk in event.grounding_metadata.grounding_chunks:
                if getattr(chunk, "web", None) and chunk.web.uri not in seen_urls:
                    seen_urls.add(chunk.web.uri)
                    citations.append(
                        {
                            "title": getattr(chunk.web, "title", "No Title"),
                            "url": chunk.web.uri,
                        }
                    )
            break  # Only process the final response

        # Inject the deterministic citations into the structured state!
        print(
            f"[DEBUG] {agent_name} generated {len(citations)} citations from grounding chunks."
        )
        if output_key and output_key in callback_context.state:
            state_val = callback_context.state[output_key]
            # Replace hallucinated citations with the true grounding URLs
            if hasattr(state_val, "citations"):
                state_val.citations = [Citation(**c) for c in citations]
                print(
                    f"[DEBUG] Pydantic citations overridden to array of length {len(state_val.citations)}"
                )
            elif isinstance(state_val, dict):
                state_val["citations"] = citations
                print(
                    f"[DEBUG] Dict citations overridden to array of length {len(state_val['citations'])}"
                )
            elif isinstance(state_val, str):
                # Store citations explicitly as strongly typed dictionaries in a parallel state key
                # We use .model_dump() to ensure JSON serializability for SqliteSessionService
                citations_key = f"{output_key}_citations"
                callback_context.state[citations_key] = [Citation(**c).model_dump() for c in citations]
                print(f"[DEBUG] Stored {len(citations)} dictionary citations in parallel state key: {citations_key}")

    return extract_citations_callback


async def prepare_drafts_callback(callback_context: CallbackContext) -> None:
    articles_data = []
    for i in range(100):
        key = f"article_{i}"
        val = callback_context.state.get(key)
        
        if val is not None:
            # Retrieve the parallel strongly-typed citation dicts
            citations_dict = callback_context.state.get(f"{key}_citations", [])
            
            articles_data.append({
                "content": val,
                "citations": citations_dict
            })
    import json

    serialized = []
    for art in articles_data:
        # art is now a dictionary containing "content" (str) and "citations" (List[dict])
        serialized.append(art)
        
    callback_context.state["draft_articles"] = json.dumps(serialized, indent=2)


# --- Agents & Workflows ---

planner_agent = Agent(
    name="planner_agent",
    model=worker_model,
    instruction=f"""
    The current date and time is: {get_current_server_time()}

    You are a senior news editor. 
    Given a broad news request from the user, generate a structured plan of at least 3 specific topics or "beats" to assign to your research team.
    Unless the user requests otherwise, ensure the topics strictly focus on recent developments from the past 3 days.
    Use Google Search to execute a first pass to discover the most important beats.
    
    IMPORTANT: You must output ONLY a raw JSON array of strings containing the topics. Do not include markdown blocks, text, or the `TopicPlan` wrapper.
    Example output exactly like this:
    ["AI advancements in healthcare", "New open source foundation models", "Regulatory changes in EU AI Act"]
    """,
    tools=[google_search],
    output_key="topic_plan",
)


def create_research_agent(topic: str, index: int) -> Agent:
    agent_name = f"researcher_{index}"
    out_key = f"article_{index}"
    return Agent(
        name=agent_name,
        model=worker_model,
        instruction=f"""
        The current date and time is: {get_current_server_time()}
        
        You are an expert investigative journalist. Research the following beat thoroughly: {topic}.
        Draft a high-quality, engaging article about your findings. Ensure your article has a catchy headline, a short engaging teaser, and the full content body.
        Your final output must be in Markdown format. Use Google Search to gather factual information.
        """,
        tools=[google_search],
        output_key=out_key,
        after_agent_callback=make_citations_callback(agent_name, out_key),
    )


class ParallelResearcherFactory(BaseAgent):
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        plan_raw = ctx.session.state.get("topic_plan")
        if not plan_raw:
            return

        import json
        import re
        try:
            # Strip potential markdown formatting
            plan_str = plan_raw.strip().strip("```json").strip("```").strip()
            # Use regex to find the first array structure in case the LLM added conversational filler
            match = re.search(r'\[.*\]', plan_str, flags=re.DOTALL)
            if match:
                plan_str = match.group(0)
            topics = json.loads(plan_str)
        except json.JSONDecodeError:
            print(f"Failed to parse topics from planner output: {plan_raw}")
            return

        researchers = [
            create_research_agent(topic, i) for i, topic in enumerate(topics)
        ]

        parallel_runner = ParallelAgent(
            name="parallel_research_executor", sub_agents=researchers
        )

        async for event in parallel_runner.run_async(ctx):
            yield event


research_team = ParallelResearcherFactory(name="research_team")


compiler_agent = Agent(
    name="compiler_agent",
    model=pro_model,
    instruction=f"""
    The current date and time is: {get_current_server_time()}

    You are the news editor-in-chief. 
    Here are the drafted articles from your reporters, including their true and final citations:
    {{draft_articles}}

    Read all of these drafted articles. Choose the best ones, drop or merge duplicates, evaluate them for quality, and compile them into a cohesive final `NewspaperPage`.

    CRITICAL INSTRUCTION: You must strictly preserve the exact `citations` array provided for each article in the data above. If an article's `citations` array is empty `[]`, you MUST output an empty array for that article. DO NOT invent, hallucinate, or infer any URLs.
    """,
    output_schema=NewspaperPage,
    output_key="compiled_news",
    before_agent_callback=prepare_drafts_callback,
)

news_pipeline = SequentialAgent(
    name="news_pipeline",
    description="A specialized research pipeline that plans queries, executes searches in parallel, and compiles a comprehensive newspaper. Use this whenever the user asks for news.",
    sub_agents=[planner_agent, research_team, compiler_agent],
)

root_agent = Agent(
    name="root_agent",
    model=worker_model,
    instruction="""
    You are a helpful, conversational AI. Delegate to `news_pipeline` sub-agent 
    whenever a user asks you to look up news; otherwise, answer the user's query directly.
    """,
    sub_agents=[news_pipeline],
)

app = App(
    root_agent=root_agent,
    name="app",
)


async def main():
    from dotenv import load_dotenv, find_dotenv
    load_dotenv(find_dotenv())
    
    print("Starting pipeline execution...")
    
    project_id = os.environ.get("PROJECT_ID", "luissala-vertex-sandbox")
    os.environ["GOOGLE_CLOUD_PROJECT"] = project_id
    os.environ["GOOGLE_CLOUD_LOCATION"] = "global"
    os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"

    # 1. Define Unique Identifiers
    session_id = "test_pipeline"
    user_id = "test_user"
    app_name = "test_app"

    # 2. Formulate the initial prompt
    query = "What's the latest news on AI Agents from OpenAI, Google, Anthropic, and any other industry leaders?"

    # 3. Initialize Services
    session_service = InMemorySessionService()
    runner = Runner(
        app_name=app_name, agent=root_agent, session_service=session_service
    )

    try:
        # 4. Create the session explicitly
        await session_service.create_session(
            app_name=app_name, user_id=user_id, session_id=session_id
        )

        # 5. Format the message
        user_message = types.Content(role="user", parts=[types.Part(text=query)])

        print(f"Running query: {query}")
        print("Executing ADK pipeline... (this may take several minutes)")

        # 6. Execute the runner
        async for event in runner.run_async(
            user_id=user_id, session_id=session_id, new_message=user_message
        ):
            if event.is_final_response() and event.content:
                for part in event.content.parts:
                    if part.text:
                        print(f"[{event.author}]: {part.text}")

        print(f"DEBUG Registry: {session_service.sessions}")

        # 7. Retrieve the populated state AFTER execution completes
        current_session = await session_service.get_session(
            app_name=runner.app_name, user_id=user_id, session_id=session_id
        )

        # 8. Extract the compiled newspaper from the final state
        compiled = current_session.state.get("compiled_news", {})

        print("-" * 80)
        print("FINAL COMPILED NEWSPAPER:")
        print(json.dumps(compiled, indent=2))

    except Exception as e:
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
