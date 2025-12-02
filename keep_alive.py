from flask import Flask, jsonify, request
import requests
import os
from threading import Thread

app = Flask('')

# Render API 情報
SERVICE_ID = os.getenv("RENDER_SERVICE_ID")  # ← あなたのサービスIDに置き換え
RENDER_API_KEY = os.getenv("RENDER_API_KEY")  # Renderの環境変数に設定（安全！）

@app.route('/')
def home():
    return "I'm alive"

@app.route('/ping')
def ping():
    return jsonify({"status": "online"}), 200

@app.route('/resume', methods=['POST'])
def resume_service():
    """自分自身をRender API経由で再開させる"""
    url = f"https://api.render.com/v1/services/{SERVICE_ID}/resume"
    headers = {
        "accept": "application/json",
        "authorization": f"Bearer {RENDER_API_KEY}"
    }

    try:
        response = requests.post(url, headers=headers)
        if response.status_code == 202:
            return jsonify({"result": "Resuming service...", "status": 202})
        else:
            return jsonify({
                "result": "Unexpected response",
                "status_code": response.status_code,
                "body": response.text
            }), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()
