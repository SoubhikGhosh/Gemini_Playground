# app.py
from dotenv import load_dotenv
import os
import logging
import time
import re
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
import google.generativeai as genai
import io
from PIL import Image  # Import the Image class from PIL
import json
import traceback
from functools import lru_cache

# Load environment variables from .env file
load_dotenv()


# Configuration Class
class Config:
    API_KEY = os.getenv("API_KEY")
    if not API_KEY:
        raise ValueError("API_KEY is not set in environment variables")
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"  # default false
    PORT = int(os.environ.get("PORT", 8080))  # Default to 8080 if PORT is not set
    ACCOUNT_BALANCE = float(os.getenv("ACCOUNT_BALANCE", 50000.00))  # Default balance
    MIN_TRANSFER_AMOUNT = float(os.getenv("MIN_TRANSFER_AMOUNT", 100.00))
    MAX_TRANSFER_AMOUNT = float(os.getenv("MAX_TRANSFER_AMOUNT", 25000.00))
    TRANSFER_LIMITS = {
        'min_transfer_amount': MIN_TRANSFER_AMOUNT,
        'max_transfer_amount': MAX_TRANSFER_AMOUNT
    }

    INITIAL_PROMPT = """You are 'FinAssist', a helpful and secure chatbot within the 'SecureBank' mobile banking application. Your primary purpose is to assist customers in making one-time fund transfers using RTGS, IMPS, or NEFT. You are guiding the user through a conversation to collect all the necessary information, ensuring accuracy and security. The user has already logged into the secure bank app, so you do not need to authenticate the user or ask any credential.

    After collecting all data, confirm the details with the user and then create a JSON object containing all data, and provide a URL to the confirmation page within the secure bank app

    Follow these steps:
    1. Start by greeting the customer politely and asking how you can help them today.
    2. If the user wants to make a one-time transfer, ask for the following information:
        * Beneficiary Name (as it appears on their bank account)
        * Beneficiary Account Number
        * Beneficiary Bank Name
        * Beneficiary Bank IFSC Code
        * Transfer Amount (₹)
        * Purpose of Transfer (Optional)
        * Preferred Transfer Method (IMPS/NEFT/RTGS)
        * MMID (Mobile Money Identifier) Number (only if IMPS is selected)

    3. After collecting all the information, display a summary to the user for confirmation, including:
        * User's Account Number (masked, e.g., XXXXXXXXXXXX1234),
        * Beneficiary Name,
        * Beneficiary Account Number,
        * Beneficiary Bank,
        * Beneficiary IFSC Code,
        * Transfer Amount,
        * Purpose of Transfer,
        * Transfer Method,
        * MMID (if IMPS is selected),
        * Estimated Transfer Time (based on method),
        * Transfer Fee (if applicable)

    4. Ask the user to confirm if the details are correct.

    5. If the user confirms, respond with a confirmation message, a reminder to keep their credentials safe, and the final JSON output along with a link to the confirmation page within the SecureBank app at the URL "/transfer/confirmation".

        If the transfer is confirmed, respond with the following JSON structure along with 201 status code instead of response:

        {
        "status": "success",
        "message": "Transfer request submitted successfully.",
        "data": {
            "userAccountNumber": (masked user account number, e.g., "XXXXXXXXXXXX1234"),
            "beneficiaryName": (string),
            "beneficiaryAccountNumber": (string),
            "beneficiaryBankName": (string),
            "beneficiaryIFSC": (string),
            "transferAmount": (number),
            "purposeOfTransfer": (string, can be null),
            "transferMethod": (string, "IMPS", "NEFT", or "RTGS"),
            "mmiNumber": (string, only if IMPS is selected, otherwise null),
            "timestamp": (current timestamp in ISO 8601 format),
            "confirmationPageLink": "/transfer/confirmation"
        }
    }

    6.  If the user wants to edit the detail, ask which detail needs to be edited and go back to the step where you are asking for the detail

    Remember: You are an AI and you can't perform the transfer. You are just collecting the data and constructing the JSON. Base on your analysis, you should respond with ONLY JSON and nothing else.
    """


# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes
app.config.from_object(Config)  # Load configuration

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize Gemini
try:
    genai.configure(api_key=app.config['API_KEY'])
