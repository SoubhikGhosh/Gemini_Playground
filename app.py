from dotenv import load_dotenv
import os
from flask import Flask, request, jsonify
from flask_cors import CORS
import google.generativeai as genai

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# Get the API key from environment variables
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    raise ValueError("API_KEY is not set in environment variables")

genai.configure(api_key=API_KEY)

# Function to send prompts to Gemini API
def get_gemini_response(prompt):
    model = genai.GenerativeModel("gemini-pro")
    response = model.generate_content(prompt)
    return response.text

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    prompt = data.get("prompt", "")
    if not prompt:
        return jsonify({"error": "Prompt is required"}), 400
    response = get_gemini_response(prompt)
    return jsonify({"response": response})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
