# ADK API Quick Reference

Condensed API reference for fast parameter lookup. For full details, see auto-generated docs or main knowledge base.

## Core Imports

```python
# Agents
from google.adk.agents import Agent, LlmAgent, BaseAgent
from google.adk.agents import SequentialAgent, ParallelAgent, LoopAgent

# Tools
from google.adk.tools import FunctionTool, LongRunningFunctionTool, ToolContext
from google.adk.tools import google_search

# Runtime
from google.adk.runners import Runner
from google.adk.runners import InvocationContext
from google.adk.events.event import Event

# Services
from google.adk.services import (
    InMemorySessionService,
    MemoryService,
    ArtifactService
)

# Apps
from google.adk.apps import CompactionApp

# Google GenAI (for types)
from google.genai import types
```

## Agent Classes

### `Agent` / `LlmAgent`

```python
Agent(
    # Required
    name: str,                           # Valid Python identifier, not "user"

    # Model (v1.23.0+: Optional - inherits from parent or default)
    model: str | BaseLlm = "",           # Default: "gemini-2.5-flash"

    # Instructions
    instruction: str | Callable = "",    # Dynamic (supports variable substitution)
    static_instruction: Content = None,  # v1.23.0+ Static (cached, no substitution)
    description: str = "",

    # Tools & Sub-agents
    tools: list[Tool] = [],
    sub_agents: list[BaseAgent] = [],    # Must have unique names

    # Model parameters
    temperature: float = 0.7,            # 0.0-1.0
    top_p: float = 0.95,
    top_k: int = 40,
    max_output_tokens: int = 8192,

    # Safety & grounding
    safety_settings: dict = None,
    grounding: bool = False,

    # Features
    enable_code_execution: bool = False,
    enable_planning: bool = False,

    # Transfer control (v1.23.0+)
    disallow_transfer_to_parent: bool = False,
    disallow_transfer_to_peers: bool = False,

    # Callbacks (single or list)
    before_agent_callback: Callable | list = None,
    after_agent_callback: Callable | list = None,
    before_model_callback: Callable | list = None,
    after_model_callback: Callable | list = None,
    on_model_error_callback: Callable | list = None,
    before_tool_callback: Callable | list = None,
    after_tool_callback: Callable | list = None,
    on_tool_error_callback: Callable | list = None,
)
```

**Class Methods (v1.23.0+):**
- `LlmAgent.set_default_model(model)` - Set global default model

**Key Methods:**
- `invoke(context: InvocationContext) -> Generator[Event]`
- `get_tools() -> list[Tool]`
- `get_child_agents() -> list[BaseAgent]`

### `SequentialAgent`

```python
SequentialAgent(
    name: str,
    sub_agents: list[BaseAgent],
    instruction: str = ""
)
```

Executes sub-agents in order.

### `ParallelAgent`

```python
ParallelAgent(
    name: str,
    sub_agents: list[BaseAgent],
    aggregator_instruction: str = "",
    aggregator_model: str = "gemini-2.5-flash"
)
```

Executes sub-agents concurrently, aggregates results.

### `LoopAgent`

```python
LoopAgent(
    name: str,
    sub_agent: BaseAgent,
    max_iterations: int = 10,
    instruction: str = ""
)
```

Loops sub-agent until complete or max iterations.

### `BaseAgent`

```python
class CustomAgent(BaseAgent):
    def __init__(self, name: str, **kwargs):
        super().__init__(name=name, **kwargs)

    def invoke(self, context: InvocationContext):
        # Custom logic
        yield Event(
            author=self.name,
            content=types.Content(
                role="model",
                parts=[types.Part(text="Response")]
            )
        )
```

## Tool Classes

### `FunctionTool`

```python
from google.adk.tools import FunctionTool

def my_function(param: str, tool_context: ToolContext) -> dict:
    """Function description for LLM."""
    return {"status": "success"}

tool = FunctionTool(my_function)
```

**Function Signature:**
- Parameters: Any JSON-serializable types
- Optional `tool_context: ToolContext` parameter
- Return: `dict` (must include 'status' key)

### `LongRunningFunctionTool`

```python
from google.adk.tools import LongRunningFunctionTool

async def async_function(param: str) -> dict:
    await asyncio.sleep(5)
    return {"status": "complete"}

tool = LongRunningFunctionTool(async_function)
```

For async operations that take significant time.

### `ToolContext`

```python
from google.adk.tools import ToolContext

def tool_with_context(param: str, tool_context: ToolContext) -> dict:
    # Access state
    value = tool_context.state.get('key')
    tool_context.state['key'] = 'new_value'

    # Access actions
    tool_context.actions.transfer_to_agent = "agent_name"
    tool_context.actions.escalate = True

    # Access services
    tool_context.memory_service.add(content="...")
    tool_context.artifact_service.save(name="file", content=b"...")

    # Access context
    agent_name = tool_context.invocation_context.agent.name
    events = tool_context.invocation_context.events

    return {"status": "success"}
```

**Properties:**
- `state: dict` - Session state
- `actions: EventActions` - Control flow actions
- `invocation_context: InvocationContext` - Full context
- `memory_service: MemoryService` - Long-term memory
- `artifact_service: ArtifactService` - File storage

## Runner

### `Runner`

```python
from google.adk.runners import Runner

runner = Runner(
    agent: BaseAgent,
    session_service: SessionService = None,
    artifact_service: ArtifactService = None,
    memory_service: MemoryService = None,
    session_id: str = None,
    user_id: str = None,
    plugins: list[Plugin] = []
)
```

**Methods:**

