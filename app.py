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

from product_film_matcher import ProductFilmMatcher
from keyword_filter import extract_keywords

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

# system prompt 読み込み
with open("system_prompt.txt", "r", encoding="utf-8") as f:
    system_prompt = f.read()

# FAQデータ読み込み
with open("data/faq.json", "r", encoding="utf-8") as f:
    faq_items = json.load(f)

questions = [item["question"] for item in faq_items]
answers = [item["answer"] for item in faq_items]
categories = [item.get("category", "") for item in faq_items]

# knowledgeデータ読み込み
with open("data/knowledge.json", "r", encoding="utf-8") as f:
    knowledge_dict = json.load(f)

knowledge_texts = []
knowledge_keys = []

for category, entries in knowledge_dict.items():
    for entry in entries:
        knowledge_texts.append(f"{category}: {entry}")
        knowledge_keys.append(category)

# Embedding設定
EMBED_MODEL = "text-embedding-3-small"
def get_embedding(text):
    response = openai.embeddings.create(
        model=EMBED_MODEL,
        input=text
    )
    return np.array(response.data[0].embedding, dtype="float32")

dimension = len(get_embedding("テスト"))

# FAQベクトル化
faq_vectors = np.array([get_embedding(q) for q in questions], dtype="float32")
faq_index = faiss.IndexFlatL2(dimension)
faq_index.add(faq_vectors)

# Knowledgeベクトル化
knowledge_vectors = np.array([get_embedding(text) for text in knowledge_texts], dtype="float32")
knowledge_index = faiss.IndexFlatL2(dimension)
knowledge_index.add(knowledge_vectors)

# Flaskアプリ
app = Flask(__name__)
CORS(app)

# マッチャー初期化
pf_matcher = ProductFilmMatcher("data/product_film_color_matrix.json")

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

    # FAQ類似検索
    D, I = faq_index.search(np.array([q_vector]), k=5)
    matched = [i for i in I[0] if category_filter is None or categories[i] == category_filter]
    faq_context = "\n".join([f"Q: {questions[i]}\nA: {answers[i]}" for i in matched[:3]])

    # Knowledge類似検索
    K_D, K_I = knowledge_index.search(np.array([q_vector]), k=3)
    knowledge_context = "\n".join([knowledge_texts[i] for i in K_I[0]])

    # フィルターマッチによる返答（該当しない場合のみGPTへ）
    if not matched:
        info = extract_keywords(user_q)

        if info["product"] and info["film"]:
            result = pf_matcher.get_colors_for_film_in_product(info["product"], info["film"])
            if result["matched"]:
                return jsonify({"response": result["message"]})

        if info["product"]:
            result = pf_matcher.get_films_for_product(info["product"])
            if result["matched"]:
                return jsonify({"response": result["message"]})

        if info["film"]:
            result = pf_matcher.get_products_for_film(info["film"])
            if result["matched"]:
                return jsonify({"response": result["message"]})

        if info["color"]:
            result = pf_matcher.get_films_for_color(info["color"])
            if result["matched"]:
                return jsonify({"response": result["message"]})

    # GPTへプロンプト送信
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"""以下は製造元の知識ベースです：

{knowledge_context}

参考FAQ:
{faq_context}

ユーザーの質問: {user_q}
回答:"""}
    ]

    completion = openai.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        temperature=0.2,
    )
    answer = completion.choices[0].message.content

    # 未回答ログ処理
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
                body={"values": [[timestamp, user_q, 1, "未回答"]]}
            ).execute()
        except Exception as e:
            print(f"スプレッドシート書き込みエラー: {e}")

    return jsonify({"response": answer})