except Exception as e:
    logger.exception(f"Failed to configure Gemini API: {e}")
    raise  # Terminate if Gemini can't be initialized


# --- Utility Functions (in a separate module or file if needed) ---
def validate_ifsc(ifsc):
    pattern = r"^[A-Z]{4}[0-9]{7}$"
    return bool(re.match(pattern, ifsc))


def validate_account_number(account_number):
    return account_number.isdigit() and 9 <= len(account_number) <= 18


def validate_transfer_amount(amount, account_balance, transfer_limits):
    try:
        amount = float(amount)
        if amount <= 0:
            return False, "Amount must be greater than zero."
        if amount > account_balance:
            return False, "Insufficient funds in your account."
        if amount > transfer_limits['max_transfer_amount']:
            return False, f"The maximum transfer amount is ₹{transfer_limits['max_transfer_amount']}."
        if amount < transfer_limits['min_transfer_amount']:
            return False, f"The minimum transfer amount is ₹{transfer_limits['min_transfer_amount']}."
        return True, None
    except ValueError:
        return False, "Invalid amount format."


def validate_mmid(mmid):
    return mmid.isdigit() and len(mmid) == 7


def sanitize_prompt(prompt):
    prompt = prompt.replace("{{", "").replace("}}", "")
    prompt = prompt.replace("/*", "").replace("*/", "")
    return prompt


def get_gemini_response(prompt, image_data=None):
    logger.info("Sending prompt to Gemini API: %s", prompt)
    start_time = time.time()  # Start measuring time

    try:
        if image_data:
            # Use gemini-1.5-flash for image input
            model = genai.GenerativeModel("gemini-1.5-flash")  # Or any other vision model

            # Prepare the image part. PIL is now used to open image from bytes.
            try:
                image = Image.open(io.BytesIO(image_data))  # open image from bytes
                contents = [prompt, image]
            except Exception as e:
                logger.error(f"Error opening or processing image: {e}")
                return "Error processing the image."
        else:
            # Use gemini-pro for text-only input
            model = genai.GenerativeModel("gemini-pro")
            contents = prompt

        response = model.generate_content(contents)
        response_text = response.text  # Extract the text from the response

    except genai.APIError as e:
        logger.error(f"Gemini API Error: {e}")
        response_text = "Sorry, the Gemini API is currently unavailable. Please try again later."
    except Exception as e:
        logger.exception(f"Unexpected error during Gemini API call: {e}")
        response_text = "Sorry, I encountered an unexpected error. Please try again later."
    finally:
        elapsed_time = time.time() - start_time  # Calculate the time taken
        logger.info("Time taken to get Gemini response: %.2f seconds", elapsed_time)

    return response_text


# --- Flask Routes ---
@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json()
        if not data:
            logger.warning("Empty JSON body in request")
            return jsonify({"error": "Empty request body"}), 400

        prompt = data.get("prompt", "")
        if not prompt:
            logger.warning("Prompt is missing in the request")
            return jsonify({"error": "Prompt is required"}), 400

        # Sanitize the prompt
        sanitized_prompt = sanitize_prompt(prompt)
        logger.info("Received and sanitized prompt: %s", sanitized_prompt)

        # Get the response from Gemini
        response = get_gemini_response(sanitized_prompt)

        # Check if the response indicates a successful transaction completion
        if "Transfer request submitted successfully" in response:  # Adjust condition if needed
            try:
                # Extract the JSON data
                response_json = json.loads(response)
                
                # Construct the desired JSON response
                transfer_data = {
                        "status": "success",
                        "message": "Transfer request submitted successfully.",
                        "data": response_json
                    }

                logger.info("Returning successful transfer response with code 201")
                return jsonify(transfer_data), 201  # Return JSON with 201 Created

            except (json.JSONDecodeError, TypeError) as e:
                logger.error(f"Error decoding or constructing JSON: {e}")
                return jsonify({"error": "Failed to construct successful transfer response"}), 500
        else:
            logger.info("Returning response from Gemini API")
            return jsonify({"response": response})

    except Exception as e:
        logger.exception("An error occurred while processing the request")
        return jsonify({"error": "An unexpected error occurred"}), 500


if __name__ == "__main__":
    app.run(debug=app.config['DEBUG'],
            host="0.0.0.0",
            port=app.config['PORT'])