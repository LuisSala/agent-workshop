# Google ADK Agent Workshop

Welcome to the Google ADK (Agent Development Kit) Workshop! This repository provides a comprehensive, step-by-step curriculum for building a multi-agent AI Newsroom application using Python, Google ADK, and Vertex AI.

> **Built on ADK 2.0 (Beta)** — the curriculum uses the new graph-based `Workflow` API (`google.adk.workflow.Workflow`) introduced in ADK 2.0 rather than the older `SequentialAgent` / `ParallelAgent` / `BaseAgent` patterns from 1.x. ADK 2.0 is in Beta; APIs may shift before GA. See [adk.dev/2.0](https://adk.dev/2.0/) for stability caveats.

## Curriculum Structure

This workshop is broken down into progressive modules:
- **Module 01: Foundation** — Introduction to solitary LLM interactions, basic tools, and ADK fundamentals.
- **Module 02: Agent Orchestration** — Building a linear three-step pipeline (planner → researcher with `google_search` → compiler) using `Workflow` with linear edges.
- **Module 03: Advanced Orchestration** — Dynamic parallel research via `@node(rerun_on_resume=True)` + `asyncio.gather(ctx.run_node(...))`, structured `NewspaperPage` output, and Google Search Grounding citation extraction.
- **Module 04: Vector Search & Routing** — Conditional routing via `RoutingMap` dict edges; a vector-search-backed archive branch; full Google Search Grounding display compliance through to the rendered web UI.

## Project Structure

```
agent-workshop/
├── workspace/             # Your live coding environment
│   └── app/               # Implement agent logic here
├── webapp/                # Flask UI for visualizing the newsroom pipeline
├── utils/                 # Shared helpers — kept out of agent files for readability
│   ├── citations.py       # Pulls verified URLs from grounding metadata events
│   └── vector_store.py    # Vertex AI Vector Search wrapper (used by mod04)
├── modules/               # Curriculum modules — each has start/ and solution/
├── .agents/skills/        # ADK reference materials (cheatsheets, docs)
├── GEMINI.md              # AI-assisted development guide (also used by Claude Code)
└── Makefile               # Commands for running, testing, and snapshotting
```

> 💡 **Tip:** Use [Gemini CLI](https://github.com/google-gemini/gemini-cli) for AI-assisted development - project context is pre-configured in `GEMINI.md`.

## Requirements

Before you begin, ensure you have:
- **uv**: Python package manager (used for all dependency management in this project) - [Install](https://docs.astral.sh/uv/getting-started/installation/) ([add packages](https://docs.astral.sh/uv/concepts/dependencies/) with `uv add <package>`)
- **Google Cloud SDK**: For GCP services - [Install](https://cloud.google.com/sdk/docs/install)
- **make**: Build automation tool - [Install](https://www.gnu.org/software/make/) (pre-installed on most Unix-based systems)
- **Google Agents-CLI**: `uvx google-agents-cli setup`

## Quick Start

Install required packages and launch the local development environment:

```bash
make install && make adk-web
```

## Commands

| Command              | Description                                                                                 |
| -------------------- | ------------------------------------------------------------------------------------------- |
| `make install`       | Install dependencies using uv                                                               |
| `make adk-web`    | Launch local development environment                                                        |
| `make lint`          | Run code quality checks                                                                     |
| `make test`          | Run unit and integration tests                                                              |
| `make deploy`        | Deploy agent to Agent Engine                                                                |
| `make register-gemini-enterprise` | Register deployed agent to Gemini Enterprise                                  |

For full command options and usage, refer to the [Makefile](Makefile).

## 🛠️ Project Management

| Command | What It Does |
|---------|--------------|
| `uvx agent-starter-pack enhance` | Add CI/CD pipelines and Terraform infrastructure |
| `uvx agent-starter-pack setup-cicd` | One-command setup of entire CI/CD pipeline + infrastructure |
| `uvx agent-starter-pack upgrade` | Auto-upgrade to latest version while preserving customizations |
| `uvx agent-starter-pack extract` | Extract minimal, shareable version of your agent |

---

## Development

Edit your agent logic in `app/agent.py` and test with `make adk-web` - it auto-reloads on save.
See the [development guide](https://googlecloudplatform.github.io/agent-starter-pack/guide/development-guide) for the full workflow.

## Deployment

```bash
gcloud config set project <your-project-id>
make deploy
```

To add CI/CD and Terraform, run `uvx agent-starter-pack enhance`.
To set up your production infrastructure, run `uvx agent-starter-pack setup-cicd`.
See the [deployment guide](https://googlecloudplatform.github.io/agent-starter-pack/guide/deployment) for details.

## Observability

Built-in telemetry exports to Cloud Trace, BigQuery, and Cloud Logging.
See the [observability guide](https://googlecloudplatform.github.io/agent-starter-pack/guide/observability) for queries and dashboards.
