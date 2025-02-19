from flask import Flask, request, jsonify, session
from flask_cors import CORS
import google.generativeai as genai
import json
import logging
import os
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from dataclasses import dataclass
from typing import Dict, Any
import uuid

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'your-secret-key-change-in-production')
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=1)

CORS(app, resources={r"/*": {"origins": "*", "supports_credentials": True}})

def setup_logging():
    log_dir = 'logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    log_file = os.path.join(log_dir, 'app.log')
    handler = RotatingFileHandler(log_file, maxBytes=10000000, backupCount=5)
    handler.setFormatter(logging.Formatter(
        '[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
    ))
    
    app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)
    
    if app.debug:
        app.logger.addHandler(logging.StreamHandler())

setup_logging()

genai.configure(api_key="AIzaSyD2ArK74wBtL1ufYmpyrV2LqaOBrSi3mlU")

@dataclass
class TransactionSession:
    session_id: str
    conversation_history: str
    transaction_info: Dict[str, Any]
    created_at: datetime
    last_updated: datetime

def get_gemini_model():
    return genai.GenerativeModel(
        "gemini-pro",
        safety_settings=[
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_ONLY_HIGH"},
        ]
    )

def get_gemini_response(model, prompt):
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        app.logger.error(f"Gemini API error: {str(e)}")
        return '{}'

def get_transaction_details(model, prompt, conversation_history):
    system_prompt = """You are a precise and accurate banking assistant. Your role is to carefully extract and validate transaction details from user messages.

    IMPORTANT EXTRACTION RULES:
    1. For amounts:
       - Look for numbers preceded by Rs, ₹, rupees, or just numbers in context of money
       - Extract only the numeric value
       - Example: "transfer 100 rupees" → amount should be "100"
       
    2. For account numbers:
       - Look for numeric sequences near words like "account", "acc", "no", "number"
       - Extract only the numeric value
       - Example: "acc no 989898" → beneficiary_account should be "989898"
       
    3. For IFSC codes:
       - Look for alphanumeric codes near "ifsc"
       - Maintain original case
       - Example: "ifsc jhjh76" → beneficiary_ifsc should be "JHJH76"
       
    4. For names:
       - Look for names after words like "to", "for", "name"
       - Properly capitalize names
       - Example: "to naveen" → beneficiary_name should be "Naveen"

    Extract these fields from the user message:
    1. Beneficiary name
    2. Beneficiary account number
    3. Beneficiary IFSC code
    4. Amount
    5. Remarks (optional)
    
    Return ONLY a valid JSON object with these fields: 
    {
        "beneficiary_name": null or string,
        "beneficiary_account": null or string,
        "beneficiary_ifsc": null or string,
        "amount": null or string,
        "remarks": null or string
    }
    
    If a field is not found in the user message, keep it as null.
    Be precise and accurate in extraction. Do not guess or approximate values."""
    
    full_prompt = system_prompt + "\n\nConversation so far:\n" + conversation_history + "\n\nCurrent user message:\n" + prompt
    
    response = get_gemini_response(model, full_prompt)
    json_str = response.strip()
    if json_str.startswith("```json"):
        json_str = json_str[7:]
    if json_str.endswith("```"):
        json_str = json_str[:-3]
        
    transaction_info = json.loads(json_str.strip())
    return transaction_info

def format_confirmation(transaction_info):
    friendly_fields = {
        "beneficiary_name": "Recipient's Name",
        "beneficiary_account": "Recipient's Account",
        "beneficiary_ifsc": "Bank IFSC Code",
        "amount": "Amount",
        "remarks": "Remarks"
    }
    
    confirmation = "Here's a summary of your transaction details:\n\n"
    
    for field, value in transaction_info.items():
        if value:
            if field == "amount":
                confirmation += f"- {friendly_fields[field]}: Rs. {value}\n"
            else:
                confirmation += f"- {friendly_fields[field]}: {value}\n"
    
    confirmation += "\nWhat would you like to do?\n"
    confirmation += "1. Say 'confirm' to proceed with the transaction\n"
    confirmation += "2. Say 'change [field]' to modify any detail (e.g., 'change amount' or 'change name')\n"
    confirmation += "3. Say 'cancel' to cancel the transaction\n\n"
    confirmation += "Remember: Always verify all details carefully before confirming."
    
    return confirmation

