import os
import queue
import threading
import asyncio
import json
from flask import Flask, Response, render_template, request
import google.auth

# Guarantee Vertex AI routing config runs before invoking ADK tools natively
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

# Import ADK modules from the user's workspace
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from workspace.app.agent import news_workflow, archive_workflow
from workspace.app.app_utils.telemetry import setup_telemetry
from workspace.app.app_utils.typing import Feedback
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

# Configure OpenTelemetry / GenAI telemetry. No-op locally without
# LOGS_BUCKET_NAME; in production it ships traces to Cloud Trace and
# (optionally) prompt-response payloads to GCS. Same helper that ships
# with the agents-cli scaffold's app/app_utils/telemetry.py.
setup_telemetry()

# Cloud Logging client for structured run/feedback events. Falls back to
# stdout when running locally without GCP credentials so students can
# develop without configuring auth.
try:
    from google.cloud import logging as google_cloud_logging
    _logging_client = google_cloud_logging.Client()
    _cloud_logger = _logging_client.logger("ai_newsroom")
except Exception as _e:
    print(f"[webapp] Cloud Logging unavailable, falling back to stdout: {_e}")
    _cloud_logger = None


def log_event(payload: dict, severity: str = "INFO") -> None:
    """Structured-log an event. Cloud Logging when available, stdout otherwise."""
    if _cloud_logger is not None:
        _cloud_logger.log_struct(payload, severity=severity)
    else:
        print(f"[webapp:{severity}] {payload}")


# Map the UI's `?mode=` param to a Workflow. The agent layer defines two
# independent workflows (see workspace/app/agent.py); the application
# layer picks the right one for each request based on which UI button
# the user clicked. Unknown modes fall back to the news pipeline.
WORKFLOWS = {
    "news": news_workflow,
    "archive": archive_workflow,
}

DATA_DIR = os.path.join(os.path.dirname(__file__), "data", "newsletters")
os.makedirs(DATA_DIR, exist_ok=True)

app = Flask(__name__)
session_service = InMemorySessionService()


def run_agent_in_thread(query: str, session_id: str, mode: str, q: queue.Queue):
    async def _run():
        await session_service.create_session(
            app_name="newsroom_ui", user_id="demo_user", session_id=session_id
        )

        # Pick the workflow per request based on the UI mode. This is the
        # core of the embedded-Runner pattern: the front-end already knows
        # the user's intent (which button was clicked), so we use that
        # signal directly rather than asking the agent to re-derive it.
        agent = WORKFLOWS.get(mode, news_workflow)

        # Instantiate runner per-thread to prevent async global state conflicts
        runner = Runner(
            app_name="newsroom_ui", agent=agent, session_service=session_service
        )
        
        msg = types.Content(role="user", parts=[types.Part(text=query)])

        try:
            async for event in runner.run_async(
                user_id="demo_user", session_id=session_id, new_message=msg
            ):
                text = ""
                function_call = ""

                if hasattr(event, "content") and event.content:
                    for part in getattr(event.content, "parts", []):
                        if getattr(part, "function_call", None):
                            function_call = part.function_call.name
                            text = f"Tool Called: {function_call}"
                        elif getattr(part, "text", None):
                            text = part.text

                # Yield live action
                if text or function_call:
                    q.put(
                        {
                            "type": "event",
                            "author": event.author,
                            "text": text,
                            "tool": function_call,
                        }
                    )

            # Finished processing, get final state
            session = await session_service.get_session(
                app_name="newsroom_ui", user_id="demo_user", session_id=session_id
            )
            compiled = session.state.get("compiled_news", {})

            if hasattr(compiled, "model_dump"):
                compiled_data = compiled.model_dump()
            elif hasattr(compiled, "dict"):
                compiled_data = compiled.dict()
            else:
                compiled_data = compiled

            if compiled_data and "articles" in compiled_data and compiled_data["articles"]:
                import time, uuid
                filename = f"{uuid.uuid4()}.json"
                file_path = os.path.join(DATA_DIR, filename)
                with open(file_path, "w") as f:
                    json.dump({
                        "id": filename,
                        "query": query,
                        "mode": mode,
                        "timestamp": time.time(),
                        "data": compiled_data
                    }, f)
                log_event({
                    "event": "workflow_completed",
                    "mode": mode,
                    "query": query,
                    "session_id": session_id,
                    "newsletter_id": filename,
                    "article_count": len(compiled_data["articles"]),
                })

            q.put({"type": "finish", "data": compiled_data})
        except Exception as e:
            import traceback
            traceback.print_exc()
            
            # Extract nested exceptions from ExceptionGroup
            if hasattr(e, 'exceptions'):
                def get_all_msgs(exc):
                    msgs = []
                    if hasattr(exc, 'exceptions'):
                        for sub_exc in exc.exceptions:
                            msgs.extend(get_all_msgs(sub_exc))
                    else:
                        msgs.append(str(exc))
                    return msgs
                
                msg = "; ".join(get_all_msgs(e))
                q.put({"type": "error", "message": "Parallel Execution Failed: " + msg})
            else:
                q.put({"type": "error", "message": str(e)})

    asyncio.run(_run())


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/stream")
def stream():
    query = request.args.get("query", "Look up latest AI news")
    mode = request.args.get("mode", "news")
    import uuid

    session_id = str(uuid.uuid4())

    q = queue.Queue()
    threading.Thread(target=run_agent_in_thread, args=(query, session_id, mode, q)).start()

    def generate():
        while True:
            item = q.get()
            # Send Server-Sent Event (SSE)
            yield f"data: {json.dumps(item)}\n\n"

            if item.get("type") in ["finish", "error"]:
                break

    return Response(generate(), mimetype="text/event-stream")


@app.route("/api/history")
def get_history():
    history = []
    if os.path.exists(DATA_DIR):
        for filename in os.listdir(DATA_DIR):
            if filename.endswith(".json"):
                try:
                    with open(os.path.join(DATA_DIR, filename), "r") as f:
                        data = json.load(f)
                        history.append({
                            "id": data.get("id"),
                            "query": data.get("query"),
                            "mode": data.get("mode", "news"),
                            "timestamp": data.get("timestamp", 0)
                        })
                except Exception as e:
                    print(f"Error reading {filename}: {e}")
    # Sort by timestamp descending
    history.sort(key=lambda x: x["timestamp"], reverse=True)
    return Response(json.dumps(history), mimetype="application/json")


@app.route("/api/history/<file_id>")
def get_history_item(file_id):
    file_path = os.path.join(DATA_DIR, file_id)
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            return Response(f.read(), mimetype="application/json")
    return Response("Not found", status=404)


@app.route("/feedback", methods=["POST"])
def collect_feedback():
    """Capture thumbs-up/down (and optional free-text) from the article modal.

    The Pydantic Feedback model lives in workspace/app/app_utils/typing.py
    (same shape the agents-cli scaffold ships with). It auto-generates
    user_id and session_id when absent so the front-end can fire-and-forget.
    """
    try:
        feedback = Feedback.model_validate(request.get_json() or {})
    except Exception as e:
        return Response(json.dumps({"status": "error", "message": str(e)}),
                        status=400, mimetype="application/json")
    log_event(feedback.model_dump(), severity="INFO")
    return Response(json.dumps({"status": "success"}), mimetype="application/json")


if __name__ == "__main__":
    app.run(debug=True, port=8510, host="0.0.0.0")
