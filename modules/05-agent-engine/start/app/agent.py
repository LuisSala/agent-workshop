# MODULE 04 — Vector Search & Structured UI Integration (ADK 2.0 Workflow API)
#
# A multi-purpose AI Newsroom defined as TWO independent Workflows:
#
#   news_workflow:
#       START --> planner_agent --> research_orchestrator --> compiler_agent
#                  (LlmAgent)        (@node, fan-out)          (NewspaperPage)
#
#   archive_workflow:
#       START --> archive_reader_agent
#                  (LlmAgent + search_news_archive tool, NewspaperPage)
#
# The webapp at webapp/app.py picks which workflow to run based on the
# UI button the user clicked (a `?mode=news|archive` query param).
# The agent layer no longer re-derives intent from the prompt.
#
# Why two workflows instead of one with a router @node? The user's intent
# is already known at the UI layer (which button was clicked). Asking the
# agent to re-derive it via keyword matching is brittle ("show me past
# articles" vs "show me articles about the past" — the rule-based router
# can't tell them apart). App-level routing is cleaner.
#
# If you want IN-AGENT conditional routing (a single Workflow with a
# router @node and a `RoutingMap` dict edge), the canonical pattern is
# at https://adk.dev/workflows/graph-routes/ — see this module's README
# → "Alternative: agent-level routing" for the trade-offs.
#
# Patterns demonstrated and where to read about them:
#   * Workflow overview ............... https://adk.dev/workflows/
#   * Dynamic parallelism via run_node  https://adk.dev/workflows/dynamic/
#   * LlmAgent + tools + output_schema  https://adk.dev/2.0/
#   * Vertex AI Vector Search           https://docs.cloud.google.com/vertex-ai/vector-search/overview
#   * Google Search Grounding (display
#     requirements MUST be honored) ... https://docs.cloud.google.com/vertex-ai/generative-ai/docs/grounding/grounding-with-google-search
#
# Stability note: ADK 2.0 is Beta. Breaking API changes are possible until GA;
# this file pins the patterns as observed against google-adk == 2.0.0b1.

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

# Repo-level utils/ on sys.path so the agent can import shared helpers.
# Both citation extraction and the Vector Search wrapper live there to keep
# this file focused on the pipeline structure rather than the plumbing.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from utils.citations import extract_citations_from_events  # noqa: E402
from utils.vector_store import search_archive  # noqa: E402

# Vertex AI auth bootstrap — pulls PROJECT_ID from the root .env and falls
# back to gcloud ADC if the env var is unset. GEMINI_LOCATION lets us point
# the LLM at a regional or global routing endpoint (use "global" if you see
# a 404 on the model name).
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


# ----------------------------------------------------------------------------
# Pydantic schemas
# ----------------------------------------------------------------------------
# These drive ADK's structured output: when an LlmAgent has `output_schema`
# set, the framework forces the model to emit a JSON object matching the
# schema and downstream nodes receive it as a `dict`. See the node_input
# table at https://adk.dev/workflows/data-handling/.

class Citation(BaseModel):
    title: str = Field(description="Title of the source")
    url: str = Field(description="URL of the source")


class ArticleDraft(BaseModel):
    title: str = Field(description="Catchy headline")
    teaser: str = Field(description="Short engaging teaser in markdown format")
    content: str = Field(description="Full article content in markdown format")


class Article(ArticleDraft):
    citations: list[Citation] = Field(default_factory=list, description="Sources used")
    # The Google Search Suggestion chip HTML — REQUIRED to be displayed
    # alongside any grounded response. See the display requirements at
    # https://docs.cloud.google.com/vertex-ai/generative-ai/docs/grounding/grounding-with-google-search
    search_entry_point_html: Optional[str] = Field(
        default=None, description="Google Search Suggestion chip HTML (must be rendered alongside the article)"
    )


class NewspaperPage(BaseModel):
    articles: list[Article] = Field(description="Collection of front-page articles")


