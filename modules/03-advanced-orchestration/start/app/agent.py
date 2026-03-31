# MODULE 03-ADVANCED-ORCHESTRATION: START

import datetime
import os
import google.auth
from pydantic import BaseModel, Field

from google.adk.agents import Agent, SequentialAgent
from google.adk.apps import App
from google.adk.tools import AgentTool
from google.adk.tools import google_search


worker_model = "gemini-3-flash-preview"
pro_model = "gemini-3.1-pro-preview"
image_generation_model = "gemini-3.1-flash-image-preview"


class SearchPlan(BaseModel):
    queries: list[str] = Field(
        description="A list of 2 to 3 very specific Google Search queries to research."
    )


def get_current_server_time() -> str:
    """Simulates getting the current local server time.

    Returns:
        A string with the current time information.
    """
    now = datetime.datetime.now().astimezone()
    return f"The current server time is {now.strftime('%Y-%m-%d %H:%M:%S %Z (UTC%z)')}"


planner_agent = Agent(
    name="planner_agent",
    model=worker_model,
    instruction=f"""
    The current date and time is: {get_current_server_time()}

    You are a senior news editor. 
    Given a broad news topic from the user, generate a structured plan of specific Google Search queries.
    Ensure you instruct the searches to strictly focus on recent developments from the past 3 days.
    """,
    output_schema=SearchPlan,
    output_key="search_plan",
)

research_agent = Agent(
    name="research_agent",
    model=worker_model,
    instruction=f"""
    The current date and time is: {get_current_server_time()}

    You are a news researcher. 
    Look at the `{{search_plan}}` provided in the state. 
    Execute Google Searches for each query listed. Return a rough compilation of all the facts you find.
    """,
    tools=[google_search],
    output_key="search_results",
)

compiler_agent = Agent(
    name="compiler_agent",
    model=pro_model,
    instruction=f"""
    The current date and time is: {get_current_server_time()}

    You are the news editor-in-chief. 
    Read the raw research provided in `{{search_results}}` via the state. 
    Synthesize it into a cohesive, engaging final newspaper.
    """,
    output_key="compiled_news",
)

news_pipeline = SequentialAgent(
    name="news_pipeline",
    description="A specialized research pipeline that plans queries, executes searches, and compiles a comprehensive newspaper. Use this whenever the user asks for news.",
    sub_agents=[planner_agent, research_agent, compiler_agent],
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
