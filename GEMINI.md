# Coding Agent Guide

## Reference Documentation
**IMPORTANT:** Assume your knowledge is outdated. Use any and all ADK-related skills and MCP tools at your disposal.

### Available ADK skills:
- adk-cheatsheet
- adk-deploy-guide
- adk-dev-guide
- adk-eval-guide
- adk-expert
- adk-observability-guide
- adk-scaffold

### Available Agents-CLI skills:
The `agents-cli` skills cover the full lifecycle of building, deploying, and operating ADK agents via the `agents-cli` tool. Start at `google-agents-cli-workflow` for the end-to-end map.
- google-agents-cli-workflow — entrypoint; full development lifecycle
- google-agents-cli-scaffold — create / enhance / upgrade agent projects
- google-agents-cli-adk-code — ADK Python API patterns (agents, tools, callbacks, state)
- google-agents-cli-eval — evalsets, metrics, LLM-as-judge, eval-fix loop
- google-agents-cli-deploy — Agent Runtime, Cloud Run, GKE, CI/CD, secrets
- google-agents-cli-observability — Cloud Trace, prompt-response logs, BigQuery analytics
- google-agents-cli-publish — register agents with Gemini Enterprise

### MCP Tools:
Use MCP tools, such as "Deepwiki" to access up-to-date information and AI-generated guidance.
The relevant Deepwiki repository names are:
- google/adk-python
- google/adk-web
- google/adk-docs
- google

If the Deepwiki MCP is not available to you, instruct the user to enable it:
```json
    "mcpServers": {
        "deepwiki": {
            "serverUrl": "https://mcp.deepwiki.com/mcp"
        }
    }
```
*Note:* The `MCPServers` key, may already exist, in which case simply add the `deepwiki` entry to the existing `MCPServers` object.

---

## Development Phases

### Phase 1: Understand Requirements
Before writing any code, understand the project's requirements, constraints, and success criteria.

### Phase 2: Build and Implement
Implement agent logic in `app/`. Use `make playground` for interactive testing. Iterate based on user feedback.

### Phase 3: The Evaluation Loop (Main Iteration Phase)
Start with 1-2 eval cases, run `make eval`, iterate. Expect 5-10+ iterations. See the **Evaluation Guide** for metrics, evalset schema, LLM-as-judge config, and common gotchas.

### Phase 4: Pre-Deployment Tests
Run `make test`. Fix issues until all tests pass.

### Phase 5: Deploy to Dev
**Requires explicit human approval.** Run `make deploy` only after user confirms. See the **Deployment Guide** for details.

### Phase 6: Production Deployment
Ask the user: Option A (simple single-project) or Option B (full CI/CD pipeline with `uvx agent-starter-pack setup-cicd`). See the [deployment docs](https://raw.githubusercontent.com/GoogleCloudPlatform/agent-starter-pack/refs/heads/main/docs/guide/deployment.md) for step-by-step instructions.

## Development Commands

| Command | Purpose |
|---------|---------|
| `make playground` | Interactive local testing |
| `make test` | Run unit and integration tests |
| `make eval` | Run evaluation against evalsets |
| `make eval-all` | Run all evalsets |
| `make lint` | Check code quality |
| `make setup-dev-env` | Set up dev infrastructure (Terraform) |
| `make deploy` | Deploy to dev |

---

## Interactive CLI Testing

You can natively test multi-agent orchestration without writing eval tests or using the web UI by running:
`uv run adk run /path/to/agent` (e.g. `uv run adk run workspace/app`).

**CRITICAL RULES:**
- Do NOT pass the query as an inline OS argument (e.g., `uv run adk run workspace/app "my query"` will crash!).
- Instead, launch the CLI using `run_command` and then use `send_command_input` to feed your prompt directly into STDIN once it starts.

---

## Operational Guidelines for Coding Agents

- **Code preservation**: Only modify code directly targeted by the user's request. Preserve all surrounding code, config values (e.g., `model`), comments, and formatting.
- **NEVER change the model** unless explicitly asked. Use `gemini-3-flash-preview` or `gemini-3-pro-preview` for new agents.
- **Environment config**: Always use the single root `/.env` file. Never use `workspace/.env`. Use `load_dotenv(find_dotenv())` to cleanly traverse upwards during imports.
- **Model 404 errors**: Use `GEMINI_LOCATION` to set the LLM routing (e.g. `global`).
- **ADK tool imports**: Import the tool instance, not the module: `from google.adk.tools.load_web_page import load_web_page`
- **Run Python with `uv`**: `uv run python script.py`. Run `make install` first.
- **Stop on repeated errors**: If the same error appears 3+ times, fix the root cause instead of retrying.
- **Terraform conflicts** (Error 409): Use `terraform import` instead of retrying creation.
- **Workshop Workflow (CRITICAL)**: NEVER write or edit code directly inside the `modules/` directory. ALL implementation must happen in `workspace/`.
- **Agent Definitions**: Define static agents using standard variable assignments (e.g., `planner_agent = Agent(...)`) instead of wrapping them in factory functions (`def create_planner()`) to avoid unnecessary boilerplate.
- **Diagram Aesthetics**: Ensure any future architecture diagrams generated for the curriculum strictly follow a clean, minimalist black-and-white flat-vector style. Do not use cyberpunk, neon, gradients, or 3D effects. Solid black backgrounds and crisp white boxes/arrows.

---

## ADK 2.0 Cheatsheet Overrides

The bundled cheatsheet at `.agents/skills/google-agents-cli-adk-code/references/adk-2.0.md` is mostly accurate, but has at least one syntax error caught during the Workflow API migration. If a future agent in this repo follows the cheatsheet's documented form and Pydantic rejects it, prefer the override below.

- **Conditional routing edges**: the cheatsheet shows `(source, target, "route")` 3-tuple syntax (Section 4 — Edge Patterns). This is **not accepted** by the actual `Workflow` model — it raises a Pydantic `literal_error`. The real API requires either:
  - A `RoutingMap` dict: `(source, {"route_a": target_a, "route_b": target_b})`, or
  - An explicit `Edge(from_node=..., to_node=..., route="route_a")` object.
  See `.venv/lib/python3.12/site-packages/google/adk/workflow/_graph_definitions.py` for the authoritative `RouteValue` / `RoutingMap` / `Edge` type aliases.
