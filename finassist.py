import google.generativeai as genai
import os
import json
from datetime import datetime

# Configure Gemini API - Replace with your actual API key
# os.environ['GOOGLE_API_KEY'] = 'YOUR_GEMINI_API_KEY'  # Or set it directly: 
genai.configure(api_key="AIzaSyD2ArK74wBtL1ufYmpyrV2LqaOBrSi3mlU")
# genai.configure(api_key=os.environ['GOOGLE_API_KEY'])

model = genai.GenerativeModel('gemini-pro')

def generate_response(prompt, history=None, initial_prompt=None):
    """
    Generates a response from the Gemini Pro model, incorporating an initial prompt.
    """
    if history:
        # Prepend the initial prompt to the conversation history
        full_history = [{"role": "user", "parts": [initial_prompt]}] + history + [{"role": "user", "parts": [prompt]}]
    else:
        full_history = [{"role": "user", "parts": [initial_prompt]}, {"role": "user", "parts": [prompt]}]

    try:
        print(full_history)
        response = model.generate_content(full_history)
        if response and response.text:
           return response.text
        else:
           return "I encountered an issue generating a response. Please try again."

    except Exception as e:
        print(f"Error generating response: {e}")
        return "I'm sorry, I encountered an error. Please try again later."


def is_json(myjson):
  try:
    json_object = json.loads(myjson)
  except ValueError as e:
    return False
  return True

def mask_account_number(account_number):
    """Masks an account number, revealing only the last four digits."""
    if account_number and len(account_number) > 4:
        return "X" * (len(account_number) - 4) + account_number[-4:]
    return account_number  # Or handle shorter numbers differently

def chatbot():
    """Simulates the SecureBank FinAssist chatbot flow."""

    conversation_history = [] # List of dictionaries {"role": "user", "parts": ["..."]} and  {"role": "model", "parts": ["..."]}

    initial_prompt = """You are 'FinAssist', a helpful and secure chatbot within the 'SecureBank' mobile banking application. Your primary purpose is to assist customers in making one-time fund transfers using RTGS, IMPS, or NEFT. You are guiding the user through a conversation to collect all the necessary information, ensuring accuracy and security. The user has already logged into the secure bank app, so you do not need to authenticate the user or ask any credential.

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

    print("FinAssist: Hi there! Welcome to SecureBank. How can I help you with your transfer today?")
    conversation_history.append({"role": "model", "parts": ["Hi there! Welcome to SecureBank. How can I help you with your transfer today?"]})

    while True:
        user_input = input("You: ")
        conversation_history.append({"role": "user", "parts": [user_input]})

        if user_input.lower() == "exit":
            print("FinAssist: Okay, exiting FinAssist mode.") #Simulating exit, can expand with more functionalities
            break

        response = generate_response(user_input, conversation_history, initial_prompt)
        print("FinAssist:", response)

        conversation_history.append({"role": "model", "parts": [response]})

        # Check if the response is a JSON
        if is_json(response):
          # In Real application, you would extract information and process it appropriately instead of printing.
          print ("\n **JSON Detected**")
          #Example of processing the JSON
          try:
            json_data = json.loads(response)
            if json_data.get("status") == "success":
                print("Transfer request details (from JSON):")
                print(f"  Beneficiary Name: {json_data['data']['beneficiaryName']}")
                # Further processing and validation of the data can be performed here
          except json.JSONDecodeError as e:
            print(f"Error decoding JSON: {e}") # Handle potential JSON decoding errors.



if __name__ == "__main__":
    chatbot()