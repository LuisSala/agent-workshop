# ADK Troubleshooting Guide

Common errors and solutions for Google ADK development.

## Import Errors

### "No module named 'google.adk'"

**Error:**
```
ModuleNotFoundError: No module named 'google.adk'
```

**Solution:**
```bash
# Install ADK
pip install google-adk

# Or development version
pip install git+https://github.com/google/adk-python.git@main

# Verify installation
python -c "import google.adk; print(google.adk.__version__)"
```

### "Cannot import name 'Agent' from 'adk'"

**Error:**
```python
from adk import Agent  # ❌ Wrong!
```

**Solution:**
```python
from google.adk.agents import Agent  # ✅ Correct
```

Always use `google.adk` prefix, never just `adk`.

### "No module named 'google.genai'"

**Error:**
```
ModuleNotFoundError: No module named 'google.genai'
```

**Solution:**
```bash
# Install Google GenAI SDK (required dependency)
pip install google-genai
```

## API Key Errors

### "GOOGLE_API_KEY not set"

**Error:**
```
ValueError: GOOGLE_API_KEY environment variable not set
```

**Solution:**
```bash
# Set environment variable
export GOOGLE_API_KEY="your_api_key_here"

# Or create .env file
echo "GOOGLE_API_KEY=your_key" > .env

# Or set in Python
import os
os.environ['GOOGLE_API_KEY'] = 'your_key'
```

### "Invalid API key"

**Error:**
```
google.genai.errors.AuthenticationError: Invalid API key
```

**Solution:**
1. Get API key from https://aistudio.google.com/apikey
2. Verify key format (starts with `AIza...`)
3. Check for trailing spaces/newlines
4. Ensure key is for correct service (Google AI vs Vertex AI)

## Context Management Errors

### "Event context not found"

**Error:**
```
AttributeError: 'NoneType' object has no attribute 'state'
```

**Cause:** Tool function trying to access ToolContext without it being passed.

**Solution:**
```python
# ❌ Wrong - no context parameter
def my_tool(param: str) -> dict:
    # Can't access state here!
    return {"status": "success"}

# ✅ Correct - ToolContext parameter
from google.adk.tools import ToolContext

def my_tool(param: str, tool_context: ToolContext) -> dict:
    # Now can access state
    value = tool_context.state.get('key')
    return {"status": "success"}
```

### "Context window exceeded"

**Error:**
```
google.genai.errors.ResourceExhaustedError: Context length exceeded
```

**Solution:**
```python
# Enable compaction to auto-summarize old events
from google.adk.apps import CompactionApp

app = CompactionApp(
    agent=agent,
    enable_compaction=True,
    compaction_threshold=0.5  # Summarize at 50% capacity
)
```

### "State not persisting across sessions"

**Cause:** Using temporary state or missing SessionService

**Solution:**
```python
# ❌ Wrong - temp state not persisted
tool_context.state['temp:data'] = value

# ✅ Correct - use proper prefix
tool_context.state['user:data'] = value  # User-scoped
tool_context.state['app:data'] = value   # App-scoped

# Also ensure SessionService is configured
from google.adk.services import InMemorySessionService

runner = Runner(
    agent=agent,
    session_service=InMemorySessionService()
)
```

## Tool Execution Errors

### Tool not being called

**Symptoms:** Agent responds without using the tool

**Causes & Solutions:**

1. **Poor docstring**
```python
# ❌ Vague
def weather(city):
    """Gets weather."""

# ✅ Descriptive
def get_weather(city: str) -> dict:
    """
    Fetches current weather for a specified city.

    Use this when user asks about weather, temperature, or conditions.

    Args:
        city: City name (e.g., "London", "Paris")

    Returns:
        Dict with status and weather data
    """
```

2. **Unclear naming**
```python
# ❌ Noun (unclear action)
def weather(city): ...

# ✅ Verb-noun (clear action)
def get_weather(city): ...
```