@app.route('/api/transaction/start', methods=['POST'])
def start_transaction():
    try:
        session_id = str(uuid.uuid4())
        welcome_message = """Hello! I'm your secure banking assistant. I'll help you make a money transfer today.

To process your transfer, I'll need:
1. Recipient's name
2. Recipient's account number
3. Bank IFSC code
4. Amount to transfer

You can provide these details all at once or one by one. How may I help you today?

Remember: Always verify recipient details before confirming any transfer."""

        transaction_session = TransactionSession(
            session_id=session_id,
            conversation_history=f"System: {welcome_message}\n",
            transaction_info={
                "beneficiary_name": None,
                "beneficiary_account": None,
                "beneficiary_ifsc": None,
                "amount": None,
                "remarks": None
            },
            created_at=datetime.utcnow(),
            last_updated=datetime.utcnow()
        )
        
        session['transaction'] = {
            'session_id': transaction_session.session_id,
            'conversation_history': transaction_session.conversation_history,
            'transaction_info': transaction_session.transaction_info,
            'created_at': transaction_session.created_at.isoformat(),
            'last_updated': transaction_session.last_updated.isoformat()
        }
        
        app.logger.info(f"Started new transaction session: {session_id}")
        
        return jsonify({
            'message': 'Transaction session started',
            'session_id': session_id,
            'next_prompt': welcome_message
        })
    
    except Exception as e:
        app.logger.error(f"Error starting transaction: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/transaction/process', methods=['POST'])
def process_transaction():
    try:
        data = request.get_json()
        user_input = data.get('message', '').strip()
        session_id = data.get('session_id')
        
        if not user_input:
            return jsonify({'error': 'Message is required'}), 400
        
        if not session_id:
            return jsonify({'error': 'Session ID is required'}), 400
        
        transaction_data = session.get('transaction')
        if not transaction_data or transaction_data['session_id'] != session_id:
            return jsonify({'error': 'No active transaction session'}), 404
        
        transaction_data['conversation_history'] += f"User: {user_input}\n"
        
        user_input_lower = user_input.lower()
        
        # Handle cancellation
        if user_input_lower in ["exit", "quit", "cancel", "stop"]:
            session.pop('transaction', None)
            return jsonify({
                'message': 'Transaction cancelled. Stay safe and have a great day!',
                'transaction_info': transaction_data['transaction_info']
            })
        
        # Handle confirmation
        if user_input_lower == "confirm":
            missing_fields = [field for field, value in transaction_data['transaction_info'].items() 
                            if not value and field != 'remarks']
            if missing_fields:
                return jsonify({
                    'error': 'Incomplete transaction',
                    'missing_fields': missing_fields,
                    'next_prompt': "Please provide the following missing information: " + 
                                 ", ".join(missing_fields)
                }), 400
            else:
                session.pop('transaction', None)
                return jsonify({
                    'message': 'Transaction completed successfully. Thank you for using our service. Stay secure!',
                    'transaction_details': transaction_data['transaction_info']
                })
        
        # Handle field changes
        if user_input_lower.startswith("change "):
            field = user_input_lower[7:].strip()  # Remove "change " prefix
            field_mappings = {
                "name": "beneficiary_name",
                "account": "beneficiary_account",
                "ifsc": "beneficiary_ifsc",
                "amount": "amount",
                "remarks": "remarks"
            }
            
            if field in field_mappings:
                transaction_data['transaction_info'][field_mappings[field]] = None
                return jsonify({
                    'transaction_info': transaction_data['transaction_info'],
                    'next_prompt': f"Please provide the new {field}:"
                })
        
        # Process normal input
        model = get_gemini_model()
        updated_info = get_transaction_details(model, user_input, transaction_data['conversation_history'])
        
        # Update transaction info with new values
        for key, value in updated_info.items():
            if value:
                transaction_data['transaction_info'][key] = value
        
        transaction_data['last_updated'] = datetime.utcnow().isoformat()
        session['transaction'] = transaction_data
        
        # Check if all required fields are filled
        missing_fields = [field for field, value in transaction_data['transaction_info'].items() 
                         if not value and field != 'remarks']
        
        if not missing_fields:
            next_prompt = format_confirmation(transaction_data['transaction_info'])
        else:
            next_prompt = get_gemini_response(model, 
                "Based on this transaction info: " + json.dumps(transaction_data['transaction_info']) +
                "\nPolitely ask the user for the missing required information. Be specific about what's needed.")
        
        response = {
            'transaction_info': transaction_data['transaction_info'],
            'next_prompt': next_prompt
        }
        
        app.logger.info(f"Processed transaction message for session {session_id}")
        return jsonify(response)
    
    except Exception as e:
        app.logger.error(f"Error processing transaction: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy', 'timestamp': datetime.utcnow().isoformat()})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))