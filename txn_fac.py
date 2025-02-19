import google.generativeai as genai
import json
import re

# Set up your API key
API_KEY = "AIzaSyD2ArK74wBtL1ufYmpyrV2LqaOBrSi3mlU"  # Replace with your actual API key
genai.configure(api_key=API_KEY)

# Function to send prompts to Gemini API with robust error handling
def get_gemini_response(prompt):
    model = genai.GenerativeModel("gemini-pro",
                                safety_settings=[
                                    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"},
                                    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_ONLY_HIGH"},
                                    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_ONLY_HIGH"},
                                    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_ONLY_HIGH"},
                                ])
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Warning: Gemini API returned an error: {e}")
        # Return a safe fallback that won't break our JSON parsing
        return '{}'

def get_transaction_details(prompt, conversation_history):
    # Use Gemini to extract transaction details with a clear explanation that this is for legitimate financial services
    system_prompt = """You are assisting with a legitimate banking application that helps customers manage their finances. 
    This is a standard financial service functionality similar to what banks provide through their apps and websites.
    
    Extract the following financial transaction information from the user message:
    1. Transaction type (IMPS/NEFT/RTGS) - if not specified, default to "IMPS"
    2. Beneficiary name
    3. Beneficiary account number
    4. Beneficiary IFSC code
    5. Amount
    6. From account number
    7. Remarks (optional)
    
    Return only a valid JSON object with these fields: 
    {"transaction_type": null or string, "beneficiary_name": null or string, "beneficiary_account": null or string, 
    "beneficiary_ifsc": null or string, "amount": null or string, "from_account": null or string, "remarks": null or string}
    
    If a field is not found in the user message, keep it as null.
    Only respond with the JSON, no other text."""
    
    full_prompt = system_prompt + "\n\nConversation so far:\n" + conversation_history + "\n\nCurrent user message:\n" + prompt
    
    try:
        json_response = get_gemini_response(full_prompt)
        # Strip any potential extra text and get just the JSON part
        json_str = json_response.strip()
        if json_str.startswith("```json"):
            json_str = json_str[7:]
        if json_str.endswith("```"):
            json_str = json_str[:-3]
        
        # Handle empty responses (when safety filter triggers)
        if not json_str:
            return fallback_extraction(prompt)
            
        transaction_info = json.loads(json_str.strip())
        return transaction_info
    except json.JSONDecodeError:
        # Fallback to simple extraction if Gemini doesn't return valid JSON
        return fallback_extraction(prompt)

def interpret_edit_command(edit_command, current_transaction_info):
    # Use Gemini to interpret the edit command in natural language
    system_prompt = """You are an assistant helping with a financial transaction app.
    The user is trying to edit their transaction details. Based on their message, determine:
    1. Which field they want to edit (from the list below)
    2. What new value they want to set
    
    Current transaction information:
    {}
    
    Available fields:
    - beneficiary_name (who the money is being sent to)
    - beneficiary_account (account number of recipient)
    - beneficiary_ifsc (bank code of recipient)
    - amount (how much money to send)
    - from_account (user's account number)
    - remarks (optional note about the transaction)
    - transaction_type (IMPS, NEFT, or RTGS)
    
    Return your answer as a JSON object with "field" and "value" properties.
    Example: {{"field": "amount", "value": "5000"}}
    
    If you can't identify what the user wants to edit, return {{"field": null, "value": null}}
    """.format(json.dumps(current_transaction_info, indent=2))
    
    full_prompt = system_prompt + "\n\nUser edit command: " + edit_command
    
    try:
        result = get_gemini_response(full_prompt)
        edit_info = json.loads(result.strip())
        return edit_info
    except:
        return {"field": None, "value": None}

def fallback_extraction(prompt):
    # Simple rule-based extraction as fallback
    transaction_info = {
        "transaction_type": None,
        "beneficiary_name": None,
        "beneficiary_account": None,
        "beneficiary_ifsc": None,
        "amount": None,
        "from_account": None,
        "remarks": None
    }
    
    words = prompt.lower().split()
    
    # Basic transaction type detection
    if "imps" in words:
        transaction_info["transaction_type"] = "IMPS"
    elif "neft" in words:
        transaction_info["transaction_type"] = "NEFT"
    elif "rtgs" in words:
        transaction_info["transaction_type"] = "RTGS"
    else:
        # Default to IMPS
        transaction_info["transaction_type"] = "IMPS"
    
    # Very basic name extraction
    if "to" in words:
        idx = words.index("to")
        if idx+1 < len(words):
            transaction_info["beneficiary_name"] = words[idx+1].capitalize()
    
    # Basic amount extraction
    if "rs" in words or "rupees" in words or "₹" in words:
        for i, word in enumerate(words):
            if word in ["rs", "rupees", "₹"] and i+1 < len(words):
                try:
                    transaction_info["amount"] = words[i+1]
                except:
                    pass
    elif "send" in words:
        idx = words.index("send")
        if idx+1 < len(words):
            try:
                transaction_info["amount"] = words[idx+1]
            except:
                pass
    
    return transaction_info

