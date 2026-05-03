---
name: adk-expert
description: Expert guidance for Google ADK (Agent Development Kit) Python development.
  Use when working with ADK agents, tools, workflows, sessions, streaming, MCP,
  callbacks, testing, or any ADK-related code. Provides code generation, debugging,
  API reference, and best practices for ADK v1.23.0.
---

# ADK Expert v1.6.0

Expert guidance for Google Agent Development Kit (ADK) Python v1.23.0. Python 3.10+ required.

## Resources

### Quick References (load first for common questions)

| File | Use for |
|------|---------|
| `references/api-quick-ref.md` | API parameters, constructors, types |
| `references/quick-patterns.md` | Common code patterns and snippets |
| `references/troubleshooting.md` | Error messages, fixes, diagnostics |

### Knowledge Base (load for deep understanding)

| File | Topics |
|------|--------|
| `knowledge-base/core-concepts/README.md` | Architecture overview |
| `knowledge-base/core-concepts/01-agents.md` | LLM, workflow, custom agents; model config; transfer controls |
| `knowledge-base/core-concepts/02-tools.md` | Function tools, built-in tools, toolsets, multimodal results |
| `knowledge-base/core-concepts/03-context-management.md` | Events, compaction, callbacks, artifacts, memory |
| `knowledge-base/core-concepts/04-runtime.md` | Runner, event loop, plugins, resumability, live mode |
| `knowledge-base/core-concepts/05-sessions-state.md` | State scoping, session services, migration, delta tracking |
| `knowledge-base/testing/README.md` | pytest setup, fixtures, mocking, evaluation tests |
| `knowledge-base/best-practices/README.md` | Agent/tool design patterns, code execution customization |
| `knowledge-base/best-practices/multimedia-rendering.md` | Media rendering, HTML widgets, data URLs |
| `knowledge-base/integrations/README.md` | Google services, MCP, LangChain, CrewAI, observability, BigQuery analytics |
| `knowledge-base/integrations/api-server-custom-ui.md` | ADK API server for custom UIs |
| `knowledge-base/advanced/README.md` | Grounding, evaluation, deployment, performance, security |
| `knowledge-base/advanced/streaming.md` | Text streaming, Live API, WebSocket/SSE patterns |
| `knowledge-base/examples/README.md` | Annotated code examples |
| `knowledge-base/examples/image-generation-callbacks.md` | Image generation with callbacks |
| `knowledge-base/examples/live-api-demo.py` | Working Live API demo |
| `knowledge-base/api-reference/README.md` | Comprehensive API reference with examples |

### Source Code (load for implementation-level answers)

`source/google/adk/` contains a trimmed snapshot of ADK v1.23.0 Python source.

| Directory | Contains |
|-----------|----------|
| `source/google/adk/agents/` | Agent base classes, LLM agent, workflow agents |
| `source/google/adk/tools/` | Tool base classes, function tool (top-level .py only) |
| `source/google/adk/flows/` | LLM flow, request/response processing |
| `source/google/adk/models/` | Model interfaces, Gemini/LiteLLM wrappers |
| `source/google/adk/sessions/` | Session services (in-memory, SQLite, database, Vertex) |
| `source/google/adk/artifacts/` | Artifact services (in-memory, GCS, file) |
| `source/google/adk/memory/` | Memory services (in-memory, Vertex) |
| `source/google/adk/events/` | Event classes and processing |
| `source/google/adk/apps/` | App wrappers (FastAPI, compaction) |
| `source/google/adk/plugins/` | Plugin base and built-in plugins |
| `source/google/adk/auth/` | OAuth and credential handling |
| `source/google/adk/utils/` | Utility functions |
| `source/google/adk/runners.py` | Runner (sync/async), InMemoryRunner, run_debug |
| `source/google/adk/__init__.py` | Public API exports |

Read specific source files when users ask how something works internally or when docs are insufficient.

### Samples (load for real-world examples)

`samples/INDEX.md` catalogs all curated samples with descriptions and file lists.

- **Core samples** (`samples/core/`): Official ADK examples — basics, multi-agent, callbacks, streaming, state, MCP, auth, integrations, code execution, model providers, plugins, advanced patterns
- **Community samples** (`samples/community/`): Production examples — customer-service, deep-search, travel-concierge, RAG

Always read `samples/INDEX.md` first to find the right sample, then read the sample directory.

### Templates (copy-paste starters)

