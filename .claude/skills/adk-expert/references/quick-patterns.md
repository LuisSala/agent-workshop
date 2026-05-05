# ADK Quick Patterns Reference

Fast reference for common ADK code patterns. Load this file when answering quick "how do I..." questions.

## Agent Creation

### Basic LLM Agent
```python
from google.adk.agents import Agent
from google.adk.runners import InMemoryRunner

agent = Agent(
    name="my_agent",
    model="gemini-2.5-flash",  # Optional in v1.23.0+ (uses default)
    instruction="You are a helpful assistant."
)

# Quick debugging (v1.18.0+)
runner = InMemoryRunner(agent=agent)
await runner.run_debug("Hello!")
```

### Model Inheritance (v1.23.0+)
```python
# Set global default model
LlmAgent.set_default_model("gemini-2.5-pro")

# Children inherit model from parent
parent = Agent(
    name="parent",
    model="gemini-2.5-flash",
    sub_agents=[
        Agent(name="child1"),  # Inherits gemini-2.5-flash
        Agent(name="child2"),  # Also inherits
    ]
)
```

### Agent with Tools
```python
from google.adk.tools import FunctionTool

def my_tool(param: str) -> dict:
    """Tool description for LLM."""
    return {"status": "success", "result": param}

agent = Agent(
    name="tool_agent",
    tools=[FunctionTool(my_tool)]  # model is optional
)
```

### Multi-Agent with Transfer Control (v1.23.0+)
```python
from google.adk.tools import TransferToAgentTool

specialist1 = Agent(name="billing", description="Handles billing")
specialist2 = Agent(name="support", description="Handles support")

# Use TransferToAgentTool for safe transfers (prevents hallucination)
coordinator = Agent(
    name="coordinator",
    instruction="Route to appropriate specialist",
    tools=[TransferToAgentTool(agent_names=["billing", "support"])],
    sub_agents=[specialist1, specialist2]
)
```

## Workflow Agents

### Sequential Pipeline
```python
from google.adk.agents import SequentialAgent

pipeline = SequentialAgent(
    name="pipeline",
    sub_agents=[agent1, agent2, agent3]
)
```

### Parallel Execution
```python
from google.adk.agents import ParallelAgent

parallel = ParallelAgent(
    name="parallel",
    sub_agents=[agent1, agent2, agent3],
    aggregator_instruction="Combine results into summary"
)
```

### Loop Agent
```python
from google.adk.agents import LoopAgent

loop = LoopAgent(
    name="loop",
    sub_agent=worker_agent,
    max_iterations=10
)
```

## Tool Patterns

### Standard Function Tool
```python
from google.adk.tools import FunctionTool

def get_weather(city: str) -> dict:
    """
    Fetches current weather for a city.

    Args:
        city: City name (e.g., "London", "Paris")

    Returns:
        Dict with status and weather data
    """
    try:
        # Implementation
        return {
            "status": "success",
            "weather": {"temp": 18, "condition": "Cloudy"}
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

weather_tool = FunctionTool(get_weather)
```

### Tool with Context Access
```python
from google.adk.tools import ToolContext

def stateful_tool(param: str, tool_context: ToolContext) -> dict:
    """Tool with state and control flow access."""

    # Read state
    value = tool_context.state.get('key', 'default')

    # Write state
    tool_context.state['key'] = 'new_value'

    # Transfer to another agent
    tool_context.actions.transfer_to_agent = "other_agent"

    # Escalate to parent
    tool_context.actions.escalate = True

    return {"status": "success"}
```

### Async Tool
```python
import aiohttp

async def async_tool(url: str) -> dict:
    """Async tool for I/O operations."""
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.json()
            return {"status": "success", "data": data}
```

## State Management

### State Prefixes
```python
# Application-wide (all users, all sessions)
tool_context.state['app:config'] = {...}

# User-specific (all sessions for this user)
tool_context.state['user:preferences'] = {...}

# Session-specific (current conversation only)
tool_context.state['session_data'] = {...}

# Temporary (not persisted)
tool_context.state['temp:cache'] = {...}
```

### Session Service
```python
from google.adk.services import InMemorySessionService

# In-memory session service
session_service = InMemorySessionService()

runner = Runner(
    agent=agent,
    session_service=session_service
)
```

## Callbacks

### Agent Lifecycle Callbacks
```python
def before_agent(context):
    """Called before agent runs."""
    print(f"Agent {context.agent.name} starting")
    # Access: context.agent, context.state, context.events

def after_agent(context):
    """Called after agent completes."""
    print(f"Agent {context.agent.name} finished")

agent = Agent(
    name="with_callbacks",
    model="gemini-2.5-flash",
    before_agent_callback=before_agent,
    after_agent_callback=after_agent
)
```

### Model Lifecycle Callbacks
```python
def before_model(context):
    """Called before each LLM call."""
    print("Calling LLM")

def after_model(context):
    """Called after each LLM response."""
    print(f"Token usage: {context.usage}")

agent = Agent(
    name="with_model_callbacks",
    model="gemini-2.5-flash",
    before_model_callback=before_model,
    after_model_callback=after_model
)
```

