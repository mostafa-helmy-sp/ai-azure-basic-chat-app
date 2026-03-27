import os
import logging
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv
from openai import OpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

# --- Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', force=True)

# --- Load env ---
load_dotenv()

# Environment variables from the authoritative documentation you provided
FOUNDRY_RESOURCE_NAME = os.getenv("AZURE_FOUNDRY_RESOURCE_NAME")
PROJECT_NAME = os.getenv("AZURE_PROJECT_NAME")
APP_NAME = os.getenv("AZURE_APP_NAME")

# --- OpenAI Client for Foundry ---
client = None
if not all([FOUNDRY_RESOURCE_NAME, PROJECT_NAME, APP_NAME]):
    logging.error("FATAL: AZURE_FOUNDRY_RESOURCE_NAME, AZURE_PROJECT_NAME, and AZURE_APP_NAME are required.")
else:
    try:
        # Construct the BASE_URL exactly as specified in the docs
        BASE_URL = f"https://{FOUNDRY_RESOURCE_NAME}.services.ai.azure.com/api/projects/{PROJECT_NAME}/applications/{APP_NAME}/protocols/openai"

        # Create the OpenAI client using the exact pattern from the docs
        client = OpenAI(
            api_key=get_bearer_token_provider(DefaultAzureCredential(), "https://ai.azure.com/.default"),
            base_url=BASE_URL,
            default_query={"api-version": "2025-11-15-preview"}
        )
        logging.info("OpenAI client for Foundry initialized successfully, as per documentation.")

    except Exception as e:
        logging.error(f"FATAL: Could not initialize OpenAI client: {e}", exc_info=True)


# --- Flask ---
app = Flask(__name__)

# --- Routes ---
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    if not client:
        return jsonify({"error": "OpenAI client is not initialized."}), 500

    data = request.json
    messages = data.get("messages", [])

    if not messages:
        return jsonify({"error": "Empty message list"}), 400

    try:
        logging.info(f"Invoking agent '{APP_NAME}' via responses.create() with {len(messages)} messages in the 'input' parameter...")
        
        # --- THE CORRECTED METHOD CALL BASED ON YOUR DOCUMENTATION ---
        # The entire conversation history is passed to the 'input' parameter
        # because the API is stateless.
        response = client.responses.create(
            input=messages
        )

        logging.info("Agent invocation successful.")
        
        agent_reply = response.output_text

        if not agent_reply:
             raise Exception(f"Agent response did not contain 'output_text'. Full Response: {response}")

        # The client expects a JSON object with role and content
        return jsonify({"role": "assistant", "content": agent_reply})

    except Exception as e:
        logging.error(f"Chat error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

