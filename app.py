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

AGENT_BASE_URL = os.getenv("AGENT_BASE_URL")

# --- OpenAI Client for Foundry ---
client = None
if not all([AGENT_BASE_URL]):
    logging.error("FATAL: AGENT_BASE_URL is required.")
else:
    try:

        # Create the OpenAI client exactly as specified in the documentation
        client = OpenAI(
            api_key=get_bearer_token_provider(DefaultAzureCredential(), "https://ai.azure.com/.default"),
            base_url=AGENT_BASE_URL,
            default_query={"api-version": "2025-11-15-preview"}
        )
        logging.info("OpenAI client for Foundry initialized successfully.")

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

    # Separate the last user message as the 'input' and the rest as 'history'
    current_input = messages[-1]['content']
    chat_history = messages[:-1]

    try:
        logging.info(f"Invoking agent via responses.create()...")
        
        # --- THIS IS THE CORRECT METHOD FROM YOUR DOCUMENTATION ---
        response = client.responses.create(
            input=current_input,
            chat_history=chat_history
        )

        logging.info("Agent invocation successful.")
        
        # The response object has an 'output_text' attribute
        agent_reply = response.output_text

        if not agent_reply:
             raise Exception(f"Agent response did not contain 'output_text'. Full Response: {response}")

        return jsonify({"role": "assistant", "content": agent_reply})

    except Exception as e:
        logging.error(f"Chat error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

