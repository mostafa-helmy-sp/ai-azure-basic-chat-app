import os
import logging
import base64
import json
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

# --- Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', force=True)

# --- Load env ---
load_dotenv()
project_endpoint = os.getenv("AZURE_AI_PROJECT_ENDPOINT")
agent_deployment_name = os.getenv("AZURE_AI_AGENT_DEPLOYMENT_NAME")

# --- Azure Client ---
project_client = None
try:
    project_client = AIProjectClient(
        endpoint=project_endpoint,
        credential=DefaultAzureCredential()
    )
    logging.info("AIProjectClient initialized successfully.")
except Exception as e:
    logging.error(f"FATAL: Could not initialize AIProjectClient: {e}", exc_info=True)


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
        logging.warning("Unauthorized access attempt.")
        return jsonify({"error": "Unauthorized"}), 401
    
    logging.info(f"Chat request for user: {user['id']}")

    data = request.json
    content = data.get("content")
    if not content:
        return jsonify({"error": "Empty message"}), 400

    try:
        # --- Get/create thread ---
        thread_id = user_threads.get(user["id"])
        if not thread_id:
            logging.info(f"No thread found for user {user['id']}. Creating new one.")
            # THIS IS THE CORRECTED METHOD NAME
            thread = project_client.agents.create_thread()
            thread_id = thread.id
            user_threads[user["id"]] = thread_id
            logging.info(f"New thread {thread_id} created for user {user['id']}.")

        # --- Add message ---
        logging.info(f"Adding message to thread {thread_id}...")
        # THIS IS THE CORRECTED METHOD NAME
        project_client.agents.create_message(
            thread_id=thread_id,
            role="user",
            content=content,
        )

        # --- Run agent ---
        logging.info(f"Running agent '{agent_deployment_name}' on thread {thread_id}...")
        run = project_client.agents.create_and_process_run(
            thread_id=thread_id,
            agent_deployment_name=agent_deployment_name
        )

        if run.status == "failed":
            logging.error(f"Agent run failed for thread {thread_id}: {run.last_error}")
            raise Exception(run.last_error)
        
        logging.info(f"Agent run successful. Status: {run.status}")

        # --- Get messages ---
        # THIS IS THE CORRECTED METHOD NAME
        messages = project_client.agents.list_messages(thread_id=thread_id)
        
        # --- Extract latest agent message ---
        # This is a more direct and reliable way to get the last message
        last_agent_message = messages.get_last_text_message_by_role("agent")
        
        if not last_agent_message:
            logging.error(f"No agent response found in thread {thread_id} after successful run.")
            raise Exception("No agent response found")

        last_text = last_agent_message.text.value
        logging.info("Successfully retrieved agent response.")

        return jsonify({"response": last_text, "thread_id": thread_id})

    except Exception as e:
        logging.error(f"Chat error for user {user['id']}: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

