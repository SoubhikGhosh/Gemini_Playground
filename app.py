from flask import Flask, request, jsonify, session
from flask_cors import CORS
from functools import wraps
import google.generativeai as genai
import json
import logging
import os
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from dataclasses import dataclass
from typing import Optional, Dict, Any
import uuid

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'your-secret-key-change-in-production')
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=1)

# Simple CORS configuration to allow all origins
CORS(app, resources={
    r"/*": {
        "origins": "*",
        "supports_credentials": True
    }
})

# Configure logging
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

# Configure Gemini AI
# GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
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
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"},
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
    
    If a field is not found in the user message, keep it as null."""
    
    full_prompt = system_prompt + "\n\nConversation so far:\n" + conversation_history + "\n\nCurrent user message:\n" + prompt
    
    try:
        json_response = get_gemini_response(model, full_prompt)
        json_str = json_response.strip()
        if json_str.startswith("```json"):
            json_str = json_str[7:]
        if json_str.endswith("```"):
            json_str = json_str[:-3]
            
        transaction_info = json.loads(json_str.strip())
        return transaction_info
    except:
        return fallback_extraction(prompt)

def fallback_extraction(prompt):
    transaction_info = {
        "transaction_type": "IMPS",
        "beneficiary_name": None,
        "beneficiary_account": None,
        "beneficiary_ifsc": None,
        "amount": None,
        "from_account": None,
        "remarks": None
    }
    
    words = prompt.lower().split()
    
    if "imps" in words:
        transaction_info["transaction_type"] = "IMPS"
    elif "neft" in words:
        transaction_info["transaction_type"] = "NEFT"
    elif "rtgs" in words:
        transaction_info["transaction_type"] = "RTGS"
    
    if "to" in words:
        idx = words.index("to")
        if idx+1 < len(words):
            transaction_info["beneficiary_name"] = words[idx+1].capitalize()
    
    if "rs" in words or "rupees" in words or "₹" in words:
        for i, word in enumerate(words):
            if word in ["rs", "rupees", "₹"] and i+1 < len(words):
                try:
                    transaction_info["amount"] = words[i+1]
                except:
                    pass
    
    return transaction_info

def get_next_missing_field(transaction_info):
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
    
    if not transaction_info["remarks"]:
        return "remarks", field_prompts["remarks"]
    
    return None, None

def format_confirmation(transaction_info):
    friendly_fields = {
        "transaction_type": "Transaction Type",
        "beneficiary_name": "Recipient's Name",
        "beneficiary_account": "Recipient's Account",
        "beneficiary_ifsc": "Bank IFSC Code",
        "amount": "Amount",
        "from_account": "Your Account",
        "remarks": "Remarks"
    }
    
    confirmation = "Here's a summary of your transaction details:\n\n"
    
    for field, value in transaction_info.items():
        if value:
            if field == "amount":
                confirmation += f"- {friendly_fields[field]}: Rs. {value}\n"
            else:
                confirmation += f"- {friendly_fields[field]}: {value}\n"
    
    confirmation += "\nIs this information correct? You can:\n"
    confirmation += "- Say what you'd like to change\n"
    confirmation += "- Say 'complete' to finalize the transaction\n"
    confirmation += "- Say 'exit' to cancel\n"
    
    return confirmation

@app.route('/api/transaction/start', methods=['POST'])
def start_transaction():
    try:
        session_id = str(uuid.uuid4())
        transaction_session = TransactionSession(
            session_id=session_id,
            conversation_history="System: Welcome to your personal financial assistant!\n",
            transaction_info={
                "transaction_type": "IMPS",
                "beneficiary_name": None,
                "beneficiary_account": None,
                "beneficiary_ifsc": None,
                "amount": None,
                "from_account": None,
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
            'next_prompt': "How can I help you with your transaction today?"
        })
    
    except Exception as e:
        app.logger.error(f"Error starting transaction: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/transaction/process', methods=['POST'])
def process_transaction():
    try:
        data = request.get_json()
        user_input = data.get('message')
        session_id = data.get('session_id')
        
        if not user_input:
            return jsonify({'error': 'Message is required'}), 400
        
        if not session_id:
            return jsonify({'error': 'Session ID is required'}), 400
        
        transaction_data = session.get('transaction')
        if not transaction_data or transaction_data['session_id'] != session_id:
            return jsonify({'error': 'No active transaction session'}), 404
        
        transaction_data['conversation_history'] += f"User: {user_input}\n"
        
        if user_input.lower() in ["exit", "quit", "cancel", "stop"]:
            session.pop('transaction', None)
            return jsonify({'message': 'Transaction cancelled'})
        
        model = get_gemini_model()
        updated_info = get_transaction_details(model, user_input, transaction_data['conversation_history'])
        
        for key, value in updated_info.items():
            if value:
                transaction_data['transaction_info'][key] = value
        
        next_field, prompt = get_next_missing_field(transaction_data['transaction_info'])
        
        transaction_data['last_updated'] = datetime.utcnow().isoformat()
        session['transaction'] = transaction_data
        
        response = {
            'transaction_info': transaction_data['transaction_info'],
            'next_prompt': prompt if prompt else format_confirmation(transaction_data['transaction_info'])
        }
        
        app.logger.info(f"Processed transaction message for session {session_id}")
        return jsonify(response)
    
    except Exception as e:
        app.logger.error(f"Error processing transaction: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/transaction/complete', methods=['POST'])
def complete_transaction():
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        
        if not session_id:
            return jsonify({'error': 'Session ID is required'}), 400
        
        transaction_data = session.get('transaction')
        if not transaction_data or transaction_data['session_id'] != session_id:
            return jsonify({'error': 'No active transaction session'}), 404
        
        missing_fields = [field for field, value in transaction_data['transaction_info'].items() 
                         if not value and field != 'remarks']
        
        if missing_fields:
            return jsonify({
                'error': 'Incomplete transaction',
                'missing_fields': missing_fields
            }), 400
        
        session.pop('transaction', None)
        
        app.logger.info(f"Completed transaction for session {session_id}")
        
        return jsonify({
            'message': 'Transaction completed successfully',
            'transaction_details': transaction_data['transaction_info']
        })
    
    except Exception as e:
        app.logger.error(f"Error completing transaction: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy', 'timestamp': datetime.utcnow().isoformat()})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))