```python
# Sync execution
for event in runner.run(user_message: str):
    if event.is_final_response():
        print(event.content.text)

# Async execution
async for event in runner.run_async(user_message: str):
    if event.is_final_response():
        print(event.content.text)

# Resume execution
for event in runner.resume(events: list[Event]):
    ...
```

## Event

### `Event`

```python
from google.adk.events.event import Event
from google.genai import types

event = Event(
    author: str,                    # "user" or agent name
    content: types.Content,         # Message content
    actions: EventActions = None,   # Actions taken
    partial: bool = False,          # Streaming indicator
    branch: str = None              # Multi-agent branch
)
```

**Key Properties:**
- `id: str` - Unique identifier
- `invocation_id: str` - Groups events in invocation
- `author: str` - Who created event
- `content: types.Content` - Message content
- `actions: EventActions` - Tool calls, transfers
- `timestamp: float` - Creation time
- `partial: bool` - If streaming partial response

**Key Methods:**
- `is_final_response() -> bool` - Check if final
- `get_text() -> str` - Extract text content

## Services

### `InMemorySessionService`

```python
from google.adk.services import InMemorySessionService

session_service = InMemorySessionService()

runner = Runner(
    agent=agent,
    session_service=session_service,
    session_id="user_123"
)
```

Stores sessions in memory (not persistent across restarts).

### `MemoryService`

```python
from google.adk.services import MemoryService

memory = MemoryService()

# Add memory
memory.add(
    content: str,
    metadata: dict = {}
)

# Search memories
results = memory.search(
    query: str,
    top_k: int = 5
)
```

Long-term memory across sessions.

### `ArtifactService`

```python
from google.adk.services import ArtifactService

artifacts = ArtifactService()

# Save artifact
artifact = artifacts.save(
    name: str,
    content: bytes,
    scope: str = "session",  # or "user"
    metadata: dict = {}
)

# Retrieve artifact
artifact = artifacts.get(
    artifact_id: str
)
```

Versioned file storage.

## State Prefixes

```python
# Application-wide (all users, all sessions)
state['app:config'] = {...}

# User-specific (all sessions for user)
state['user:preferences'] = {...}

# Session-specific (current conversation)
state['session_data'] = {...}

# Temporary (not persisted)
state['temp:cache'] = {...}
```

## Safety Settings

```python
from google.genai import types

safety_settings = {
    types.HarmCategory.HARM_CATEGORY_HATE_SPEECH:
        types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT:
        types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT:
        types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    types.HarmCategory.HARM_CATEGORY_HARASSMENT:
        types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
}

agent = Agent(
    name="safe_agent",
    model="gemini-2.5-flash",
    safety_settings=safety_settings
)
```

## Compaction

```python
from google.adk.apps import CompactionApp

app = CompactionApp(
    agent: BaseAgent,
    enable_compaction: bool = True,
    compaction_threshold: float = 0.5,  # 50% of context
    compaction_function: Callable = None  # Custom compactor
)
```

Auto-summarizes old events to manage context window.

## Common Model Names

```python
# Flash models (fast, cost-effective) - Default
"gemini-2.5-flash"          # Default model in ADK v1.23.0

# Pro models (more capable)
"gemini-2.5-pro"

# Image generation
"gemini-2.5-flash-image"    # Text + image generation

# Via LiteLLM (100+ providers)
"litellm/anthropic/claude-sonnet-4-20250514"
"litellm/openai/gpt-4o"
```

## Environment Variables

```bash
# Google AI Studio (default)
GOOGLE_API_KEY=your_api_key
GOOGLE_GENAI_USE_VERTEXAI=0

# Vertex AI
GOOGLE_CLOUD_PROJECT=your_project
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_GENAI_USE_VERTEXAI=1
GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json
```

## Type Hints

```python
from typing import Generator, Callable
from google.adk.agents import BaseAgent
from google.adk.runners import InvocationContext
from google.adk.events.event import Event
from google.adk.tools import ToolContext
from google.genai import types

# Agent invoke signature
def invoke(
    self,
    context: InvocationContext
) -> Generator[Event, None, None]:
    ...

# Tool signature
def tool_function(
    param: str,
    tool_context: ToolContext
) -> dict:
    ...

# Callback signature
def callback(context: InvocationContext) -> None:
    ...
```

## Quick Patterns

### Minimal Agent
```python
from google.adk.agents import Agent
from google.adk.runners import Runner

agent = Agent(name="bot", model="gemini-2.5-flash")
runner = Runner(agent)
for e in runner.run("hi"):
    if e.is_final_response():
        print(e.content.text)
```

### Agent with Tool
```python
from google.adk.tools import FunctionTool

def get_time() -> dict:
    """Get current time."""
    import datetime
    return {"status": "success", "time": str(datetime.datetime.now())}

agent = Agent(
    name="assistant",
    model="gemini-2.5-flash",
    tools=[FunctionTool(get_time)]
)
```

### Stateful Tool
```python
from google.adk.tools import ToolContext

def counter(tool_context: ToolContext) -> dict:
    """Increment counter."""
    count = tool_context.state.get('count', 0)
    count += 1
    tool_context.state['count'] = count
    return {"status": "success", "count": count}
```

### Multi-Agent
```python
spec1 = Agent(name="s1", model="gemini-2.5-flash")
spec2 = Agent(name="s2", model="gemini-2.5-flash")

coordinator = Agent(
    name="coordinator",
    model="gemini-2.5-flash",
    instruction="Route to s1 or s2 based on query",
    sub_agents=[spec1, spec2]
)
```
