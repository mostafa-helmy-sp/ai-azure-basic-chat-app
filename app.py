import os
import logging
import base64
import json

from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

# --- Logging ---
logging.basicConfig(level=logging.INFO)

# --- Load env ---
load_dotenv()

project_endpoint=os.getenv("AZURE_AI_PROJECT_ENDPOINT")
subscription_id=os.getenv("AZURE_SUBSCRIPTION_ID")
resource_group_name=os.getenv("AZURE_RESOURCE_GROUP")
project_name=os.getenv("AZURE_AI_PROJECT_NAME")
agent_deployment_name = os.getenv("AZURE_AI_AGENT_DEPLOYMENT_NAME")

# --- Azure Client ---
project_client = AIProjectClient(
    endpoint=project_endpoint,
    #subscription_id=subscription_id,
    #resource_group_name=resource_group_name,
    #project_name=project_name,
    credential=DefaultAzureCredential()
)

# --- Flask ---
app = Flask(__name__)

# --- In-memory thread store ---
user_threads = {}

# --- Auth helper ---
def get_user():
    header = request.headers.get("X-MS-CLIENT-PRINCIPAL")
    if not header:
        return None

    decoded = base64.b64decode(header)
    data = json.loads(decoded)

    user_id = data.get("userId")

    # fallback for some providers
    if not user_id and "claims" in data:
        for claim in data["claims"]:
            if claim["typ"] in ["sub", "nameidentifier"]:
                user_id = claim["val"]

    return {
        "id": user_id,
        "name": data.get("userDetails") or "Unknown"
    }

# --- Routes ---

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/chat", methods=["POST"])
def chat():
    user = get_user()
    if not user or not user["id"]:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json
    content = data.get("content")

    if not content:
        return jsonify({"error": "Empty message"}), 400

    try:
        # --- Get/create thread ---
        thread_id = user_threads.get(user["id"])

        if not thread_id:
            thread = project_client.agents.threads.create()
            thread_id = thread.id
            user_threads[user["id"]] = thread_id

        # --- Add message ---
        project_client.agents.messages.create(
            thread_id=thread_id,
            role="user",
            content=content,
        )

        # --- Run agent ---
        run = project_client.agents.create_and_process_run(
            thread_id=thread_id,
            agent_deployment_name=agent_deployment_name
        )

        if run.status == "failed":
            raise Exception(run.last_error)

        # --- Get messages ---
        messages = project_client.agents.messages.list(thread_id=thread_id)

        # --- Extract latest agent message ---
        last_text = None

        for msg in reversed(list(messages)):
            if msg.role == "assistant" or msg.role == "agent":
                try:
                    last_text = msg.content[0].text.value
                    break
                except Exception:
                    continue

        if not last_text:
            raise Exception("No agent response found")

        return jsonify({"response": last_text})

    except Exception as e:
        logging.error(f"Chat error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500