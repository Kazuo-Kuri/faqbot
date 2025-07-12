from flask import Flask, request, jsonify
import faiss
import openai
import numpy as np
import os
import json
import datetime
from dotenv import load_dotenv
from flask_cors import CORS
from google.oauth2 import service_account
from googleapiclient.discovery import build
import base64

# 環境変数ロード
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# Google認証
encoded_cred = os.getenv("GOOGLE_CREDENTIALS_BASE64")
creds_json = base64.b64decode(encoded_cred).decode("utf-8")
creds_dict = json.loads(creds_json)

credentials = service_account.Credentials.from_service_account_info(
    creds_dict,
    scopes=["https://www.googleapis.com/auth/spreadsheets"]
)

SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
SHEET_NAME = "suggestions"  # スプレッドシートのシート名

# FAQデータ読み込み
with open("faq_data.json", "r", encoding="utf-8") as f:
    faq_items = json.load(f)

questions = [item["question"] for item in faq_items]
answers = [item["answer"] for item in faq_items]
categories = [item.get("category", "") for item in faq_items]

# Embedding設定
EMBED_MODEL = "text-embedding-3-small"
def get_embedding(text):
    response = openai.embeddings.create(
        model=EMBED_MODEL,
        input=text
    )
    return np.array(response.data[0].embedding, dtype="float32")

dimension = len(get_embedding("テスト"))
index = faiss.IndexFlatL2(dimension)
faq_vectors = np.array([get_embedding(q) for q in questions], dtype="float32")
index.add(faq_vectors)

# Flaskアプリ
app = Flask(__name__)
CORS(app)

@app.route("/", methods=["GET"])
def home():
    return "FAQ bot is running."

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_q = data.get("question")
    category_filter = data.get("category", None)

    if not user_q:
        return jsonify({"error": "質問がありません"}), 400

    q_vector = get_embedding(user_q)
    D, I = index.search(np.array([q_vector]), k=5)
    matched = [i for i in I[0] if category_filter is None or categories[i] == category_filter]

    if not matched:
        # Google Sheets に未回答として記録
        try:
            service = build("sheets", "v4", credentials=credentials)
            sheet = service.spreadsheets()
            sheet.values().append(
                spreadsheetId=SPREADSHEET_ID,
                range=f"{SHEET_NAME}!A:D",
                valueInputOption="USER_ENTERED",
                body={
                    "values": [[
                        datetime.datetime.now().isoformat(),
                        user_q,
                        1,
                        "未回答"
                    ]]
                }
            ).execute()
        except Exception as e:
            print(f"スプレッドシート書き込みエラー: {e}")

        return jsonify({"response": "該当するFAQが見つかりませんでした。"})

    # 回答生成
    context = "\n".join([f"Q: {questions[i]}\nA: {answers[i]}" for i in matched[:3]])
    prompt = f"以下はFAQです。ユーザーの質問に答えてください。\n\n{context}\n\nユーザーの質問: {user_q}\n回答:"

    completion = openai.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )
    answer = completion.choices[0].message.content

    return jsonify({"response": answer})
