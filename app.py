from flask import Flask, request, jsonify
import faiss
import openai
import numpy as np
import json
import os
from dotenv import load_dotenv
import datetime

# 環境変数ロード
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# FAQデータの読み込み
with open("faq_data.json", "r", encoding="utf-8") as f:
    faq_items = json.load(f)

questions = [item["question"] for item in faq_items]
answers = [item["answer"] for item in faq_items]
categories = [item.get("category", "") for item in faq_items]

# Embeddingモデル設定
EMBED_MODEL = "text-embedding-3-small"
def get_embedding(text):
    response = openai.embeddings.create(
        model=EMBED_MODEL,
        input=text
    )
    return np.array(response.data[0].embedding, dtype="float32")

# ベクトル構築
dimension = len(get_embedding("テスト"))
index = faiss.IndexFlatL2(dimension)
faq_vectors = np.array([get_embedding(q) for q in questions], dtype="float32")
index.add(faq_vectors)

# Flaskアプリ
app = Flask(__name__)

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
        suggestion = {
            "question": user_q,
            "count": 1,
            "status": "未回答"
        }
        suggestion_path = os.path.join(os.path.dirname(__file__), "faq_suggestions.json")
        if os.path.exists(suggestion_path):
            with open(suggestion_path, "r", encoding="utf-8") as f:
                existing = json.load(f)
        else:
            existing = []

        for item in existing:
            if item["question"] == user_q:
                item["count"] += 1
                break
        else:
            existing.append(suggestion)

        with open(suggestion_path, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)

        return jsonify({"response": "該当するFAQが見つかりませんでした。"})

    context = "\n".join([f"Q: {questions[i]}\nA: {answers[i]}" for i in matched[:3]])
    prompt = f"以下はFAQです。ユーザーの質問に答えてください。\n\n{context}\n\nユーザーの質問: {user_q}\n回答:"

    completion = openai.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )
    answer = completion.choices[0].message.content

    with open("log.txt", "a", encoding="utf-8") as log:
        log.write(f"[{datetime.datetime.now()}] Q: {user_q}\n")

    return jsonify({"response": answer})
