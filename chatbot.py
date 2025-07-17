# from flask import Flask, request, jsonify
# from flask_cors import CORS
# from dotenv import load_dotenv
# import os
# import openai

# load_dotenv()  # Load from .env
# openai.api_key = os.environ.get("GROQ_API_KEY")

# app = Flask(__name__)
# CORS(app)

# @app.route("/chat", methods=["POST"])
# def chat():
#     data = request.json
#     user_message = data.get("message")

#     if not user_message:
#         return jsonify({"error": "No message provided"}), 400

#     try:
#         response = openai.ChatCompletion.create(
#             model="llama3-70b-8192",
#             messages=[
#                 {"role": "system", "content": "You are a helpful assistant that helps users spot job scams and stay safe."},
#                 {"role": "user", "content": user_message},
#             ]
#         )
#         reply = response.choices[0].message["content"]
#         return jsonify({"response": reply})
#     except Exception as e:
#         return jsonify({"error": str(e)}), 500

# if __name__ == "__main__":
#     app.run(debug=True, port=5001)


from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise EnvironmentError("GROQ_API_KEY not found in .env file")

# Initialize Flask app
app = Flask(__name__)

# Enable CORS for your frontend (Vite on port 5173)
CORS(app, origins=["http://localhost:5173"])

# Chat endpoint
@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_message = data.get("message")

    if not user_message:
        return jsonify({"error": "No message provided"}), 400

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    body = {
        "model": "llama3-70b-8192",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant specialized in job scam detection and job safety advice."},
            {"role": "user", "content": user_message}
        ]
    }

    response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=body)

    if response.status_code != 200:
        return jsonify({"error": "Failed to get response from Groq API", "details": response.text}), 500

    try:
        content = response.json()["choices"][0]["message"]["content"]
        return jsonify({"response": content})
    except Exception as e:
        return jsonify({"error": "Error parsing response", "details": str(e)}), 500

# Run the Flask app
if __name__ == "__main__":
    app.run(port=5001, debug=True)
