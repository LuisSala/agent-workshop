import os
import queue
import threading
import asyncio
import json
from flask import Flask, Response, render_template, request
import google.auth

# Guarantee Vertex AI routing config runs before invoking ADK tools natively
_, project_id = google.auth.default()
os.environ["GOOGLE_CLOUD_PROJECT"] = project_id
os.environ["GOOGLE_CLOUD_LOCATION"] = "global"

# Import ADK modules from the user's workspace
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from workspace.app.agent import root_agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

app = Flask(__name__)
session_service = InMemorySessionService()
runner = Runner(app_name="newsroom_ui", agent=root_agent, session_service=session_service)

def run_agent_in_thread(query: str, session_id: str, q: queue.Queue):
    async def _run():
        await session_service.create_session(app_name="newsroom_ui", user_id="demo_user", session_id=session_id)
        msg = types.Content(role="user", parts=[types.Part(text=query)])
        
        try:
            async for event in runner.run_async(user_id="demo_user", session_id=session_id, new_message=msg):
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
                    q.put({"type": "event", "author": event.author, "text": text, "tool": function_call})

            # Finished processing, get final state
            session = await session_service.get_session(session_id)
            compiled = session.state.get("compiled_news", {})
            
            # Extract JSON from Pydantic model
            if hasattr(compiled, "model_dump"):
                compiled_data = compiled.model_dump()
            elif hasattr(compiled, "dict"):
                compiled_data = compiled.dict()
            else:
                compiled_data = compiled
                
            q.put({"type": "finish", "data": compiled_data})
        except Exception as e:
            q.put({"type": "error", "message": str(e)})

    asyncio.run(_run())

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/stream')
def stream():
    query = request.args.get("query", "Look up latest AI news")
    import uuid
    session_id = str(uuid.uuid4())
    
    q = queue.Queue()
    threading.Thread(target=run_agent_in_thread, args=(query, session_id, q)).start()

    def generate():
        while True:
            item = q.get()
            # Send Server-Sent Event (SSE)
            yield f"data: {json.dumps(item)}\n\n"
            
            if item.get("type") in ["finish", "error"]:
                break

    return Response(generate(), mimetype="text/event-stream")

if __name__ == "__main__":
    app.run(debug=True, port=8510, host="0.0.0.0")