### Image Generation Callback
```python
def save_image_callback(callback_context, llm_response=None):
    """Save generated image from gemini-2.5-flash-image model."""
    if hasattr(llm_response, "content") and llm_response.content:
        for part in llm_response.content.parts:
            if hasattr(part, "inline_data") and part.inline_data:
                # inline_data.data is raw binary (not base64)
                image_data = part.inline_data.data
                mime_type = part.inline_data.mime_type

                # Save to disk
                filename = callback_context.state.get("image_filename", "image.png")
                with open(f"./output/{filename}", "wb") as f:
                    f.write(image_data)

                # Store path in state
                callback_context.state["generated_image_path"] = f"./output/{filename}"
                break

image_agent = Agent(
    name="image_generator",
    model="gemini-2.5-flash-image",
    instruction="Generate images based on prompts",
    after_model_callback=save_image_callback
)
```

## Context Management

### Compaction (Auto Summarization)
```python
from google.adk.apps import CompactionApp

# Automatic compaction at 50% of context window
app = CompactionApp(
    agent=agent,
    enable_compaction=True,
    compaction_threshold=0.5  # Trigger at 50% full
)
```

### Custom Compaction
```python
from google.adk.apps import CompactionApp

def custom_compactor(events, agent):
    """Custom summarization logic."""
    # Filter events to keep
    important_events = [e for e in events if is_important(e)]

    # Summarize old events
    summary = "Summary of earlier conversation..."

    return important_events, summary

app = CompactionApp(
    agent=agent,
    compaction_function=custom_compactor
)
```

### Artifacts
```python
from google.adk.tools import ToolContext

def generate_report(topic: str, tool_context: ToolContext) -> dict:
    """Generate and store report as artifact."""

    report_content = f"Report on {topic}..."

    # Save artifact (versioned, scoped to user or session)
    artifact = tool_context.artifact_service.save(
        name=f"{topic}_report.md",
        content=report_content.encode(),
        scope="user",  # or "session"
        metadata={"topic": topic, "version": "1.0"}
    )

    return {
        "status": "success",
        "artifact_id": artifact.id,
        "url": artifact.url
    }
```

### Memory (Long-term Knowledge)
```python
from google.adk.services import MemoryService

def store_fact(fact: str, tool_context: ToolContext) -> dict:
    """Store fact in long-term memory."""

    tool_context.memory_service.add(
        content=fact,
        metadata={"type": "user_preference"}
    )

    return {"status": "success"}

def recall_facts(query: str, tool_context: ToolContext) -> dict:
    """Retrieve relevant facts from memory."""

    memories = tool_context.memory_service.search(
        query=query,
        top_k=5
    )

    return {
        "status": "success",
        "memories": [m.content for m in memories]
    }
```

## Streaming

### Text Streaming
```python
# Sync streaming
for event in runner.run("query"):
    if event.partial:
        print(event.content.text, end="", flush=True)
    elif event.is_final_response():
        print("\n" + event.content.text)

# Async streaming
async for event in runner.run_async("query"):
    if event.partial:
        print(event.content.text, end="", flush=True)
    elif event.is_final_response():
        print("\n" + event.content.text)
```

## Testing Patterns

### Basic Test
```python
import pytest
from google.adk.agents import Agent
from google.adk.runners import Runner

@pytest.mark.asyncio
async def test_agent():
    agent = Agent(name="test", model="gemini-2.5-flash")
    runner = Runner(agent)

    events = []
    async for event in runner.run_async("test"):
        events.append(event)

    assert len(events) > 0
```

### Test Fixture
```python
@pytest.fixture
def agent():
    return Agent(
        name="test",
        model="gemini-2.5-flash",
        instruction="Test agent"
    )

def test_with_fixture(agent):
    assert agent.name == "test"
```

### Mock Tool
```python
from unittest.mock import Mock

@pytest.fixture
def mock_tool():
    tool = Mock()
    tool.run.return_value = {"status": "success"}
    return tool

def test_agent_with_mock(mock_tool):
    agent = Agent(
        name="test",
        model="gemini-2.5-flash",
        tools=[mock_tool]
    )
    # Test agent behavior
```

## Built-in Tools

```python
from google.adk.tools import google_search

# Google Search
agent = Agent(
    name="searcher",
    model="gemini-2.5-flash",
    tools=[google_search]
)

# Code Execution
agent = Agent(
    name="coder",
    model="gemini-2.5-flash",
    enable_code_execution=True
)

# Grounding (Google Search integration)
agent = Agent(
    name="grounded",
    model="gemini-2.5-flash",
    grounding=True
)
```

## Error Handling

```python
def safe_tool(param: str) -> dict:
    """Tool with comprehensive error handling."""
    try:
        result = process(param)
        return {"status": "success", "result": result}
    except ValueError as e:
        return {"status": "error", "message": f"Invalid input: {e}"}
    except ConnectionError as e:
        return {"status": "error", "message": "Service unavailable"}
    except Exception as e:
        return {"status": "error", "message": "Unexpected error occurred"}
```

## Common Issues

### Tool Not Being Called
- Check docstring is descriptive
- Use verb-noun naming (e.g., `get_weather`, not `weather`)
- Mention tool in agent instruction
- Ensure return type is dict with 'status' key

### Agent Stuck in Loop
- Add `max_iterations` to LoopAgent
- Check escalate condition
- Review transfer logic
- Add timeout to Runner

### Context Window Exhausted
- Enable compaction with `CompactionApp`
- Use memory service for long-term facts
- Limit conversation history
- Summarize old events

### State Not Persisting
- Check state prefix (app:, user:, temp:)
- Verify SessionService is configured
- Ensure session_id is consistent
- Don't use temp: for persistent data
