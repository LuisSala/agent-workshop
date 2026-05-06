"""
Cloud Run version of the AI Newsroom webapp.
Connects to a deployed Agent Engine instance instead of importing agent code directly.

Usage:
    AGENT_ENGINE_ID=projects/.../reasoningEngines/... gunicorn webapp.app_remote:app
"""

import json
import os
import queue
import threading

from flask import Flask, Response, render_template, request
import google.auth
import vertexai
from vertexai import agent_engines

# Load env
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

# --- Agent Engine Configuration ---

AGENT_ENGINE_ID = os.environ.get("AGENT_ENGINE_ID")
if not AGENT_ENGINE_ID:
    raise RuntimeError(
        "AGENT_ENGINE_ID environment variable is required. "
        "Set it to the full resource name from deployment_metadata.json, e.g. "
        "projects/PROJECT/locations/LOCATION/reasoningEngines/ENGINE_ID"
    )

_, project_id = google.auth.default()
location = os.environ.get("GOOGLE_CLOUD_REGION", "us-central1")
vertexai.init(project=project_id, location=location)

agent_engine = agent_engines.get(AGENT_ENGINE_ID)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data", "newsletters")
os.makedirs(DATA_DIR, exist_ok=True)

app = Flask(__name__)


def run_agent_in_thread(query: str, q: queue.Queue):
    def _run_sync():
        try:
            for event_dict in agent_engine.stream_query(
                message=query, user_id="webapp_user"
            ):
                text = ""
                function_call = ""

                content = event_dict.get("content")
                if content and content.get("parts"):
                    for part in content["parts"]:
                        if part.get("functionCall"):
                            function_call = part["functionCall"].get("name", "")
                            text = f"Tool Called: {function_call}"
                        elif part.get("text"):
                            text = part["text"]

                author = event_dict.get("author", "agent")
                if text or function_call:
                    q.put(
                        {
                            "type": "event",
                            "author": author,
                            "text": text,
                            "tool": function_call,
                        }
                    )

            q.put({"type": "finish", "data": {}})

        except Exception as e:
            import traceback
            traceback.print_exc()
            q.put({"type": "error", "message": str(e)})

    _run_sync()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/stream")
def stream():
    query = request.args.get("query", "Look up latest AI news")
    q = queue.Queue()
    threading.Thread(target=run_agent_in_thread, args=(query, q), daemon=True).start()

    def generate():
        while True:
            item = q.get()
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
                            "timestamp": data.get("timestamp", 0)
                        })
                except Exception as e:
                    print(f"Error reading {filename}: {e}")
    history.sort(key=lambda x: x["timestamp"], reverse=True)
    return Response(json.dumps(history), mimetype="application/json")


@app.route("/api/history/<file_id>")
def get_history_item(file_id):
    file_path = os.path.join(DATA_DIR, file_id)
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            return Response(f.read(), mimetype="application/json")
    return Response("Not found", status=404)


if __name__ == "__main__":
    app.run(debug=True, port=8510, host="0.0.0.0")
