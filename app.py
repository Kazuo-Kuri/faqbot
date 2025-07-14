from flask import Flask, request, jsonify
import faiss
import openai
import numpy as np
import os
import json
import time
from dotenv import load_dotenv
from flask_cors import CORS
from product_film_matcher import ProductFilmMatcher
from keyword_filter import extract_keywords
from query_expander import expand_query  # ✅ 追加

# 環境変数のロード
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

app = Flask(__name__)
CORS(app)

# セッション履歴管理
session_histories = {}
HISTORY_TTL = 1800  # 30分

def get_session_history(session_id):
    now = time.time()
    session = session_histories.get(session_id)
    if not session or now - session["last_active"] > HISTORY_TTL:
        session_histories[session_id] = {"last_active": now, "history": []}
    else:
        session_histories[session_id]["last_active"] = now
    return session_histories[session_id]["history"]

def add_to_session_history(session_id, role, content):
    history = get_session_history(session_id)
    history.append({"role": role, "content": content})
    if len(history) > 10:
        history[:] = history[-10:]

# データ読み込み
with open("data/faq.json", "r", encoding="utf-8") as f:
    faq_items = json.load(f)
questions = [item["question"] for item in faq_items]
answers = [item["answer"] for item in faq_items]

with open("data/knowledge.json", "r", encoding="utf-8") as f:
    knowledge_dict = json.load(f)
knowledge_texts = [f"{cat}: {entry}" for cat, entries in knowledge_dict.items() for entry in entries]

with open("system_prompt.txt", "r", encoding="utf-8") as f:
    base_prompt = f.read()

EMBED_MODEL = "text-embedding-3-small"
def get_embedding(text):
    response = openai.embeddings.create(model=EMBED_MODEL, input=text)
    return np.array(response.data[0].embedding, dtype="float32")

dimension = len(get_embedding("テスト"))
faq_vectors = np.array([get_embedding(q) for q in questions], dtype="float32")
knowledge_vectors = np.array([get_embedding(k) for k in knowledge_texts], dtype="float32")

faq_index = faiss.IndexFlatL2(dimension)
faq_index.add(faq_vectors)
knowledge_index = faiss.IndexFlatL2(dimension)
knowledge_index.add(knowledge_vectors)

pf_matcher = ProductFilmMatcher("data/product_film_color_matrix.json")

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_q = data.get("question")
    customer_attrs = data.get("attributes", {})
    session_id = data.get("session_id", "default")

    if not user_q:
        return jsonify({"error": "質問がありません"}), 400

    add_to_session_history(session_id, "user", user_q)
    session_history = get_session_history(session_id)

    # ✅ クエリ拡張処理（gpt-3.5で補完）
    expanded_q = expand_query(user_q, session_history)

    # ベクトル検索用の質問文（拡張後）
    q_vector = get_embedding(expanded_q)

    D, I = faq_index.search(np.array([q_vector]), k=5)
    faq_context = "\n".join([f"Q: {questions[i]}\nA: {answers[i]}" for i in I[0][:3]])

    K_D, K_I = knowledge_index.search(np.array([q_vector]), k=3)
    knowledge_context = "\n".join([knowledge_texts[i] for i in K_I[0]])

    attr_context = "\n".join([f"- {k}: {v}" for k, v in customer_attrs.items()])

    # 会話履歴
    user_assistant_pairs = [
        (session_history[i]["content"], session_history[i + 1]["content"])
        for i in range(0, len(session_history) - 1, 2)
        if session_history[i]["role"] == "user" and session_history[i + 1]["role"] == "assistant"
    ]
    history_context = "\n".join([f"Q{idx+1}: {q}\nA{idx+1}: {a}" for idx, (q, a) in enumerate(user_assistant_pairs[-3:])])

    # ProductFilmMatcher（関数に応じた引数を明示的に渡す）
    info = extract_keywords(user_q)

    if info.get("product") and info.get("film"):
        result = pf_matcher.get_colors_for_film_in_product(info["product"], info["film"])
        if result and result["matched"]:
            return jsonify({
                "response": result["message"],
                "original_question": user_q,
                "expanded_question": expanded_q
            })

    if info.get("product"):
        result = pf_matcher.get_films_for_product(info["product"])
        if result and result["matched"]:
            return jsonify({
                "response": result["message"],
                "original_question": user_q,
                "expanded_question": expanded_q
            })

    if info.get("film"):
        result = pf_matcher.get_products_for_film(info["film"])
        if result and result["matched"]:
            return jsonify({
                "response": result["message"],
                "original_question": user_q,
                "expanded_question": expanded_q
            })

    if info.get("color"):
        result = pf_matcher.get_films_for_color(info["color"])
        if result and result["matched"]:
            return jsonify({
                "response": result["message"],
                "original_question": user_q,
                "expanded_question": expanded_q
            })

    # プロンプト構築
    system_prompt = f"""{base_prompt}

【顧客属性】
{attr_context}

【会話履歴】
{history_context}

【参考知識ベース】
{knowledge_context}

この文脈を踏まえて、次のユーザーの質問に丁寧にお答えください。"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_q}
    ]

    completion = openai.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        temperature=0.2,
    )
    answer = completion.choices[0].message.content

    add_to_session_history(session_id, "assistant", answer)

    return jsonify({
        "response": answer,
        "original_question": user_q,
        "expanded_question": expanded_q
    })

@app.route("/", methods=["GET"])
def home():
    return "Contextual Chatbot API with query expansion is running."

if __name__ == "__main__":
    app.run(debug=True)
