import os
import logging
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from openai import AzureOpenAI

# --- Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', force=True)

# --- Load env ---
load_dotenv()
project_endpoint = os.getenv("AZURE_AI_PROJECT_ENDPOINT")
agent_deployment_name = os.getenv("AZURE_AI_AGENT_DEPLOYMENT_NAME") # This is used as the 'model'

# --- Azure Clients ---
openai_client = None
try:
    project_client = AIProjectClient(
        endpoint=project_endpoint,
        credential=DefaultAzureCredential()
    )
    openai_client = project_client.get_openai_client()
    logging.info("Successfully created an authenticated OpenAI client for Responses API.")

except Exception as e:
    logging.error(f"FATAL: Could not initialize clients: {e}", exc_info=True)

# --- Flask ---
app = Flask(__name__)

# --- Routes ---
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    if not openai_client:
        return jsonify({"error": "OpenAI client is not initialized."}), 500

    data = request.json
    # The client now sends the entire message history
    messages = data.get("messages")

    if not messages:
        return jsonify({"error": "Empty message list"}), 400

    try:
        logging.info(f"Received {len(messages)} messages. Calling chat completions API...")
        
        # --- Call the Responses API ---
        completion = openai_client.chat.completions.create(
            model=agent_deployment_name, # The agent deployment is the model
            messages=messages
        )

        logging.info("API call successful.")
        
        response_message = completion.choices[0].message

        if not response_message or not response_message.content:
             raise Exception("API returned an empty response.")

        # The response from the API is a message object that can be sent back to the client
        return jsonify(response_message)

    except Exception as e:
        logging.error(f"Chat error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500
