
.DEFAULT_GOAL := help

# ==============================================================================
# Help
# ==============================================================================

help:
	@echo "==============================================================================="
	@echo "| Agent Workshop Development Commands                                         |"
	@echo "==============================================================================="
	@echo "  make adk-web        - Launch local dev playground (Web UI & CLI)"
	@echo "  make run-webapp     - Launch the AI Newsroom Web UI (Module 04 demo)"
	@echo "  make run-slides     - Launch the interactive Marimo Workshop Slideshow"
	@echo "  make test           - Run unit and integration tests"
	@echo "  make eval           - Run agent evaluation using ADK evalsets"
	@echo "  make lint           - Run code quality checks"
	@echo "  make deploy         - Deploy the agent remotely"
	@echo "  make deploy-webapp  - Deploy the AI Newsroom webapp to Cloud Run"
	@echo "  make catchup        - Start over at the beginning of a specific module"
	@echo "  make solve          - Applies the solution of a module directly into the workspace"
	@echo "  make snapshot       - Save the current workspace to a module's solution directory"
	@echo "  make harvest        - Run the Vector Search News Harvester daemon"
	@echo "  make vector-cli     - Run the Vector Search diagnostic CLI (Usage: make vector-cli ARGS=\"...\")"
	@echo "  make gcloud-reset   - Reset gcloud account, ADC login, and quota project"
	@echo "==============================================================================="

# ==============================================================================
# Installation & Setup
# ==============================================================================

# Install dependencies using uv package manager
install:
	@command -v uv >/dev/null 2>&1 || { echo "uv is not installed. Installing uv..."; curl -LsSf https://astral.sh/uv/0.8.13/install.sh | sh; source $HOME/.local/bin/env; }
	uv sync

# Reset gcloud auth: switch account, run interactive ADC login, and pin the
# ADC quota project. Override defaults with:
#   make gcloud-reset GCLOUD_ACCOUNT=other@example.com GCLOUD_QUOTA_PROJECT=other-proj
GCLOUD_ACCOUNT ?= luis@luissala.altostrat.com
GCLOUD_QUOTA_PROJECT ?= shared-services-388522

gcloud-reset:
	@echo "==============================================================================="
	@echo "| 🔐 Resetting gcloud auth                                                    |"
	@echo "|    account:        $(GCLOUD_ACCOUNT)"
	@echo "|    quota project:  $(GCLOUD_QUOTA_PROJECT)"
	@echo "==============================================================================="
	gcloud config set account "$(GCLOUD_ACCOUNT)"
	gcloud auth application-default login
	gcloud auth application-default set-quota-project "$(GCLOUD_QUOTA_PROJECT)"
	@echo
	@echo "✅ Done. Active config:"
	@gcloud config list

# ==============================================================================
# Playground Targets
# ==============================================================================

# Launch local dev playground
adk-web:
	@echo "==============================================================================="
	@echo "| 🚀 Starting your agent playground...                                        |"
	@echo "|                                                                             |"
	@echo "| 💡 Try asking: What's the weather in San Francisco?                         |"
	@echo "|                                                                             |"
	@echo "| 🔍 IMPORTANT: Select the 'app' folder to interact with your agent.          |"
	@echo "==============================================================================="
	uv run adk web workspace --host 0.0.0.0 --port 8500 --reload_agents

# Launch Flask Newsroom UI (mod04 demo — embeds an ADK Runner into Flask)
run-webapp:
	@if ! grep -q "from utils.vector_store" workspace/app/agent.py 2>/dev/null; then \
		echo "==============================================================================="; \
		echo "| ⚠️  WARNING: workspace/app/agent.py doesn't import utils.vector_store.       |"; \
		echo "|                                                                             |"; \
		echo "| The AI Newsroom web app is the Module 04 demo — it expects an agent that   |"; \
		echo "| produces a structured NewspaperPage so the front-end can render the grid.  |"; \
		echo "| Earlier modules (01-03) won't render correctly here; use 'make adk-web'    |"; \
		echo "| (ADK Web) for those instead.                                                |"; \
		echo "|                                                                             |"; \
		echo "| To load the Module 04 solution:  make solve module=04                       |"; \
		echo "==============================================================================="; \
		echo; \
	fi
	@echo "==============================================================================="
	@echo "| 📰 Starting your AI Newsroom Web UI...                                      |"
	@echo "|                                                                             |"
	@echo "| 🌐 Open your browser to http://127.0.0.1:8510                               |"
	@echo "==============================================================================="
	uv run --no-sync python webapp/app.py


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
	# Export dependencies to requirements file, then deploy from workspace/ so ./app resolves correctly on Agent Engine.
	(uv export --no-hashes --no-header --no-dev --no-emit-project --no-annotate > workspace/app/app_utils/.requirements.txt 2>/dev/null || \
	uv export --no-hashes --no-header --no-dev --no-emit-project > workspace/app/app_utils/.requirements.txt) && \
	cd workspace && PYTHONPATH=. uv run python -m app.app_utils.deploy \
		--source-packages=./app \
		--entrypoint-module=app.agent_engine_app \
		--entrypoint-object=agent_engine \
		--requirements-file=app/app_utils/.requirements.txt \
		--display-name="workshop-agent-$$(hostname -s)" \
		$(if $(AGENT_IDENTITY),--agent-identity) \
		$(if $(filter command line,$(origin SECRETS)),--set-secrets="$(SECRETS)")

# Alias for 'make deploy' for backward compatibility
backend: deploy

# Deploy the AI Newsroom webapp to Cloud Run (connects to deployed Agent Engine)
# Requires: a successful `make deploy` first (needs deployment_metadata.json)
deploy-webapp:
	@if [ ! -f deployment_metadata.json ] && [ ! -f workspace/deployment_metadata.json ]; then \
		echo "❌ No deployment_metadata.json found. Run 'make deploy' first to deploy the agent."; \
		exit 1; \
	fi
	$(eval METADATA_FILE := $(shell [ -f workspace/deployment_metadata.json ] && echo workspace/deployment_metadata.json || echo deployment_metadata.json))
	$(eval ENGINE_ID := $(shell python3 -c "import json; print(json.load(open('$(METADATA_FILE)'))['remote_agent_engine_id'])"))
	@echo "==============================================================================="
	@echo "| 🚀 Deploying AI Newsroom to Cloud Run...                                     |"
	@echo "|                                                                             |"
	@echo "| Agent Engine: $(ENGINE_ID)"
	@echo "==============================================================================="
	gcloud run deploy newsroom-$$(hostname -s) \
		--source=webapp \
		--region=us-central1 \
		--allow-unauthenticated \
		--set-env-vars="AGENT_ENGINE_ID=$(ENGINE_ID)" \
		--memory=1Gi \
		--timeout=300

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