# MODULE 04-VECTOR-SEARCH: SOLUTION (ADK 2.0 Workflow API)
#
# Builds on mod03's news pipeline by adding a vector-search archive branch.
# Demonstrates two new ADK 2.0 patterns:
#   1. Conditional routing — a router @node emits Event(route="news"|"archive")
#      and workflow edges with a third element pick the branch.
#   2. Two terminal nodes — whichever terminal runs, its output becomes the
#      workflow's output. No SequentialAgent/sub_agents juggling needed.
#
# Routing is rule-based (keyword match) for clarity. An LLM-driven router is
# a one-line swap: replace the @node with an LlmAgent(output_schema=Route)
# followed by a tiny @node that converts Route.value → Event(route=...).

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
from google.adk.events.event import Event
from google.adk.tools import google_search
from google.adk.workflow import Workflow, node

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

# Repo-level utils/ on sys.path — citations + vector_store live there.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from utils.citations import extract_citations_from_events  # noqa: E402
from utils.vector_store import search_archive  # noqa: E402

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


# --- Tool: archive search (delegates to utils.vector_store) ---

def search_news_archive(query: str, top_k: int = 5) -> list[dict]:
    """Search the Vector Search archive for past articles relevant to a query."""
    results = search_archive(query, top_k)
    if not results:
        return [{"status": "success", "results": "No archived articles found."}]
    return results


# --- Router: decide news vs archive ---

ARCHIVE_KEYWORDS = ("archive", "past", "historical", "previously", "earlier",
                    "old", "from yesterday", "last week")


def _user_text(node_input) -> str:
    """Pull plain text out of START's types.Content payload."""
    parts = getattr(node_input, "parts", None)
    if parts:
        return " ".join(p.text for p in parts if getattr(p, "text", None))
    return str(node_input)


@node
def router(node_input):
    text = _user_text(node_input).lower()
    if any(k in text for k in ARCHIVE_KEYWORDS):
        print(f"[DEBUG] router: → archive (matched keyword in '{text[:80]}')")
        return Event(output=node_input, route="archive")
    print(f"[DEBUG] router: → news ('{text[:80]}')")
    return Event(output=node_input, route="news")


# --- News-path agents (mod03-style) ---

planner_agent = LlmAgent(
    name="planner_agent",
    model=worker_model,
    instruction=f"""
    The current date and time is: {get_current_server_time()}

    You are a senior news editor. Given a broad news request from the user,
    generate a structured plan of at least 3 specific topics or "beats" to
    assign to your research team. Focus on recent developments from the past
    3 days unless the user requests otherwise. Use Google Search to discover
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
)


# --- Archive-path agent ---

archive_reader_agent = LlmAgent(
    name="archive_reader_agent",
    model=pro_model,
    instruction=f"""
    The current date and time is: {get_current_server_time()}

    You are an archival librarian answering questions using past editions of
    the newspaper. Always search the archive first using `search_news_archive`.

    Construct your output as a NewspaperPage with multiple Article objects:
    each article has a title, an engaging teaser, and the full content body
    formatted in Markdown. Strictly preserve and populate the original
    `citations` array from your search results into the final schema.
    """,
    tools=[search_news_archive],
    output_schema=NewspaperPage,
)


# --- Top-level Workflow with conditional routing ---

root_agent = Workflow(
    name="news_workflow",
    edges=[
        ("START", router),
        # Conditional routing — RoutingMap dict picks the branch by route value
        # emitted from the router (Event(route="news") or Event(route="archive")).
        (router, {"news": planner_agent, "archive": archive_reader_agent}),
        (planner_agent, research_orchestrator),
        (research_orchestrator, compiler_agent),
    ],
)


app = App(
    root_agent=root_agent,
    name="app",
)
