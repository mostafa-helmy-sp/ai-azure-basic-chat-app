import os
import logging
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

# --- Routes ---
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    content = data.get("content")
    thread_id = data.get("thread_id")  # Get thread_id from the client

    if not content:
        return jsonify({"error": "Empty message"}), 400

    try:
        # --- Get or create thread ---
        if not thread_id:
            logging.info("No thread_id from client. Creating new one.")
            thread = project_client.agents.create_thread()
            thread_id = thread.id
            logging.info(f"New thread {thread_id} created.")

        # --- Add message ---
        logging.info(f"Adding message to thread {thread_id}...")
        project_client.agents.create_message(
            thread_id=thread_id,
            role="user",
            content=content,
        )

        # --- Run agent ---
        logging.info(f"Running agent on thread {thread_id}...")
        run = project_client.agents.create_and_process_run(
            thread_id=thread_id,
            agent_deployment_name=agent_deployment_name
        )

        if run.status == "failed":
            raise Exception(run.last_error)
        
        logging.info(f"Agent run successful. Status: {run.status}")

        messages = project_client.agents.list_messages(thread_id=thread_id)
        last_agent_message = messages.get_last_text_message_by_role("agent")
        
        if not last_agent_message:
            raise Exception("No agent response found")

        last_text = last_agent_message.text.value
        logging.info("Successfully retrieved agent response.")

        return jsonify({"response": last_text, "thread_id": thread_id})

    except Exception as e:
        logging.error(f"Chat error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500
