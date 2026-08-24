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

# MODULE 01-FOUNDATION: START

import datetime
from zoneinfo import ZoneInfo

from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.genai import types

import os

# TODO (Module 01, Step 2): add `import random` here — get_weather() needs it
#                           and it is NOT imported yet (see README).


# TODO (Module 01, Step 2): paste your get_weather() function here.
# It should return a random temperature and weather condition for a given city.
# Then (Step 3) register it in the root_agent's tools=[...] list below.


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
    # TODO (Module 01, Step 3): add get_weather to register it as a tool ->
    tools=[get_current_server_time],
)

app = App(
    root_agent=root_agent,
    name="app",
)
