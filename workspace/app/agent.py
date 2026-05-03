# MODULE 02-AGENT-ORCHESTRATION: SOLUTION (ADK 2.0 Workflow API)
#
# A linear three-step newsroom pipeline: planner → research → compiler.
#
# Compared to the 1.x version this teaches:
#   - SequentialAgent → Workflow with linear edges
#   - Agent → LlmAgent (renamed in 2.0)
#   - State templating ({search_plan}, {search_results}) → node_input
#     (the predecessor's return value is auto-injected as the LLM's user
#     message). The instruction string is now strictly a system prompt.

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


class SearchPlan(BaseModel):
    queries: list[str] = Field(
        description="2-3 very specific Google Search queries to research."
    )


def get_current_server_time() -> str:
    now = datetime.datetime.now().astimezone()
    return f"The current server time is {now.strftime('%Y-%m-%d %H:%M:%S %Z (UTC%z)')}"


# --- Pipeline nodes ---

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


# --- Top-level Workflow (replaces SequentialAgent + root_agent topology) ---
# Edges define the strict left-to-right pipeline. Each node's return value is
# automatically forwarded as the next node's `node_input`, so we no longer
# need {state_var} interpolation in the instruction strings.

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