class TopicPlan(BaseModel):
    topics: list[str] = Field(description="Specific beats to investigate")


def get_current_server_time() -> str:
    now = datetime.datetime.now().astimezone()
    return f"The current server time is {now.strftime('%Y-%m-%d %H:%M:%S %Z (UTC%z)')}"


# ----------------------------------------------------------------------------
# Tool: archive search (delegates to utils.vector_store)
# ----------------------------------------------------------------------------
# Wrapping `search_archive` rather than passing it directly means students
# can adjust the empty-result UX (returning a status payload instead of
# `None`) without touching utils/vector_store.py.

def search_news_archive(query: str, top_k: int = 5) -> list[dict]:
    """Search the Vector Search archive for past articles relevant to a query."""
    results = search_archive(query, top_k)
    if not results:
        return [{"status": "success", "results": "No archived articles found."}]
    return results


# ----------------------------------------------------------------------------
# News pipeline (mod03-style): planner → orchestrator → compiler
# ----------------------------------------------------------------------------

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


# A single, shared researcher template. The orchestrator below spawns N
# parallel sub-runs of this same agent — one per topic — via ctx.run_node.
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


# Replaces the 1.x ParallelResearcherFactory(BaseAgent) hand-rolled fan-out
# with the canonical dynamic-parallelism pattern from
# https://adk.dev/workflows/dynamic/ : `asyncio.gather(*[ctx.run_node(...)])`.
#
# Why `rerun_on_resume=True` is required: parent nodes that call ctx.run_node
# must opt into rerun-on-resume so that an interrupted workflow can re-launch
# the parallel children without losing state.
#
# Citation attribution caveat: every parallel ctx.run_node call shares one
# `session.events` stream, and Python asyncio runs each coroutine up to its
# first `await` synchronously — so all `research_one` tasks capture the
# same `start` index. As tasks complete, each captures `end` at its own
# moment, but the slice [start:end] picks up grounding chunks emitted by
# *peers* that happened to finish earlier. The resulting per-article
# citation list is a SUPERSET of that researcher's real grounding chunks.
# For workshop purposes this is acceptable; see utils/citations.py for the
# long-form discussion plus the cleaner alternative.
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
                # Required for Google Search Grounding TOS compliance.
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
    edit, or modify any URLs or HTML. The search_entry_point_html is
    required by Google's grounding terms — dropping it breaks compliance.
    """,
    output_schema=NewspaperPage,
    # output_key publishes the compiled result to session.state['compiled_news'].
    # The AI Newsroom web app reads this from outside the workflow to render
    # the article grid — see this module's README → "Embedding a Runner" for
    # the full integration walk-through.
    output_key="compiled_news",
)


# ----------------------------------------------------------------------------
# Archive-path agent (single-step "workflow")
# ----------------------------------------------------------------------------
# A single LlmAgent equipped with the Vector Search tool and forced to emit
# a NewspaperPage.

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
    # Same contract as compiler_agent — see that comment above.
    output_key="compiled_news",
)


# ----------------------------------------------------------------------------
# Top-level Workflows
# ----------------------------------------------------------------------------
# Two independent graphs. webapp/app.py imports both and picks one per
# request based on the UI button the user clicked (the `?mode=` query
# param). ADK Web (`make playground`) only sees `root_agent`, so we alias
# it to news_workflow for development convenience — to test the archive
# flow during development, drive it via the AI Newsroom web app or write
# a small script that imports `archive_workflow` directly.

news_workflow = Workflow(
    name="news_workflow",
    edges=[
        ("START", planner_agent),
        (planner_agent, research_orchestrator),
        (research_orchestrator, compiler_agent),
    ],
)

archive_workflow = Workflow(
    name="archive_workflow",
    edges=[
        ("START", archive_reader_agent),
    ],
)

# ADK Web's developmental default. The webapp ignores this and selects
# from {news_workflow, archive_workflow} explicitly per request.
root_agent = news_workflow


app = App(
    root_agent=root_agent,
    name="app",
)
