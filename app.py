from flask import Flask, request, jsonify, make_response
from flask_cors import CORS
from routes.auth import auth_bp
from dotenv import load_dotenv
import os
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from db import user_collection
from utils import hash_password
try:
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
    import torch
    import torch.nn.functional as F
    TRANSFORMERS_AVAILABLE = True
except ImportError as e:
    print(f"Transformers not available: {e}")
    TRANSFORMERS_AVAILABLE = False

# Load environment variables from .env
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
CORS(app, supports_credentials=True, resources={r"/*": {"origins": "*"}})

# Register authentication blueprint
app.register_blueprint(auth_bp, url_prefix="/auth")

# Load the job classifier model and tokenizer at startup
MODEL_DIR = os.path.join(os.path.dirname(__file__), 'job_classifier_model')
tokenizer = None
model = None

if TRANSFORMERS_AVAILABLE:
    try:
        print("Loading model and tokenizer...")
        tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR)
        model = AutoModelForSequenceClassification.from_pretrained(MODEL_DIR)
        model.eval()
        print("Model loaded successfully!")
    except Exception as e:
        print(f"Error loading model: {e}")
        print("Model will not be available for classification.")
else:
    print("Transformers library not available. Model will not be loaded.")

# Optional home route
@app.route("/")
def home():
    return {"message": "Welcome to JobGuard API"}

# ✅ Forgot Password Endpoint - Sends Email
@app.route("/api/forgot-password", methods=["POST"])
def forgot_password():

    data = request.get_json()
    email = data.get("email")

    if not email:
        return jsonify({"error": "Email is required"}), 400

    # Frontend reset link
    reset_link = f"http://localhost:5173/reset-password?email={email}"

    # Gmail SMTP setup
    sender_email = os.getenv("EMAIL_SENDER")
    sender_password = os.getenv("EMAIL_PASSWORD")

    message = MIMEMultipart()
    message["From"] = sender_email
    message["To"] = email
    message["Subject"] = "JobGuard Password Reset"
    body = f"Click this link to reset your password:\n\n{reset_link}"
    message.attach(MIMEText(body, "plain"))

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, email, message.as_string())
        server.quit()
        return jsonify({"message": "Reset link sent to your email."}), 200

    except Exception as e:
        print("SMTP error:", str(e))
        return jsonify({
            "error": "Failed to send email",
            "details": str(e)
        }), 500

# ✅ Reset Password Endpoint - Updates MongoDB
@app.route("/api/reset-password", methods=["POST"])
def reset_password():
    print("Reset password route hit")
    data = request.get_json()
    email = data.get("email")
    new_password = data.get("password")

    if not email or not new_password:
        return jsonify({"error": "Email and new password are required"}), 400
    print("All emails in DB:")
    for user in user_collection.find():
     print("-", user.get("email"))
    user = user_collection.find_one({"email": email})
    
    if not user:
        return jsonify({"error": "User not found"}), 404

    # Hash new password
    hashed_password = hash_password(new_password)

    # Update password in MongoDB
    user_collection.update_one(
        {"email": email},
        {"$set": {"password": hashed_password}}
    )

    return jsonify({"message": "Password has been reset successfully."}), 200

# ✅ Groq Chatbot Endpoint
@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_message = data.get("message", "")

    if not user_message:
        return jsonify({"error": "No message provided"}), 400

    headers = {
        "Authorization": f"Bearer {os.getenv('GROQ_API_KEY')}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "llama3-70b-8192",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": user_message}
        ]
    }

    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        json=payload,
        headers=headers
    )

    if response.status_code == 200:
        reply = response.json()["choices"][0]["message"]["content"]
        return jsonify({"response": reply})
    else:
        return jsonify({
            "error": "Failed to get response from Groq API",
            "details": response.text
        }), 500

@app.route("/api/classify", methods=["POST", "OPTIONS"])
def classify():
    if request.method == "OPTIONS":
        response = make_response('', 204)
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response
    data = request.get_json()
    text = data.get("text", "")
    if not text:
        return jsonify({"error": "No text provided"}), 400
    # Use Groq LLM for detection with confidence
    headers = {
        "Authorization": f"Bearer {os.getenv('GROQ_API_KEY')}",
        "Content-Type": "application/json"
    }
    prompt = (
        "You are a job scam detection expert. "
        "Analyze the following job description or URL and answer ONLY with:\n"
        "'scam' or 'legitimate', a confidence score from 0 to 100, and a short explanation.\n"
        "Format: <result> | <confidence> | <explanation>\n"
        f"Input: {text}\nOutput:"
    )
    payload = {
        "model": "llama3-70b-8192",
        "messages": [
            {"role": "system", "content": "You are a job scam detection expert."},
            {"role": "user", "content": prompt}
        ]
    }
    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        json=payload,
        headers=headers
    )
    if response.status_code == 200:
        reply = response.json()["choices"][0]["message"]["content"]
        # Example reply: "scam | 95 | This job asks for money upfront, which is a red flag."
        parts = reply.split('|')
        if len(parts) >= 2:
            result_type = parts[0].strip().lower()
            try:
                confidence = int(parts[1].strip())
            except Exception:
                confidence = 80
            explanation = '|'.join(parts[2:]).strip() if len(parts) > 2 else ''
            is_legit = 'legit' in result_type
            return jsonify({
                "result": result_type,
                "confidence": confidence,
                "explanation": explanation,
                "is_legit": is_legit
            })
        else:
            return jsonify({"error": "Could not parse LLM response.", "raw": reply}), 500
    else:
        return jsonify({
            "error": "Failed to get response from Groq API",
            "details": response.text
        }), 500

# ✅ Run the server
if __name__ == "__main__":
    app.run(debug=True)