def get_next_missing_field(transaction_info):
    """Returns the next missing field in a friendly format with appropriate prompt"""
    
    field_prompts = {
        "beneficiary_name": "Could you please tell me the name of the person you're sending money to?",
        "beneficiary_account": "What is the account number of the recipient?",
        "beneficiary_ifsc": "Could you provide the IFSC code of the recipient's bank?",
        "amount": "How much would you like to transfer?",
        "from_account": "Which account would you like to transfer from? Please provide your account number.",
        "remarks": "Would you like to add any remarks to this transaction? If not, just say 'no remarks'."
    }
    
    required_fields = ["beneficiary_name", "beneficiary_account", "beneficiary_ifsc", "amount", "from_account"]
    
    for field in required_fields:
        if not transaction_info[field]:
            return field, field_prompts[field]
    
    # If all required fields are filled, ask for remarks if not provided
    if not transaction_info["remarks"]:
        return "remarks", field_prompts["remarks"]
    
    return None, None

def format_confirmation(transaction_info):
    """Format the final confirmation message in a user-friendly way"""
    
    # Map technical fields to user-friendly descriptions
    friendly_fields = {
        "transaction_type": "Transaction Type",
        "beneficiary_name": "Recipient's Name",
        "beneficiary_account": "Recipient's Account",
        "beneficiary_ifsc": "Bank IFSC Code",
        "amount": "Amount",
        "from_account": "Your Account",
        "remarks": "Remarks"
    }
    
    confirmation = "Thank you! Here's a summary of your transaction details:\n\n"
    
    for field, value in transaction_info.items():
        if value:
            if field == "amount":
                confirmation += f"- {friendly_fields[field]}: Rs. {value}\n"
            else:
                confirmation += f"- {friendly_fields[field]}: {value}\n"
    
    confirmation += "\nIs this information correct? You can:\n"
    confirmation += "- Say what you'd like to change (e.g., 'change the amount to 5000' or 'the recipient is John')\n"
    confirmation += "- Say 'complete' to finalize the transaction\n"
    confirmation += "- Say 'exit' to cancel\n"
    
    return confirmation

def process_edit(edit_command, transaction_info):
    # First, try to interpret the edit using AI
    edit_info = interpret_edit_command(edit_command, transaction_info)
    
    if edit_info["field"] and edit_info["value"]:
        field = edit_info["field"]
        value = edit_info["value"]
        
        # If we found a valid field and value, update the transaction
        if field in transaction_info:
            transaction_info[field] = value
            friendly_field = field.replace('_', ' ')
            return f"I've updated the {friendly_field} to: {value}."
    
    # Handle case where we couldn't interpret the edit
    return "I'm not sure what you want to change. Could you please be more specific about what field you want to edit and what the new value should be?"

if __name__ == "__main__":
    print("Welcome to your personal financial assistant! I'm here to help you make transactions safely and easily.")
    print("You can transfer money to anyone you'd like. Let's get started!")
    
    transaction_info = {
        "transaction_type": "IMPS",  # Default to IMPS
        "beneficiary_name": None,
        "beneficiary_account": None,
        "beneficiary_ifsc": None,
        "amount": None,
        "from_account": None,
        "remarks": None
    }
    
    # Initialize conversation history
    conversation_history = "System: Welcome to your personal financial assistant!\n"
    current_field = None
    all_fields_collected = False
    
    while True:
        if not current_field:
            user_input = input("You: ")
        else:
            user_input = input("You: ")
        
        # Check for exit command first
        if user_input.lower() in ["exit", "quit", "cancel", "stop"]:
            print("Assistant: Thank you for using our services. Have a great day!")
            break
            
        # Check for completion command
        if user_input.lower() in ["complete", "confirm", "finished", "done", "yes"] and all_fields_collected:
            # Generate final JSON output
            print("Assistant: Your transaction has been submitted successfully! Here's the confirmation:")
            for field, value in transaction_info.items():
                if field == "amount" and value:
                    print(f"{field.replace('_', ' ').title()}: Rs. {value}")
                elif value:
                    print(f"{field.replace('_', ' ').title()}: {value}")
            print("Thank you for using our service. Have a great day!")
            break
        
        # Update conversation history
        conversation_history += "User: " + user_input + "\n"
        
        # Check if this is an edit command - now much more flexible
        is_edit = any(word in user_input.lower() for word in ["change", "edit", "update", "modify", "correct"])
        if is_edit:
            response = process_edit(user_input, transaction_info)
            print("Assistant:", response)
            
            # Check if all fields are filled after editing
            current_field, prompt = get_next_missing_field(transaction_info)
            if not current_field:
                all_fields_collected = True
                print("Assistant:", format_confirmation(transaction_info))
            else:
                all_fields_collected = False
                print("Assistant:", prompt)
            
            continue
            
        # Extract or update transaction details based on user input
        updated_info = get_transaction_details(user_input, conversation_history)
        
        # Update transaction info with any new details
        for key, value in updated_info.items():
            if value:
                transaction_info[key] = value
        
        # Get next missing field
        current_field, prompt = get_next_missing_field(transaction_info)
        
        # If all required fields are filled, confirm the transaction
        if not current_field or (current_field == "remarks" and user_input.lower() in ["no remarks", "none", "no"]):
            if current_field == "remarks" and user_input.lower() in ["no remarks", "none", "no"]:
                transaction_info["remarks"] = "None"
            
            all_fields_collected = True
            response = format_confirmation(transaction_info)
            print("Assistant:", response)
        else:
            # Ask for the next missing field
            print("Assistant:", prompt)
        
        # Update conversation history with assistant's response
        if all_fields_collected:
            conversation_history += "Assistant: " + format_confirmation(transaction_info) + "\n"
        else:
            conversation_history += "Assistant: " + prompt + "\n"