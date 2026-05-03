# MODULE 03 — Advanced Orchestration: START
#
# In this module you'll evolve the linear pipeline below (your mod02
# solution) into a dynamic-parallel pipeline that spawns N researchers
# based on a planner's topic list, then collects verified citations from
# the underlying Google Search grounding metadata.
#
# Your destination:
#                                  +---> researcher[0]
#                                  |
#       START --> planner_agent ---+---> researcher[1]   --> compiler_agent
#                  (TopicPlan)     |   (asyncio.gather)       (NewspaperPage,
#                                  +---> researcher[…]         output_key
#                                  research_orchestrator       "compiled_news")
#                                  (@node, rerun_on_resume)
#
# What you'll build (follow modules/03-advanced-orchestration/README.md):
#   - Add Pydantic schemas: Citation, ArticleDraft, Article, NewspaperPage,
#     TopicPlan (replaces SearchPlan from mod02)
#   - Replace research_agent with a single shared researcher_agent template
#     (LlmAgent with output_schema=Article, tools=[google_search])
#   - Add a research_orchestrator @node(rerun_on_resume=True) that uses
#     asyncio.gather(ctx.run_node(researcher_agent, …)) to spawn N parallel
#     sub-runs based on the TopicPlan
#   - Pull verified citation URLs from each researcher's session.events
#     slice via utils.citations.extract_citations_from_events
#   - Update compiler_agent: output_schema=NewspaperPage, output_key="compiled_news"
#     (the output_key publishes the result to session state so external
#     consumers can read it — you'll see why this matters in mod04, where
#     the AI Newsroom web app reads from this key)
#
# Key references:
#   * Dynamic parallelism via
#     ctx.run_node + asyncio ........... https://adk.dev/workflows/dynamic/
#   * Data flow between nodes .......... https://adk.dev/workflows/data-handling/
#   * Google Search Grounding (display
#     requirements MUST be honored) .... https://docs.cloud.google.com/vertex-ai/generative-ai/docs/grounding/grounding-with-google-search

import datetime

from google.adk.agents import LlmAgent
from google.adk.apps import App
from google.adk.tools import google_search
from google.adk.workflow import Workflow

from dotenv import load_dotenv, find_dotenv
from pydantic import BaseModel, Field

load_dotenv(find_dotenv())

worker_model = "gemini-3-flash-preview"
pro_model = "gemini-3.1-pro-preview"


# --- Structured Pydantic Schemas ---
# When an LlmAgent has `output_schema` set, ADK forces the model to emit a
# JSON object matching the schema and downstream nodes receive it as a
# `dict`. See the node_input table at https://adk.dev/workflows/data-handling/.

class SearchPlan(BaseModel):
    queries: list[str] = Field(
        description="2-3 very specific Google Search queries to research."
    )


def get_current_server_time() -> str:
    now = datetime.datetime.now().astimezone()
    return f"The current server time is {now.strftime('%Y-%m-%d %H:%M:%S %Z (UTC%z)')}"


# --- Pipeline nodes ---
# Each node's return value is auto-forwarded as the next node's `node_input`.
# That means the research_agent receives the SearchPlan dict as its user
# message, and the compiler receives the research_agent's text output. No
# {state_key} interpolation, no output_key plumbing for intermediate steps.

planner_agent = LlmAgent(
    name="planner_agent",
    model=worker_model,
    instruction=f"""
    The current date and time is: {get_current_server_time()}

    You are a senior news editor. Given a broad news topic from the user,
    generate a structured plan of specific Google Search queries. Focus the
    queries on recent developments from the past 3 days unless the user
    requests otherwise.
    """,
    output_schema=SearchPlan,
)

research_agent = LlmAgent(
    name="research_agent",
    model=worker_model,
    instruction=f"""
    The current date and time is: {get_current_server_time()}

    You are a news researcher. The previous step has produced a SearchPlan
    with a list of queries. Execute a Google Search for each query and
    return a rough compilation of the facts you find.
    """,
    tools=[google_search],
)

compiler_agent = LlmAgent(
    name="compiler_agent",
    model=pro_model,
    instruction=f"""
    The current date and time is: {get_current_server_time()}

    You are the news editor-in-chief. Read the raw research provided as input
    and synthesize it into a cohesive, engaging final newspaper.
    """,
)


# --- Top-level Workflow ---
# Edges define the strict left-to-right pipeline. The terminal node's output
# becomes the workflow's output. No conversational outer LlmAgent — the
# Workflow IS the root, since this is a single-purpose newsroom pipeline.
#
# Note: this module deliberately does NOT set `output_key="compiled_news"`
# on the compiler. Mod02's compiler emits raw text; the webapp's persistence
# guard requires structured output (NewspaperPage with an `articles` array),
# which is introduced in mod03. Students running mod02 in `make run-webapp`
# will see the live event log and a "[system] Agent finished" message at
# the end — that's the intended behavior.

root_agent = Workflow(
    name="news_workflow",
    edges=[
        ("START", planner_agent),
        (planner_agent, research_agent),
        (research_agent, compiler_agent),
    ],
)


app = App(
    root_agent=root_agent,
    name="app",
)
