# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# MODULE 01-FOUNDATION: SOLUTION & START OF MODULE 02-AGENT-ORCHESTRATION

import datetime
from zoneinfo import ZoneInfo

from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.genai import types

import os
import random


def get_weather(city: str) -> str:
    """Simulates getting the current weather conditions for a given city.

    Args:
        city: The city to get the weather conditions for.

    Returns:
        A string with the simulated weather conditions for the queried city.
    """
    temperature = random.randint(-10, 40)
    conditions = random.choice(["sunny", "cloudy", "rainy", "windy", "snowy"])
    return f"The weather in {city} is {temperature} degrees Celsius and {conditions}."


def get_current_server_time() -> str:
    """Simulates getting the current local server time.

    Returns:
        A string with the current time information.
    """

    now = datetime.datetime.now().astimezone()
    return f"The current server time is {now.strftime('%Y-%m-%d %H:%M:%S %Z (UTC%z)')}"


root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model="gemini-3.7-flash",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction="You are a helpful AI assistant designed to provide accurate and useful information.",
    tools=[get_current_server_time, get_weather],
)

app = App(
    root_agent=root_agent,
    name="app",
)
