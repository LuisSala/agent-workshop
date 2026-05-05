# MODULE 04 — Vector Search & Structured UI Integration: START
#
# In this module you'll add an archive branch to the newsroom (your mod03
# solution sits below): a Vector Search-backed librarian that runs when
# the user asks about *past* coverage instead of *fresh* news. The two
# branches are exposed as INDEPENDENT Workflows; the AI Newsroom web app
# (introduced in this module's "Embedding a Runner" section) picks which
# one to invoke per request based on the UI button the user clicked.
#
# Your destination:
#
#   news_workflow (the existing mod03 pipeline, kept as-is):
#       START --> planner_agent --> research_orchestrator --> compiler_agent
#
#   archive_workflow (new):
#       START --> archive_reader_agent
#
# What you'll build (follow modules/04-vector-search/README.md):
#   - A search_news_archive tool that delegates to utils.vector_store.search_archive
#   - An archive_reader_agent (LlmAgent) with tools=[search_news_archive]
#     and output_schema=NewspaperPage and output_key="compiled_news"
#   - A second top-level Workflow (`archive_workflow`) wrapping the
#     archive_reader_agent
#   - root_agent = news_workflow (so ADK Web's `make adk-web` keeps
#     working; the webapp imports both workflows directly)
#
# Why two workflows instead of one Workflow with a router @node? The user's
# intent is already known at the UI layer (which button was clicked).
# Asking the agent to re-derive it via keyword matching is brittle. See
# the README's "Alternative: agent-level routing" section for trade-offs
# and the canonical RoutingMap pattern if you want it.
#
# Key references:
#   * Workflow overview ............... https://adk.dev/workflows/
#   * Vertex AI Vector Search ......... https://docs.cloud.google.com/vertex-ai/vector-search/overview
#   * Conditional routing (alternative) https://adk.dev/workflows/graph-routes/
#   * Google Search Grounding (display
#     requirements MUST be honored) ... https://docs.cloud.google.com/vertex-ai/generative-ai/docs/grounding/grounding-with-google-search

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

# Repo-level utils/ on sys.path — the citation-extraction helper lives there
# so the agent file stays focused on the pipeline structure rather than the
# event-traversal plumbing. (Mod04 follows the same pattern for vector_store.py.)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from utils.citations import extract_citations_from_events  # noqa: E402

# Vertex AI auth bootstrap. PROJECT_ID comes from the root .env; if unset we
# fall back to gcloud ADC. GEMINI_LOCATION lets us pick regional vs. global
# routing — set it to "global" if you ever see a 404 on the model name.
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
    # Required by Google Search Grounding terms — the chip HTML must be
    # displayed alongside the grounded article. See the orchestrator below
    # for where this gets populated and the README for the compliance walk-through.
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


# ----------------------------------------------------------------------------
# Pipeline nodes
# ----------------------------------------------------------------------------
# Each node's return value is auto-forwarded as the next node's `node_input`.
# That means the orchestrator receives the planner's TopicPlan dict, the
# researcher receives a single topic string, and the compiler receives the
# orchestrator's list of Article dicts. No {state_key} interpolation in the
# instructions — they're pure system prompts.

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


# A single, shared researcher template. The orchestrator below spawns N
# parallel sub-runs of this same agent — one per topic — via ctx.run_node.
# Each sub-run gets its own LLM context but writes events into the parent
# workflow's session.events stream (see the orchestrator note below).
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


# Replaces the 1.x ParallelResearcherFactory(BaseAgent) hand-rolled fan-out.
# The canonical dynamic-parallelism pattern from
# https://adk.dev/workflows/dynamic/ is `asyncio.gather(*[ctx.run_node(...)])`.
#
# Why `rerun_on_resume=True` is required: parent nodes that call ctx.run_node
# must opt into rerun-on-resume so an interrupted workflow can re-launch the
# parallel children without losing state.
#
# Citation attribution caveat: every parallel ctx.run_node call shares one
# `session.events` stream, and Python asyncio runs each coroutine up to its
# first `await` synchronously — so all `research_one` tasks capture the
# same `start` index. As tasks complete, each captures `end` at its own
# moment, but the slice [start:end] picks up grounding chunks emitted by
# *peers* that happened to finish earlier. The resulting per-article
# citation list is a SUPERSET of that researcher's real grounding chunks.
# For workshop purposes this is acceptable — see utils/citations.py and
# the README for the long-form discussion plus the cleaner alternative.
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
    # Persist the compiled NewspaperPage to session.state['compiled_news'] so
    # downstream consumers can pick it up after the workflow finishes. The
    # AI Newsroom web app introduced in mod04 (see modules/04-vector-search/README.md
    # → "Embedding a Runner") is the consumer this hook is here for; for
    # mod03 it just demonstrates the session-state contract.
    output_key="compiled_news",
)


# ----------------------------------------------------------------------------
# Top-level Workflow
# ----------------------------------------------------------------------------
# Edges define the strict left-to-right pipeline. The terminal node's output
# (compiler_agent's NewspaperPage) becomes the workflow's final output. No
# conversational outer LlmAgent — the Workflow IS the root, since this is
# a single-purpose newsroom pipeline.

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
