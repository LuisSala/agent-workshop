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
import sys
import google.auth
from pydantic import BaseModel, Field
from typing import Optional

from google.adk.agents import LlmAgent
from google.adk.agents.context import Context
from google.adk.apps import App
from google.adk.tools import google_search
from google.adk.workflow import Workflow, node

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

# Make the repo-level utils/ importable (matches the pattern used by mod04 for
# vector_store.py — keeps non-pipeline plumbing out of the agent file).
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from utils.citations import extract_citations_from_events  # noqa: E402

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


# --- Agents (LlmAgent nodes in the workflow) ---
# The citation-extraction helper lives in utils/citations.py — see that file
# for notes on why per-researcher attribution is approximate under parallel
# ctx.run_node execution and how the orchestrator works around it.

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
)


# Replaces the 1.x ParallelResearcherFactory custom BaseAgent. The graph API
# lets us spawn N parallel sub-runs natively via ctx.run_node + asyncio.gather.
@node(rerun_on_resume=True)
async def research_orchestrator(ctx: Context, node_input: dict) -> list:
    topics = node_input.get("topics", []) if isinstance(node_input, dict) else []
    print(f"[DEBUG] research_orchestrator: spawning {len(topics)} researchers")

    async def research_one(topic: str, idx: int) -> dict:
        start = len(ctx.session.events)
        article = await ctx.run_node(researcher_agent, node_input=topic)
        end = len(ctx.session.events)
        citations, rendered = extract_citations_from_events(
            ctx.session.events[start:end]
        )
        print(
            f"[DEBUG] researcher[{idx}] '{topic[:60]}': "
            f"{len(citations)} citations from events {start}..{end}"
        )
        if isinstance(article, dict):
            article["citations"] = citations
            if rendered:
                article["search_entry_point_html"] = rendered
        return article

    tasks = [research_one(t, i) for i, t in enumerate(topics)]
    return await asyncio.gather(*tasks)


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
    # Persist the compiled NewspaperPage to session.state['compiled_news'].
    # webapp/app.py reads this after the run to write the persistent newsletter
    # JSON and emit the SSE 'finish' payload that triggers the front-end's
    # transition from the diagnostic event log to the rendered article grid.
    output_key="compiled_news",
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