| Template | Purpose |
|----------|---------|
| `assets/templates/agent_basic.py` | Simple LLM agent |
| `assets/templates/agent_with_tools.py` | Agent with custom tools |
| `assets/templates/multi_agent.py` | Multi-agent coordinator |
| `assets/templates/callback_example.py` | Lifecycle callbacks |
| `assets/templates/memory_example.py` | Memory service integration |
| `assets/templates/test_template.py` | pytest test suite |

### Scripts

| Script | Purpose |
|--------|---------|
| `scripts/validate_adk_code.py` | Validate ADK code for common issues |

## Decision Tree

Follow this routing logic for every ADK question:

```
User question about ADK
│
├─ Error/debugging ("I'm getting...", "Why isn't...", stack trace)
│   1. Read references/troubleshooting.md
│   2. If not found, search knowledge-base/ for related topic
│   3. If implementation detail needed, read source/google/adk/
│   4. Provide fix with explanation
│
├─ API lookup ("What parameters...", "How to call...", constructor)
│   1. Read references/api-quick-ref.md
│   2. If not found, read knowledge-base/api-reference/README.md
│   3. If still unclear, read the actual source file
│   4. Provide signature, types, defaults, example
│
├─ Code generation ("Create an agent...", "Write a tool...", "Show me...")
│   1. Read references/quick-patterns.md for matching pattern
│   2. Read relevant knowledge-base/ section for context
│   3. Check samples/INDEX.md for similar examples
│   4. Use assets/templates/ as starting point if applicable
│   5. Generate customized code following ADK conventions
│
├─ How does X work internally? ("How does the runner...", "What happens when...")
│   1. Read relevant knowledge-base/ doc first
│   2. Read source/google/adk/ for the specific module
│   3. Explain with references to source code
│
├─ Best practices ("What's the best way...", "Should I use...")
│   1. Read knowledge-base/best-practices/README.md
│   2. Read relevant topic docs (agents, tools, etc.)
│   3. Check samples/ for production patterns
│   4. Recommend approach with tradeoffs
│
├─ Testing ("How to test...", "Write tests for...")
│   1. Read knowledge-base/testing/README.md
│   2. Read assets/templates/test_template.py
│   3. Check references/quick-patterns.md testing section
│   4. Generate pytest code
│
├─ Integration ("MCP", "LangChain", "Vertex", "BigQuery", "deployment")
│   1. Read knowledge-base/integrations/README.md
│   2. Read knowledge-base/advanced/README.md for deployment
│   3. Check samples/INDEX.md for integration examples
│
└─ General concept ("What is...", "Explain...")
    1. Read knowledge-base/core-concepts/ relevant file
    2. Supplement with references/quick-patterns.md
    3. Point to samples/ for practical examples
```

## Key ADK Facts

- **Default model**: `gemini-2.5-flash` (model parameter is optional since v1.23.0)
- **Imports**: `from google.adk.runners import Runner` (not `from google.adk import Runner`)
- **Agent naming**: Must be valid Python identifiers, no "user", unique among sub-agents
- **State prefixes**: `app:` (app-wide), `user:` (per-user), no prefix (session), `temp:` (turn-only)
- **Tool returns**: Always return `dict` with `"status"` key
- **Tool naming**: Use verb-noun pattern (e.g., `search_documents`, `get_weather`)
- **Testing**: Use `InMemoryRunner` for tests, `run_debug()` for quick REPL testing

## ADK Conventions for Code Generation

When generating ADK code, always follow these patterns:

```python
# Correct imports (v1.23.0)
from google.adk.agents import LlmAgent, SequentialAgent, ParallelAgent, LoopAgent
from google.adk.runners import Runner, InMemoryRunner
from google.adk.sessions import InMemorySessionService
from google.adk.tools import FunctionTool
from google.adk.memory import InMemoryMemoryService
from google.adk.artifacts import InMemoryArtifactService

# Tool pattern
def search_items(query: str, max_results: int = 10) -> dict:
    """Search for items matching the query.

    Args:
        query: Search query string.
        max_results: Maximum number of results to return.

    Returns:
        dict with status and results.
    """
    results = do_search(query, max_results)
    return {"status": "success", "results": results}

# Agent pattern
agent = LlmAgent(
    name="my_agent",
    model="gemini-2.5-flash",  # optional, this is the default
    instruction="You are a helpful assistant.",
    tools=[search_items],
)

# Runner pattern
runner = InMemoryRunner(agent=agent, app_name="my_app")
```
