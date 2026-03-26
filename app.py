import os
import logging
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    force=True
)

# --- Azure AI Client Setup ---
load_dotenv()
logger_azure = logging.getLogger("azure.core.pipeline.policies.http_logging_policy")
logger_azure.setLevel(logging.WARNING)

project_endpoint = os.getenv("AZURE_AI_PROJECT_ENDPOINT")
agent_deployment_name = os.getenv("AZURE_AI_AGENT_DEPLOYMENT_NAME")

project_client = None
try:
    logging.info("Attempting to initialize AIProjectClient...")
    project_client = AIProjectClient(
        endpoint=project_endpoint, credential=DefaultAzureCredential()
    )
    logging.info("AIProjectClient initialized successfully.")
except Exception as e:
    logging.error(f"FATAL: Failed to initialize AIProjectClient during startup: {e}", exc_info=True)

app = Flask(__name__)

# --- API Endpoints ---

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    logging.info("--- /chat endpoint hit ---")
    data = request.json
    content = data.get("content")
    thread_id = data.get("thread_id")
    logging.info(f"Received content: '{content}', thread_id: '{thread_id}'")

    if not project_client:
        logging.error("Cannot process chat: AI client is not initialized.")
        return jsonify({"error": "Azure AI client is not initialized. Check server startup logs."}), 500
    if not content:
        return jsonify({"error": "Content cannot be empty"}), 400

    try:
        if not thread_id:
            logging.info("No thread_id found, creating a new thread...")
            # CORRECTED LINE 1
            thread = project_client.agents.threads.create()
            thread_id = thread.id
            logging.info(f"New thread created with ID: {thread_id}")
        else:
            logging.info(f"Using existing thread with ID: {thread_id}")

        logging.info("Adding user message to the thread...")
        # CORRECTED LINE 2
        project_client.agents.threads.create_message(
            thread_id=thread_id,
            role="user",
            content=content,
        )
        logging.info("User message added successfully.")

        logging.info(f"Creating and processing run for agent: '{agent_deployment_name}'...")
        run = project_client.agents.create_and_process_run(
            thread_id=thread_id, agent_deployment_name=agent_deployment_name
        )
        logging.info(f"Agent run completed with status: '{run.status}'")

        if run.status == "failed":
            logging.error(f"Agent run failed. Error details: {run.last_error}")
            raise Exception(f"Agent run failed: {run.last_error}")

        logging.info("Listing messages from the thread...")
        # CORRECTED LINE 3
        messages = project_client.agents.threads.list_messages(thread_id)
        logging.info("Messages listed successfully.")

        logging.info("Searching for the last message from the agent...")
        last_msg = messages.get_last_text_message_by_role("agent")

        if not last_msg:
             logging.error("Agent run succeeded, but no agent message was found in the thread.")
             raise Exception("Agent did not return a message.")
        
        logging.info(f"Agent message found: '{last_msg.text.value[:80]}...'")

        return jsonify({
            "response": last_msg.text.value,
            "thread_id": thread_id
        })

    except Exception as e:
        logging.error(f"An exception occurred during chat processing: {e}", exc_info=True)
        return jsonify({"error": "An error occurred on the server. Check logs for details."}), 500

