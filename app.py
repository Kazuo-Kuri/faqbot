from flask import Flask, request, jsonify
import faiss
import openai
import numpy as np
import json
import os
from dotenv import load_dotenv
import datetime
from flask_cors import CORS
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# === 初期化 ===
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# === FAQデータの読み込み ===
with open("faq_data.json", "r", encoding="utf-8") as f:
    faq_items = json.load(f)

questions = [item["question"] for item in faq_items]
answers = [item["answer"] for item in faq_items]
categories = [item.get("category", "") for item in faq_items]

# === Embedding 関連 ===
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

# === スプレッドシートに未回答を記録する関数 ===
SPREADSHEET_ID = '1asbjzo-G9I6SmztBG18iWuiTKetOJK20JwAyPF11fA4'
SHEET_NAME = 'Suggestions'
SUGGESTION_RANGE = f'{SHEET_NAME}!A2:C'


def append_to_sheet(question):
    creds = Credentials.from_service_account_file("credentials.json", scopes=["https://www.googleapis.com/auth/spreadsheets"])
    service = build("sheets", "v4", credentials=creds)
    sheet = service.spreadsheets()

    result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=SUGGESTION_RANGE).execute()
    existing = result.get("values", [])

    updated = False
    for i, row in enumerate(existing):
        if len(row) > 0 and row[0] == question:
            count = int(row[1]) + 1 if len(row) > 1 else 1
            sheet.values().update(
                spreadsheetId=SPREADSHEET_ID,
                range=f"{SHEET_NAME}!B{i+2}",
                valueInputOption="RAW",
                body={"values": [[count]]}
            ).execute()
            updated = True
            break

    if not updated:
        sheet.values().append(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{SHEET_NAME}!A2",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [[question, 1, "未回答"]]}
        ).execute()

# === Flask アプリ ===
app = Flask(__name__)
CORS(app)

@app.route("/", methods=["GET"])
def home():
    return "FAQ bot backend is running!"

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
        append_to_sheet(user_q)
        log_to_file(user_q, matched=False)
        return jsonify({"response": "申し訳ございません。FAQには該当の情報が含まれていません。詳細につきましては、メールもしくはお問合せフォームよりお問合せをお願いいたします。"})

    context = "\n".join([f"Q: {questions[i]}\nA: {answers[i]}" for i in matched[:3]])
    prompt = f"以下はFAQです。ユーザーの質問に答えてください。\n\n{context}\n\nユーザーの質問: {user_q}\n回答:"

    completion = openai.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )
    answer = completion.choices[0].message.content

    log_to_file(user_q, matched=True)
    return jsonify({"response": answer})


def log_to_file(user_q, matched):
    try:
        with open("log.txt", "a", encoding="utf-8") as log:
            log.write(f"[{datetime.datetime.now()}] ユーザーの質問: {user_q}\n")
            if not matched:
                log.write(f"[{datetime.datetime.now()}] 回答: 該当なし\n")
    except Exception as e:
        print(f"ログ書き込み失敗: {e}")

# エントリーポイント（Render等で使う場合）
if __name__ == "__main__":
    app.run(debug=True, port=8000)
