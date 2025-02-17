from dotenv import load_dotenv
import os
import logging
import time
from flask import Flask, request, jsonify
from flask_cors import CORS
import google.generativeai as genai
import io
from PIL import Image  # Import the Image class from PIL
import json

# Load environment variables from .env file
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Get the API key from environment variables
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    raise ValueError("API_KEY is not set in environment variables")

genai.configure(api_key=API_KEY)

# Function to send prompts and image to Gemini API
def get_gemini_response(prompt, image_data=None):
    logger.info("Sending prompt to Gemini API: %s", prompt)
    start_time = time.time()  # Start measuring time

    model = genai.GenerativeModel("gemini-1.5-flash")  # Use gemini-pro-vision for image input

    if image_data:
        # Prepare the image part.  PIL is now used to open image from bytes.
        try:
            image = Image.open(io.BytesIO(image_data))  # open image from bytes
        except Exception as e:
            logger.error(f"Error opening image: {e}")
            return "Error processing the image."

        response = model.generate_content([prompt, image])
    else:
        model = genai.GenerativeModel("gemini-pro")  # Use gemini-pro for text-only input
        response = model.generate_content(prompt)
    
    elapsed_time = time.time() - start_time  # Calculate the time taken
    logger.info("Time taken to get Gemini response: %.2f seconds", elapsed_time)
    return response.text

# Endpoint to accept prompt and image
@app.route("/extract-aadhar", methods=["POST"])
def extract_aadhar():
    # Ensure the prompt and image are included in the request
    if 'image' not in request.files:
        logger.warning("No image file provided in the request")
        return jsonify({"error": "Image file is required"}), 400
    
    image_file = request.files['image']
    image_data = image_file.read() # read directly into bytes
    
    # Use a clear and specific prompt for Aadhar card information extraction
    prompt = """
    You are an expert in processing identity documents.  Analyze the provided image of an Indian Aadhar card and extract the following information:

    - Name: The full name of the cardholder.
    - Gender: The gender of the cardholder (Male or Female).
    - Date of Birth: The date of birth in DD/MM/YYYY format.
    - Aadhar Number: The 12-digit Aadhar number.

    Return the extracted information in JSON format.  If any information is not clearly visible or cannot be accurately extracted, mark the corresponding field as "null" in the JSON.

    Example JSON output:

    {
        "name": "John Doe",
        "gender": "Male",
        "dob": "01/01/1990",
        "aadhar_number": "123456789012"
    }

    Make sure that the JSON is valid and parsable.  Do not include any additional text or explanations.
    """

    # Send the image data along with the prompt to Gemini API
    response_text = get_gemini_response(prompt, image_data)  # Get the raw text response

    # Remove ```json and ``` from the response, if present
    response_text = response_text.replace("```json", "").replace("```", "")
    
    try:
        # Attempt to parse the JSON from the response
        json_response = json.loads(response_text)
        return jsonify(json_response)  # Return the parsed JSON directly
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON: {e}. Response text: {response_text}")
        return jsonify({"error": "Failed to decode JSON from the response", "raw_response": response_text}), 500

# Endpoint to accept prompt and image
@app.route("/extract-pan", methods=["POST"])
def extract_pan():
    # Ensure the prompt and image are included in the request
    if 'image' not in request.files:
        logger.warning("No image file provided in the request")
        return jsonify({"error": "Image file is required"}), 400
    
    image_file = request.files['image']
    image_data = image_file.read() # read directly into bytes
    
    # Use a clear and specific prompt for Aadhar card information extraction
    prompt = """
    You are an expert in processing identity documents.  Analyze the provided image of an Indian PAN card and extract the following information:

    - Name: The full name of the cardholder.
    - Date of Birth: The date of birth in DD/MM/YYYY format.
    - PAN: The 10-character PAN number.

    Return the extracted information in JSON format.  If any information is not clearly visible or cannot be accurately extracted, mark the corresponding field as "null" in the JSON.

    Example JSON output:

    {
        "name": "John Doe",
        "dob": "01/01/1990",
        "PAN": "123456789012"
    }

    Make sure that the JSON is valid and parsable.  Do not include any additional text or explanations.
    """

    # Send the image data along with the prompt to Gemini API
    response_text = get_gemini_response(prompt, image_data)  # Get the raw text response

    # Remove ```json and ``` from the response, if present
    response_text = response_text.replace("```json", "").replace("```", "")
    
    try:
        # Attempt to parse the JSON from the response
        json_response = json.loads(response_text)
        return jsonify(json_response)  # Return the parsed JSON directly
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON: {e}. Response text: {response_text}")
        return jsonify({"error": "Failed to decode JSON from the response", "raw_response": response_text}), 500

# Combined endpoint to accept image and determine document type
@app.route("/extract-info", methods=["POST"])
def extract_info():
    # Ensure the prompt and image are included in the request
    if 'image' not in request.files:
        logger.warning("No image file provided in the request")
        return jsonify({"error": "Image file is required"}), 400
    
    image_file = request.files['image']
    image_data = image_file.read() # read directly into bytes
    
    # General prompt to identify the document and extract information
    prompt = """
    You are an expert in processing identity documents.  Analyze the provided image of an Indian identity card and:

    1.  **Identify the document type:** Determine if it is an Aadhar card or a PAN card.
    2.  **Extract information based on the document type:**
        *   **If Aadhar card:** Extract Name, Gender, Date of Birth (DD/MM/YYYY), and Aadhar Number.
        *   **If PAN card:** Extract Name, Date of Birth (DD/MM/YYYY), and PAN number.
        *  **If other type:** Return `{"document_type": "unknown"}`

    Return the extracted information in JSON format, including the document_type field as either "aadhar" or "pan".  If any information is not clearly visible or cannot be accurately extracted, mark the corresponding field as "null" in the JSON.

    Example JSON output for Aadhar:

    {
        "document_type": "aadhar",
        "name": "John Doe",
        "gender": "Male",
        "dob": "01/01/1990",
        "aadhar_number": "123456789012"
    }

    Example JSON output for PAN:

    {
        "document_type": "pan",
        "name": "John Doe",
        "dob": "01/01/1990",
        "pan_number": "ABCDE1234F"
    }
    """

    # Send the image data along with the prompt to Gemini API
    response_text = get_gemini_response(prompt, image_data)  # Get the raw text response

    # Remove ```json and ``` from the response, if present
    response_text = response_text.replace("```json", "").replace("```", "")
    
    try:
        # Attempt to parse the JSON from the response
        json_response = json.loads(response_text)
        return jsonify(json_response)  # Return the parsed JSON directly
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON: {e}. Response text: {response_text}")
        return jsonify({"error": "Failed to decode JSON from the response", "raw_response": response_text}), 500

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    prompt = data.get("prompt", "")
    
    if not prompt:
        logger.warning("Prompt is missing in the request")
        return jsonify({"error": "Prompt is required"}), 400

    logger.info("Received prompt: %s", prompt)
    response = get_gemini_response(prompt)
    
    logger.info("Returning response from Gemini API")
    return jsonify({"response": response})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)