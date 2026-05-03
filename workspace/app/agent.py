# MODULE 03-ADVANCED-ORCHESTRATION: SOLUTION (ADK 2.0 Workflow API)
#
# Replaces the 1.x SequentialAgent / ParallelAgent / custom BaseAgent pattern with
# the new ADK 2.0 Workflow graph API:
#   - Workflow + edges replace SequentialAgent
#   - asyncio.gather(ctx.run_node(...)) replaces ParallelAgent + ParallelResearcherFactory
#   - Agent → LlmAgent (same class, renamed in 2.0)

import asyncio
import datetime
import os
import google.auth
from pydantic import BaseModel, Field
from typing import Optional

from google.adk.agents import LlmAgent
from google.adk.agents.context import Context
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.tools import google_search
from google.adk.workflow import Workflow, node

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

try:
    project_id = os.environ.get("PROJECT_ID") or ""
    if not project_id:
        _, project_id = google.auth.default()
    os.environ["GOOGLE_CLOUD_PROJECT"] = project_id or ""
    os.environ["GOOGLE_CLOUD_LOCATION"] = os.environ.get("GEMINI_LOCATION") or "global"
    os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"
except Exception as e:
    print(f"Warning: Could not configure Vertex AI Auth natively: {e}")

worker_model = "gemini-3-flash-preview"
pro_model = "gemini-3.1-pro-preview"

# --- Structured Pydantic Schemas ---

class Citation(BaseModel):
    title: str = Field(description="Title of the source")
    url: str = Field(description="URL of the source")


class ArticleDraft(BaseModel):
    title: str = Field(description="Catchy headline")
    teaser: str = Field(description="Short engaging teaser in markdown format")
    content: str = Field(description="Full article content in markdown format")


class Article(ArticleDraft):
    citations: list[Citation] = Field(default_factory=list, description="Sources used")
    search_entry_point_html: Optional[str] = Field(
        default=None, description="Google Search Suggestion chip HTML"
    )


class NewspaperPage(BaseModel):
    articles: list[Article] = Field(description="Collection of front-page articles")


class TopicPlan(BaseModel):
    topics: list[str] = Field(description="Specific beats to investigate")


def get_current_server_time() -> str:
    now = datetime.datetime.now().astimezone()
    return f"The current server time is {now.strftime('%Y-%m-%d %H:%M:%S %Z (UTC%z)')}"


# --- Citation extraction callback ---
# Preserves the deterministic-grounding-URL pattern from 1.x: walks session events
# in reverse for this agent's grounding_metadata and overwrites any hallucinated
# Citation URLs with the verified ones from Google Search.

async def extract_citations_callback(callback_context: CallbackContext) -> None:
    session = callback_context._invocation_context.session
    citations = []
    seen_urls = set()
    rendered_content = None
    agent_name = callback_context.agent_name

    for event in reversed(session.events):
        if event.author != agent_name:
            continue
        grounding = getattr(event, "grounding_metadata", None)
        chunks = getattr(grounding, "grounding_chunks", None) if grounding else None
        if not chunks:
            continue

        for chunk in chunks:
            web = getattr(chunk, "web", None)
            uri = getattr(web, "uri", None) if web else None
            if uri and uri not in seen_urls:
                seen_urls.add(uri)
                citations.append({
                    "title": getattr(web, "title", "No Title"),
                    "url": uri,
                })
        search_entry_point = getattr(grounding, "search_entry_point", None)
        if search_entry_point:
            rendered_content = getattr(search_entry_point, "rendered_content", None)
        break

    print(f"[DEBUG] {agent_name} got {len(citations)} citations from grounding chunks")

    # Try to mutate the agent's structured output in place
    output = getattr(callback_context, "output", None)
    if output is not None:
        if hasattr(output, "citations"):
            output.citations = [Citation(**c) for c in citations]
            if rendered_content:
                output.search_entry_point_html = rendered_content
        elif isinstance(output, dict):
            output["citations"] = citations
            if rendered_content:
                output["search_entry_point_html"] = rendered_content


# --- Agents (LlmAgent nodes in the workflow) ---

planner_agent = LlmAgent(
    name="planner_agent",
    model=worker_model,
    instruction=f"""
    The current date and time is: {get_current_server_time()}

    You are a senior news editor. Given a broad news request from the user,
    generate a structured plan of at least 3 specific topics or "beats" to
    assign to your research team. Unless the user requests otherwise, focus
    on recent developments from the past 3 days. Use Google Search to discover
    the most important beats first.
    """,
    tools=[google_search],
    output_schema=TopicPlan,
)


researcher_agent = LlmAgent(
    name="researcher",
    model=worker_model,
    instruction=f"""
    The current date and time is: {get_current_server_time()}

    You are an expert investigative journalist. Research the following beat
    thoroughly. Draft a high-quality, engaging article with a catchy headline,
    a short engaging teaser, and the full content body. Output in Markdown
    format. Use Google Search to gather factual information.
    """,
    tools=[google_search],
    output_schema=Article,
    after_agent_callback=extract_citations_callback,
)


# Replaces the 1.x ParallelResearcherFactory custom BaseAgent. The graph API
# lets us spawn N parallel sub-runs natively via ctx.run_node + asyncio.gather.
@node(rerun_on_resume=True)
async def research_orchestrator(ctx: Context, node_input: dict) -> list:
    topics = node_input.get("topics", []) if isinstance(node_input, dict) else []
    print(f"[DEBUG] research_orchestrator: spawning {len(topics)} researchers")

    tasks = [
        ctx.run_node(researcher_agent, node_input=topic)
        for topic in topics
    ]
    results = await asyncio.gather(*tasks)
    return results


compiler_agent = LlmAgent(
    name="compiler_agent",
    model=pro_model,
    instruction=f"""
    The current date and time is: {get_current_server_time()}

    You are the news editor-in-chief. The previous step provided drafted
    articles from your reporters, each with their true citations.

    Read the drafts. Choose the best ones, drop or merge duplicates, evaluate
    them for quality, and compile them into a cohesive final NewspaperPage.

    CRITICAL: You must strictly preserve each article's exact `citations`
    array and `search_entry_point_html` value. If an article's `citations`
    array is empty `[]`, output an empty array. DO NOT invent, hallucinate,
    edit, or modify any URLs or HTML.
    """,
    output_schema=NewspaperPage,
)


# --- Top-level Workflow (replaces SequentialAgent + root_agent topology) ---

root_agent = Workflow(
    name="news_workflow",
    edges=[
        ("START", planner_agent),
        (planner_agent, research_orchestrator),
        (research_orchestrator, compiler_agent),
    ],
)


app = App(
    root_agent=root_agent,
    name="app",
)
