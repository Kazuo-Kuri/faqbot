from flask import Flask, request, jsonify
import faiss
import openai
import numpy as np
import os
import json
from datetime import datetime, timedelta, timezone
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
SHEET_NAME = "SUG"

# system_prompt.txt を読み込み
with open("system_prompt.txt", "r", encoding="utf-8") as f:
    system_prompt = f.read()

# FAQデータ読み込み
with open("data/faq.json", "r", encoding="utf-8") as f:
    faq_items = json.load(f)

faq_questions = [item["question"] for item in faq_items]
faq_answers = [item["answer"] for item in faq_items]
faq_categories = [item.get("category", "") for item in faq_items]

# knowledge.json 読み込み
with open("data/knowledge.json", "r", encoding="utf-8") as f:
    knowledge_items = json.load(f)

knowledge_contents = [f"{item['title']}：{item['content']}" for item in knowledge_items]

# metadata.json 読み込み
with open("data/metadata.json", "r", encoding="utf-8") as f:
    metadata = json.load(f)

metadata_note = f"【ファイル情報】{metadata.get('title', '')}（種類：{metadata.get('type', '')}、優先度：{metadata.get('priority', '')}）"

# 検索対象とソース区分
search_texts = faq_questions + knowledge_contents + [metadata_note]
source_flags = ["faq"] * len(faq_questions) + ["knowledge"] * len(knowledge_contents) + ["metadata"]

# Embedding設定
EMBED_MODEL = "text-embedding-3-small"
def get_embedding(text):
    response = openai.embeddings.create(
        model=EMBED_MODEL,
        input=text
    )
    return np.array(response.data[0].embedding, dtype="float32")

vectors = np.array([get_embedding(text) for text in search_texts], dtype="float32")
dimension = vectors.shape[1]
index = faiss.IndexFlatL2(dimension)
index.add(vectors)

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
    D, I = index.search(np.array([q_vector]), k=7)

    faq_context = []
    reference_context = []

    for idx in I[0]:
        source = source_flags[idx]
        if source == "faq":
            if category_filter is None or faq_categories[idx] == category_filter:
                faq_context.append(f"Q: {faq_questions[idx]}\nA: {faq_answers[idx]}")
        elif source == "knowledge":
            ref_idx = idx - len(faq_questions)
            reference_context.append(f"【参考知識】{knowledge_contents[ref_idx]}")
        elif source == "metadata":
            reference_context.append(metadata_note)

    faq_part = "\n\n".join(faq_context[:3]) if faq_context else "該当するFAQは見つかりませんでした。"
    ref_part = "\n".join(reference_context[:2]) if reference_context else ""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"""以下は当社のFAQおよび参考情報です。これらを参考に、ユーザーの質問に製造元の立場でご回答ください。

【FAQ】
{faq_part}

【参考情報】
{ref_part}

ユーザーの質問: {user_q}
回答:"""}
    ]

    completion = openai.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        temperature=0.2,
    )
    answer = completion.choices[0].message.content

    # 未回答として記録（「申し訳」など含む場合）
    unanswered_keywords = ["申し訳", "確認", "調査"]
    if any(keyword in answer for keyword in unanswered_keywords):
        try:
            jst = timezone(timedelta(hours=9))
            timestamp = datetime.now(jst).isoformat()

            service = build("sheets", "v4", credentials=credentials)
            sheet = service.spreadsheets()
            sheet.values().append(
                spreadsheetId=SPREADSHEET_ID,
                range=f"{SHEET_NAME}!A:D",
                valueInputOption="USER_ENTERED",
                body={
                    "values": [[
                        timestamp,
                        user_q,
                        1,
                        "未回答"
                    ]]
                }
            ).execute()
        except Exception as e:
            print(f"スプレッドシート書き込みエラー: {e}")

    return jsonify({"response": answer})
