
.DEFAULT_GOAL := help

# ==============================================================================
# Help
# ==============================================================================

help:
	@echo "==============================================================================="
	@echo "| Agent Workshop Development Commands                                         |"
	@echo "==============================================================================="
	@echo "  make playground     - Launch local dev playground (Web UI & CLI)"
	@echo "  make run-webapp     - Launch the AI Newsroom Web UI directly"
	@echo "  make run-slides     - Launch the interactive Marimo Workshop Slideshow"
	@echo "  make test           - Run unit and integration tests"
	@echo "  make eval           - Run agent evaluation using ADK evalsets"
	@echo "  make lint           - Run code quality checks"
	@echo "  make deploy         - Deploy the agent remotely"
	@echo "  make catchup        - Start over at the beginning of a specific module"
	@echo "  make solve          - Applies the solution of a module directly into the workspace"
	@echo "  make snapshot       - Save the current workspace to a module's solution directory"
	@echo "  make harvest        - Run the Vector Search News Harvester daemon"
	@echo "  make vector-cli     - Run the Vector Search diagnostic CLI (Usage: make vector-cli ARGS=\"...\")"
	@echo "==============================================================================="

# ==============================================================================
# Installation & Setup
# ==============================================================================

# Install dependencies using uv package manager
install:
	@command -v uv >/dev/null 2>&1 || { echo "uv is not installed. Installing uv..."; curl -LsSf https://astral.sh/uv/0.8.13/install.sh | sh; source $HOME/.local/bin/env; }
	uv sync

# ==============================================================================
# Playground Targets
# ==============================================================================

# Launch local dev playground
playground:
	@echo "==============================================================================="
	@echo "| 🚀 Starting your agent playground...                                        |"
	@echo "|                                                                             |"
	@echo "| 💡 Try asking: What's the weather in San Francisco?                         |"
	@echo "|                                                                             |"
	@echo "| 🔍 IMPORTANT: Select the 'app' folder to interact with your agent.          |"
	@echo "==============================================================================="
	uv run adk web workspace --port 8501 --reload_agents

# Launch Flask Newsroom UI
run-webapp:
	@echo "==============================================================================="
	@echo "| 📰 Starting your AI Newsroom Web UI...                                      |"
	@echo "|                                                                             |"
	@echo "| 🌐 Open your browser to http://127.0.0.1:8510                               |"
	@echo "==============================================================================="
	uv run python webapp/app.py

# Launch Marimo Slideshow
run-slides:
	@echo "==============================================================================="
	@echo "| 📊 Starting the Workshop Slideshow...                                       |"
	@echo "|                                                                             |"
	@echo "| 🌐 Open your browser to http://localhost:2718                               |"
	@echo "==============================================================================="
	uv run marimo edit slides/workshop.py -p 2718 --headless --no-token

# ==============================================================================
# Ingestion & Harvester
# ==============================================================================

# Launch the Vector Search news harvester daemon
harvest:
	@echo "==============================================================================="
	@echo "| 🚜 Starting the News Harvester & Vector Search Ingestion...                   |"
	@echo "==============================================================================="
	uv run python news_harvester/manager.py

# Launch the Vector Search Administrative CLI
# Usage: make vector-cli ARGS="list-objects --limit 5"
vector-cli:
	@echo "==============================================================================="
	@echo "| 🔍 Launching Vector Search CLI...                                             |"
	@echo "==============================================================================="
	@uv run python scripts/vector_cli.py $(ARGS)
# ==============================================================================
# Backend Deployment Targets
# ==============================================================================

# Deploy the agent remotely
# Usage: make deploy [AGENT_IDENTITY=true] [SECRETS="KEY=SECRET_ID,..."] - Set AGENT_IDENTITY=true to enable per-agent IAM identity (Preview)
deploy:
	# Export dependencies to requirements file using uv export.
	(uv export --no-hashes --no-header --no-dev --no-emit-project --no-annotate > app/app_utils/.requirements.txt 2>/dev/null || \
	uv export --no-hashes --no-header --no-dev --no-emit-project > app/app_utils/.requirements.txt) && \
	uv run -m app.app_utils.deploy \
		--source-packages=./app \
		--entrypoint-module=app.agent_engine_app \
		--entrypoint-object=agent_engine \
		--requirements-file=app/app_utils/.requirements.txt \
		$(if $(AGENT_IDENTITY),--agent-identity) \
		$(if $(filter command line,$(origin SECRETS)),--set-secrets="$(SECRETS)")

# Alias for 'make deploy' for backward compatibility
backend: deploy

# ==============================================================================
# Testing & Code Quality
# ==============================================================================

# Run unit and integration tests
test:
	uv sync --dev
	uv run pytest tests/unit && uv run pytest tests/integration

# ==============================================================================
# Agent Evaluation
# ==============================================================================

# Run agent evaluation using ADK eval
# Usage: make eval [EVALSET=tests/eval/evalsets/basic.evalset.json] [EVAL_CONFIG=tests/eval/eval_config.json]
eval:
	@echo "==============================================================================="
	@echo "| Running Agent Evaluation                                                    |"
	@echo "==============================================================================="
	uv sync --dev --extra eval
	uv run adk eval ./app $${EVALSET:-tests/eval/evalsets/basic.evalset.json} \
		$(if $(EVAL_CONFIG),--config_file_path=$(EVAL_CONFIG),$(if $(wildcard tests/eval/eval_config.json),--config_file_path=tests/eval/eval_config.json,))

# Run evaluation with all evalsets
eval-all:
	@echo "==============================================================================="
	@echo "| Running All Evalsets                                                        |"
	@echo "==============================================================================="
	@for evalset in tests/eval/evalsets/*.evalset.json; do \
		echo ""; \
		echo "▶ Running: $$evalset"; \
		$(MAKE) eval EVALSET=$$evalset || exit 1; \
	done
	@echo ""
	@echo "✅ All evalsets completed"

# Run code quality checks (codespell, ruff, ty)
lint:
	uv sync --dev --extra lint
	uv run codespell
	uv run ruff check . --diff
	uv run ruff format . --check --diff
	uv run ty check .

# ==============================================================================
# Gemini Enterprise Integration
# ==============================================================================

# Register the deployed agent to Gemini Enterprise
# Usage: make register-gemini-enterprise (interactive - will prompt for required details)
# For non-interactive use, set env vars: ID or GEMINI_ENTERPRISE_APP_ID (full GE resource name)
# Optional env vars: GEMINI_DISPLAY_NAME, GEMINI_DESCRIPTION, GEMINI_TOOL_DESCRIPTION, AGENT_ENGINE_ID
register-gemini-enterprise:
	@uvx agent-starter-pack@0.39.4 register-gemini-enterprise

# ==============================================================================
# Workshop Utilities
# ==============================================================================

# Save the current workspace to a module's solution directory
# Usage: make snapshot [module=01-foundation] [magic=true|false]
snapshot:
	@bash scripts/snapshot.sh "$(module)" "$${magic:-true}"

# Restores the workspace to the starting point of a module
# Usage: make catchup [module=02]
catchup:
	@bash scripts/catchup.sh "$(module)"

# Applies the solution of a module directly into the workspace
# Usage: make solve [module=02]
solve:
	@bash scripts/solve.sh "$(module)"