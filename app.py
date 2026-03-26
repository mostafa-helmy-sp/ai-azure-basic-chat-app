import os
import logging
from flask import Flask, request, jsonify, render_template  # <-- render_template is now imported instead of render_template_string
from dotenv import load_dotenv
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

# --- SETUP ---
load_dotenv()
logger = logging.getLogger("azure.core.pipeline.policies.http_logging_policy")
logger.setLevel(logging.WARNING)

project_endpoint = os.getenv("AZURE_AI_PROJECT_ENDPOINT")
agent_deployment_name = os.getenv("AZURE_AI_AGENT_DEPLOYMENT_NAME")

project_client = None
try:
    project_client = AIProjectClient(
        endpoint=project_endpoint, credential=DefaultAzureCredential()
    )
except Exception as e:
    logging.error(f"Failed to initialize AIProjectClient: {e}")

app = Flask(__name__)

# --- API ENDPOINTS ---

@app.route("/")
def index():
    """Serves the main chat page from the template file."""
    # This line is the only functional change
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    """Handles the chat logic."""
    data = request.json
    content = data.get("content")
    thread_id = data.get("thread_id")

    if not project_client:
        return jsonify({"error": "Azure AI client is not initialized. Check server logs."}), 500
    if not content:
        return jsonify({"error": "Content cannot be empty"}), 400

    try:
        if not thread_id:
            thread = project_client.agents.create_thread()
            thread_id = thread.id

        project_client.agents.create_message(
            thread_id=thread_id,
            role="user",
            content=content,
        )

        run = project_client.agents.create_and_process_run(
            thread_id=thread_id, agent_deployment_name=agent_deployment_name
        )

        if run.status == "failed":
            raise Exception(run.last_error or "Agent run failed without a specific error.")

        messages = project_client.agents.list_messages(thread_id)
        last_msg = messages.get_last_text_message_by_role("agent")

        if not last_msg:
             raise Exception("Agent did not return a message.")

        return jsonify({
            "response": last_msg.text.value,
            "thread_id": thread_id
        })

    except Exception as e:
        logging.error(f"Error during chat processing: {e}")
        return jsonify({"error": str(e)}), 500
