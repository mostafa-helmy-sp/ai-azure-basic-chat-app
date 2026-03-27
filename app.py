import os
import logging
import base64
import json

from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    force=True
)

# --- Load env ---
load_dotenv()

project_endpoint = os.getenv("AZURE_AI_PROJECT_ENDPOINT")
agent_deployment_name = os.getenv("AZURE_AI_AGENT_DEPLOYMENT_NAME")

# --- Azure Client ---
project_client = None
use_threads_api = False

try:
    project_client = AIProjectClient(
        endpoint=project_endpoint,
        credential=DefaultAzureCredential()
    )

    if hasattr(project_client.agents, "threads"):
        use_threads_api = True
        logging.info("Using NEW SDK (threads API)")
    else:
        logging.info("Using OLD SDK")

except Exception as e:
    logging.error(f"Failed to init Azure client: {e}", exc_info=True)

# --- Flask ---
app = Flask(__name__)

# --- In-memory store (replace with Redis/Cosmos in production) ---
user_threads = {}


# --- Auth helper ---
def get_user():
    header = request.headers.get("X-MS-CLIENT-PRINCIPAL")

    if not header:
        return None

    decoded = base64.b64decode(header)
    data = json.loads(decoded)

    return {
        "id": data.get("userId"),
        "name": data.get("userDetails"),
        "provider": data.get("identityProvider")
    }


# --- Routes ---

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/chat", methods=["POST"])
def chat():
    if not project_client:
        return jsonify({"error": "Azure client not initialized"}), 500

    user = get_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json
    content = data.get("content")

    if not content:
        return jsonify({"error": "Empty message"}), 400

    user_id = user["id"]

    try:
        # --- Get or create thread (server-side!) ---
        thread_id = user_threads.get(user_id)

        if not thread_id:
            logging.info(f"Creating thread for user {user['name']}")

            if use_threads_api:
                thread = project_client.agents.threads.create()
            else:
                thread = project_client.agents.create_thread()

            thread_id = thread.id
            user_threads[user_id] = thread_id

        # --- Add message (with user context) ---
        message_text = f"[User: {user['name']}] {content}"

        if use_threads_api:
            project_client.agents.threads.create_message(
                thread_id=thread_id,
                role="user",
                content=message_text,
            )
        else:
            project_client.agents.create_message(
                thread_id=thread_id,
                role="user",
                content=message_text,
            )

        # --- Run agent ---
        run = project_client.agents.create_and_process_run(
            thread_id=thread_id,
            agent_deployment_name=agent_deployment_name
        )

        if run.status == "failed":
            raise Exception(run.last_error)

        # --- Get messages ---
        if use_threads_api:
            messages = project_client.agents.threads.list_messages(thread_id)
        else:
            messages = project_client.agents.list_messages(thread_id=thread_id)

        # --- Extract last agent response ---
        last_text = None

        try:
            last_msg = messages.get_last_text_message_by_role("agent")
            if last_msg:
                last_text = last_msg.text.value
        except Exception:
            pass

        if not last_text:
            for msg in reversed(messages.data):
                if msg.role == "agent":
                    try:
                        last_text = msg.content[0].text.value
                        break
                    except Exception:
                        continue

        if not last_text:
            raise Exception("No response from agent")

        return jsonify({"response": last_text})

    except Exception as e:
        logging.error(f"Chat error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500