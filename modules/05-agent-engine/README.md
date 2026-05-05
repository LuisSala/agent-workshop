# Module 05: Agent Engine

In this module, we move from running our agent locally to deploying it as a managed service on **Vertex AI Agent Engine**. Agent Engine is a fully managed Google Cloud service purpose-built for hosting ADK agents — no Dockerfiles, no infrastructure management. You upload your source code, and Google handles scaling, serving, and lifecycle management.

You will learn how the `AdkApp` deployment wrapper bridges your local ADK `app` to Agent Engine, configure your GCP environment, deploy with a single command, and verify the agent is live.

---

## Your Objectives

### 1. Understand the `AdkApp` Deployment Wrapper

Before deploying, examine how your agent gets packaged for Agent Engine. Open `workspace/app/agent_engine_app.py` and study its structure:

```python
from vertexai.agent_engines.templates.adk import AdkApp
from app.agent import app as adk_app

class AgentEngineApp(AdkApp):
    def set_up(self) -> None:
        """Lifecycle hook — runs once when the agent starts on Agent Engine."""
        vertexai.init()
        setup_telemetry()
        super().set_up()
        # ... logging setup

    def register_feedback(self, feedback: dict[str, Any]) -> None:
        """Custom operation — collect user feedback via Cloud Logging."""
        ...

    def register_operations(self) -> dict[str, list[str]]:
        """Expose custom operations alongside the default ADK ones."""
        operations = super().register_operations()
        operations[""] = operations.get("", []) + ["register_feedback"]
        return operations

agent_engine = AgentEngineApp(app=adk_app, ...)
```

**Key concepts:**
- **`AdkApp`** is the bridge class that wraps your ADK `app` for Agent Engine deployment.
- **`set_up()`** is a lifecycle hook that runs once when the engine initializes — use it for Vertex AI init, telemetry, and logging.
- **`register_operations()`** exposes callable methods on the deployed engine. The base class provides `stream_query`/`query` by default; here we add `register_feedback`.
- **`agent_engine`** is the module-level instance that `deploy.py` uploads to Vertex AI.

Also review the supporting files:
- **`app_utils/telemetry.py`** — Configures OpenTelemetry for Cloud Trace and optional prompt-response logging to GCS.
- **`app_utils/typing.py`** — Defines the `Feedback` Pydantic model for structured feedback logging.
- **`app_utils/deploy.py`** — The full CLI deployment script (creates/updates Agent Engine resources, handles secrets, scaling, IAM).

### 2. Configure GCP Prerequisites

Before deploying, ensure your Google Cloud environment is ready:

**Log in to the Google Cloud environment you want to deploy to:**
```bash
gcloud auth login
```
This opens a browser window for you to authenticate with your Google account. Make sure you log in with an account that has access to the GCP project you intend to deploy to.

**Set your project:**
```bash
gcloud config set project <YOUR_PROJECT_ID>
```

**Set Application Default Credentials (used by the deploy script):**
```bash
gcloud auth application-default login
```

**Enable required APIs:**
```bash
gcloud services enable aiplatform.googleapis.com logging.googleapis.com --project=<YOUR_PROJECT_ID>
```

**Verify your setup:**
```bash
gcloud config get-value project
gcloud auth application-default print-access-token > /dev/null && echo "✅ Auth OK"
```

### 3. Deploy with `make deploy`

With prerequisites in place, deploy your agent with a single command:

```bash
make deploy
```

**What happens under the hood:**
1. `uv export` generates a `requirements.txt` from your project dependencies
2. `deploy.py` uploads your `app/` source package to Vertex AI
3. Agent Engine builds a container, installs dependencies, and starts your `AgentEngineApp`
4. If an agent named `workshop-agent` already exists, it **updates** it; otherwise it **creates** a new one

⏱️ **This takes 3–5 minutes.** Watch the terminal for progress.

When complete, you'll see:
```
✅ Deployment successful!
Service Account: service-XXXXX@gcp-sa-aiplatform-re.iam.gserviceaccount.com

📊 Open Console Playground: https://console.cloud.google.com/vertex-ai/agents/...
```

A `deployment_metadata.json` file is written to your project root with the deployed engine ID:
```json
{
  "remote_agent_engine_id": "projects/.../reasoningEngines/...",
  "deployment_target": "agent_engine",
  "deployment_timestamp": "2026-..."
}
```

### 4. Verify the Deployment

**Option A: Console Playground**
Click the Console Playground URL printed after deployment. This opens a web chat interface where you can interact with your deployed agent directly. Try:
- *"What's the latest news on AI?"* — triggers the full news pipeline
- *"What time is it?"* — tests basic tool calling

**Option B: Check deployment metadata**
```bash
cat deployment_metadata.json
```
Confirm the `remote_agent_engine_id` is populated.

### 5. (Optional) Advanced Deployment Options

**Deploy with secrets** (e.g., API keys stored in Secret Manager):
```bash
make deploy SECRETS="API_KEY=my-secret-name"
```

**Deploy with per-agent IAM identity** (Preview feature):
```bash
make deploy AGENT_IDENTITY=true
```

**Register with Gemini Enterprise** (after deployment):
```bash
make register-gemini-enterprise
```

---

## 🆘 Getting Stuck?

If you fall behind or your code isn't working, you can instantly catch up to the beginning of the **next module** by running:

```bash
make catchup module=06
```
*(Note: This will completely overwrite your current `workspace/` with the known good baseline for the next module!)*

## References & Further Reading
*   **[Agent Engine Deployment Guide](https://google.github.io/adk-docs/deploy/agent-engine/)**: Official ADK documentation for deploying agents to Vertex AI Agent Engine, including the `AdkApp` class and deployment workflow.
*   **[Agent Engine Overview](https://cloud.google.com/vertex-ai/generative-ai/docs/agent-engine/overview)**: Google Cloud documentation covering Agent Engine concepts, pricing, and managed infrastructure.
*   **[Agent Starter Pack Deployment Guide](https://googlecloudplatform.github.io/agent-starter-pack/guide/deployment)**: The deployment guide for projects scaffolded with Agent Starter Pack, covering `deploy.py` and CI/CD setup.
*   **[Observability Guide](https://googlecloudplatform.github.io/agent-starter-pack/guide/observability)**: How to monitor deployed agents with Cloud Trace, BigQuery, and Cloud Logging.
