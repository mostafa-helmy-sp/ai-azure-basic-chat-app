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
    session_id = data.get("thread_id") 

    if not content:
        return jsonify({"error": "Empty message"}), 400

    try:
        if not session_id:
            logging.info("No session_id from client. Starting a new chat session.")
            chat_session = project_client.agents.start_chat_session()
            session_id = chat_session.id
            logging.info(f"New session {session_id} started.")

        logging.info(f"Getting response for session {session_id}...")
        
        response_data = project_client.agents.get_chat_session_response(
            message=content,
            chat_session_id=session_id
        )

        agent_reply = response_data.get("response")
        
        if not agent_reply:
            raise Exception("Agent run succeeded, but the response was empty.")

        logging.info("Successfully retrieved agent response.")

        return jsonify({"response": agent_reply, "thread_id": session_id})

    except Exception as e:
        logging.error(f"Chat error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