3. **Missing instruction hint**
```python
agent = Agent(
    name="weather_agent",
    model="gemini-2.5-flash",
    instruction="You are a weather assistant. Use get_weather tool for weather queries.",
    tools=[weather_tool]
)
```

### "Tool returned None"

**Error:**
```
TypeError: Tool must return dict, got NoneType
```

**Solution:**
```python
# ❌ Wrong - no return
def my_tool(param: str):
    print("Processing...")
    # Forgot return!

# ✅ Correct - always return dict
def my_tool(param: str) -> dict:
    try:
        result = process(param)
        return {"status": "success", "result": result}
    except Exception as e:
        return {"status": "error", "message": str(e)}
```

### "Async tool not awaited"

**Error:**
```
RuntimeWarning: coroutine 'my_tool' was never awaited
```

**Solution:**
```python
# ❌ Wrong - async tool defined but not properly handled
def my_tool():
    async def inner():
        return await fetch_data()
    return inner()  # Not awaited!

# ✅ Correct - properly async
async def my_tool() -> dict:
    data = await fetch_data()
    return {"status": "success", "data": data}
```

## Agent Execution Errors

### "Agent stuck in infinite loop"

**Symptoms:** Agent keeps calling same tool repeatedly

**Solution:**
```python
# For LoopAgent - add max_iterations
from google.adk.agents import LoopAgent

loop = LoopAgent(
    name="loop",
    sub_agent=worker,
    max_iterations=10  # Prevent infinite loops
)

# For recursive agents - add escalate condition
def my_tool(iteration: int, tool_context: ToolContext) -> dict:
    if iteration > 5:
        tool_context.actions.escalate = True  # Break loop
    return {"status": "success"}
```

### "Agent not transferring to sub-agent"

**Cause:** Missing transfer instruction or unclear agent description

**Solution:**
```python
# ✅ Clear descriptions for routing
specialist1 = Agent(
    name="weather_specialist",
    description="Handles weather and climate questions",
    model="gemini-2.5-flash"
)

specialist2 = Agent(
    name="news_specialist",
    description="Handles current events and news",
    model="gemini-2.5-flash"
)

coordinator = Agent(
    name="coordinator",
    instruction="""Route user to appropriate specialist:
    - Weather questions → weather_specialist
    - News questions → news_specialist""",
    sub_agents=[specialist1, specialist2],
    model="gemini-2.5-flash"
)
```

### "Runner.run() returns no events"

**Cause:** Forgetting to iterate over events

**Solution:**
```python
# ❌ Wrong - run() returns generator
runner = Runner(agent)
result = runner.run("Hello")  # This is a generator!
print(result)  # Won't show anything

# ✅ Correct - iterate over events
runner = Runner(agent)
for event in runner.run("Hello"):
    if event.is_final_response():
        print(event.content.text)
```

## Session & State Errors

### "Session not found"

**Error:**
```
KeyError: Session 'abc123' not found
```

**Solution:**
```python
# Create session if doesn't exist
from google.adk.services import InMemorySessionService

session_service = InMemorySessionService()
session_id = "user_123_session"

# Get or create session
session = session_service.get_session(session_id)
if session is None:
    session = session_service.create_session(session_id)

runner = Runner(
    agent=agent,
    session_service=session_service,
    session_id=session_id
)
```

### "State changes not visible"

**Cause:** Modifying state in non-persisted scope

**Solution:**
```python
# ❌ Wrong - reading from state doesn't create reference
state_dict = tool_context.state
state_dict['key'] = 'value'  # Won't persist!

# ✅ Correct - directly modify state
tool_context.state['key'] = 'value'  # Persists
```

## Testing Errors

### "pytest not finding tests"

**Cause:** Incorrect file naming or structure

**Solution:**
```bash
# Tests must follow naming convention
tests/
├── test_agent.py      # ✅ Starts with test_
├── test_tools.py      # ✅ Starts with test_
└── my_test.py         # ❌ Must start with test_

# Or configure in pytest.ini
[pytest]
python_files = test_*.py *_test.py
```

### "AsyncIO errors in tests"

