import os
from flask import Flask, request, jsonify, render_template
from openai import OpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

app = Flask(__name__)

# Configuration from Environment Variables
BASE_URL = os.getenv("FOUNDRY_BASE_URL")
API_VERSION = "2025-11-15-preview"

# Initialize Azure Authentication
credential = DefaultAzureCredential()
token_provider = get_bearer_token_provider(credential, "https://ai.azure.com/.default")

# Initialize OpenAI Client
client = OpenAI(
    api_key=token_provider(),
    base_url=BASE_URL,
    default_query={"api-version": API_VERSION}
)

@app.route('/')
def index():
    # Simple HTML interface
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    user_input = request.json.get("message")
    if not user_input:
        return jsonify({"error": "No message provided"}), 400

    try:
        # Call the Foundry Agent
        response = client.responses.create(
            input=user_input
        )
        return jsonify({"reply": response.output_text})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run()