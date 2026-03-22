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

_, project_id = google.auth.default()
os.environ["GOOGLE_CLOUD_PROJECT"] = project_id
os.environ["GOOGLE_CLOUD_LOCATION"] = "global"
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"

worker_model = "gemini-3-flash-preview"
pro_model = "gemini-3.1-pro-preview"
image_generation_model = "gemini-3.1-flash-image-preview"

# --- Structured Pydantic Schemas ---


class Citation(BaseModel):
    title: str = Field(description="Title of the source")
    url: str = Field(description="URL of the source")


class SearchResult(BaseModel):
    content: str = Field(description="The factual content found")


class Article(BaseModel):
    title: str = Field(description="Catchy headline")
    teaser: str = Field(description="Short engaging teaser")
    content: str = Field(description="Full article content")
    citations: list[Citation] = Field(description="Sources used in this article")


class NewspaperPage(BaseModel):
    articles: list[Article] = Field(
        description="Collection of articles for the front page"
    )


class SearchPlan(BaseModel):
    queries: list[str] = Field(
        description="A list of at least 5 very specific Google Search queries to research."
    )


def get_current_server_time() -> str:
    now = datetime.datetime.now().astimezone()
    return f"The current server time is {now.strftime('%Y-%m-%d %H:%M:%S %Z (UTC%z)')}"


# --- Native Grounding Callbacks ---


def make_citations_callback(agent_name: str, output_key: str):
    async def extract_citations_callback(callback_context: CallbackContext) -> None:
        """
        Extracts citations from the LLM's grounding metadata.
        
        The ADK Event object stores the raw Gemini API response. When a tool like 
        `google_search` is used natively by Vertex AI, the model attaches a 
        `grounding_metadata` object to the event. 
        
        Inside `grounding_metadata.grounding_chunks`, there are web chunk objects 
        with `.web.title` and `.web.uri` properties containing the exact 
        sources the model used to generate its factual response.
        """
        session = callback_context._invocation_context.session
        citations = []
        seen_urls = set()

        # Traverse events in reverse to find the latest grounding chunks for this agent
        for event in reversed(session.events):
            if (
                event.author == agent_name
                and getattr(event, "grounding_metadata", None)
                and getattr(event.grounding_metadata, "grounding_chunks", None)
            ):
                for chunk in event.grounding_metadata.grounding_chunks:
                    if getattr(chunk, "web", None) and chunk.web.uri not in seen_urls:
                        seen_urls.add(chunk.web.uri)
                        citations.append({"title": getattr(chunk.web, "title", "No Title"), "url": chunk.web.uri})
                break  # Only process the final response

        # Inject the deterministic citations into the structured state!
        if (
            output_key
            and output_key in callback_context.state
            and isinstance(callback_context.state[output_key], dict)
        ):
            callback_context.state[output_key]["citations"] = citations

    return extract_citations_callback


# --- Agents & Workflows ---

planner_agent = Agent(
    name="planner_agent",
    model=worker_model,
    instruction=f"""
    The current date and time is: {get_current_server_time()}

    You are a senior news editor. 
    Given a broad news topic from the user, generate a structured plan of at least 5 very specific Google Search queries to run in parallel.
    Ensure you instruct the searches to strictly focus on recent developments from the past 3 days.
    Use `google_search` to inform your 
    """,
    tools=[google_search],
    output_schema=SearchPlan,
    output_key="search_plan",
)


def create_research_agent(topic: str, index: int) -> Agent:
    agent_name = f"researcher_{index}"
    out_key = f"search_result_{index}"
    return Agent(
        name=agent_name,
        model=worker_model,
        instruction=f"""
        The current date and time is: {get_current_server_time()}
        
        Research the following topic: {topic}. 
        Return highly detailed factual content from your tools. Do not include URLs or citations in your text output.
        """,
        tools=[google_search],
        output_schema=SearchResult,
        output_key=out_key,
        after_agent_callback=make_citations_callback(agent_name, out_key),
    )


class ParallelResearcherFactory(BaseAgent):
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        plan = ctx.session.state.get("search_plan")
        if not plan or not plan.get("queries"):
            return

        researchers = [
            create_research_agent(query, i) for i, query in enumerate(plan["queries"])
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
    The results from the parallel research team are available in the state under keys starting with 'search_result_'.
    Read all of these results. They contain deterministic arrays of "citations" as well as "content".
    Synthesize them into a cohesive, engaging final newspaper. Preserve the exact URLs provided in the state arrays.
    """,
    output_schema=NewspaperPage,
    output_key="compiled_news",
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
        print(
            "Executing ADK pipeline... (this may take up to 60 seconds for parallel searches)"
        )

        # 6. Execute the runner
        async for event in runner.run_async(
            user_id=user_id, session_id=session_id, new_message=user_message
        ):
            if (
                hasattr(event, "content")
                and event.content
                and isinstance(event.content, types.Content)
            ):
                for part in event.content.parts:
                    if part.text:
                        print(f"[{event.author}]: {part.text}")

        # 7. Retrieve the populated state AFTER execution completes
        current_session = await session_service.get_session(
            app_name=app_name, user_id=user_id, session_id=session_id
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