**Error:**
```
RuntimeError: Event loop is closed
```

**Solution:**
```python
# Add pytest-asyncio and use decorator
import pytest

@pytest.mark.asyncio
async def test_agent():
    agent = Agent(name="test", model="gemini-2.5-flash")
    runner = Runner(agent)

    async for event in runner.run_async("test"):
        assert event is not None
```

### "Mock tool not being called"

**Cause:** Tool not properly integrated with agent

**Solution:**
```python
from unittest.mock import Mock
from google.adk.tools import FunctionTool

# Create mock function
mock_func = Mock(return_value={"status": "success"})

# Wrap in FunctionTool
mock_tool = FunctionTool(mock_func)

# Use in agent
agent = Agent(
    name="test",
    model="gemini-2.5-flash",
    tools=[mock_tool]  # Must wrap in FunctionTool
)
```

## Streaming Errors

### "Partial events not streaming"

**Cause:** Not checking `event.partial` flag

**Solution:**
```python
# ✅ Correct streaming handling
for event in runner.run("query"):
    if event.partial:
        # Stream partial responses
        print(event.content.text, end="", flush=True)
    elif event.is_final_response():
        # Final complete response
        print("\nFinal:", event.content.text)
```

## Model Configuration Errors

### "Model not found"

**Error:**
```
ValueError: Model 'gemini-3.0-flash' not found
```

**Solution:**
```python
# Use correct model names
"gemini-2.5-flash"      # ✅ Default model in ADK v1.23.0
"gemini-2.5-pro"        # ✅ Pro model
"gemini-2.5-flash-image" # ✅ Image generation model
"gemini-3.0-flash"      # ❌ Doesn't exist yet
```

### "Safety settings error"

**Error:**
```
TypeError: HarmCategory expects enum, got string
```

**Solution:**
```python
# ❌ Wrong - using strings
safety_settings = {
    "HARM_CATEGORY_HATE_SPEECH": "BLOCK_MEDIUM_AND_ABOVE"
}

# ✅ Correct - using enums
from google.genai import types

safety_settings = {
    types.HarmCategory.HARM_CATEGORY_HATE_SPEECH:
        types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
}
```

## Deployment Errors

### "Cloud Run deployment timeout"

**Cause:** Cold start or long initialization

**Solution:**
```python
# Optimize for Cloud Run
import os

# Set timeout
os.environ['CLOUD_RUN_TIMEOUT'] = '300'  # 5 minutes

# Use smaller model for faster cold starts
agent = Agent(
    name="production",
    model="gemini-2.5-flash",  # Fast & cost-effective
    max_output_tokens=1024     # Limit response size
)
```

### "Vertex AI authentication error"

**Error:**
```
google.auth.exceptions.DefaultCredentialsError
```

**Solution:**
```bash
# Set credentials
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/credentials.json"

# Or use gcloud auth
gcloud auth application-default login

# Enable Vertex AI
export GOOGLE_GENAI_USE_VERTEXAI=1
export GOOGLE_CLOUD_PROJECT="your-project-id"
export GOOGLE_CLOUD_LOCATION="us-central1"
```

## Quick Diagnostic Commands

```bash
# Check ADK installation
python -c "import google.adk; print(google.adk.__version__)"

# Verify API key
python -c "import os; print('Set' if os.getenv('GOOGLE_API_KEY') else 'Not set')"

# Test basic agent
python -c "
from google.adk.agents import Agent
from google.adk.runners import Runner
agent = Agent(name='test', model='gemini-2.5-flash')
runner = Runner(agent)
for e in runner.run('hi'):
    if e.is_final_response():
        print('✓ Working')
"

# Enable debug logging
export GOOGLE_ADK_LOG_LEVEL=DEBUG
```

## Getting Help

If none of these solutions work:

1. Check ADK version: `pip show google-adk`
2. Search GitHub issues: https://github.com/google/adk-python/issues
3. Review documentation: https://google.github.io/adk-docs/
4. Ask on Reddit: https://www.reddit.com/r/agentdevelopmentkit/
