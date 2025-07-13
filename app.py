from flask import Flask, request, jsonify
import faiss
import openai
import numpy as np
import os
import json
from dotenv import load_dotenv
from flask_cors import CORS
from product_film_matcher import ProductFilmMatcher
from keyword_filter import extract_keywords

# 環境変数のロード
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# Flaskアプリ初期化
app = Flask(__name__)
CORS(app)

# データ読み込み（FAQ）
with open("data/faq.json", "r", encoding="utf-8") as f:
    faq_items = json.load(f)
questions = [item["question"] for item in faq_items]
answers = [item["answer"] for item in faq_items]

# データ読み込み（knowledge）
with open("data/knowledge.json", "r", encoding="utf-8") as f:
    knowledge_dict = json.load(f)
knowledge_texts = []
for category, entries in knowledge_dict.items():
    for entry in entries:
        knowledge_texts.append(f"{category}: {entry}")

# ベースプロンプト読み込み
with open("system_prompt.txt", "r", encoding="utf-8") as f:
    base_prompt = f.read()

# Embedding関数
EMBED_MODEL = "text-embedding-3-small"
def get_embedding(text):
    response = openai.embeddings.create(
        model=EMBED_MODEL,
        input=text
    )
    return np.array(response.data[0].embedding, dtype="float32")

# ベクトル生成
dimension = len(get_embedding("テスト"))
faq_vectors = np.array([get_embedding(q) for q in questions], dtype="float32")
knowledge_vectors = np.array([get_embedding(k) for k in knowledge_texts], dtype="float32")

faq_index = faiss.IndexFlatL2(dimension)
faq_index.add(faq_vectors)
knowledge_index = faiss.IndexFlatL2(dimension)
knowledge_index.add(knowledge_vectors)

# ProductFilmMatcher 初期化
pf_matcher = ProductFilmMatcher("data/product_film_color_matrix.json")

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_q = data.get("question")
    customer_attrs = data.get("attributes", {})
    chat_history = data.get("history", [])

    if not user_q:
        return jsonify({"error": "質問がありません"}), 400

    q_vector = get_embedding(user_q)

    # FAQ検索
    D, I = faq_index.search(np.array([q_vector]), k=5)
    faq_context = "\n".join([f"Q: {questions[i]}\nA: {answers[i]}" for i in I[0][:3]])

    # knowledge検索
    K_D, K_I = knowledge_index.search(np.array([q_vector]), k=3)
    knowledge_context = "\n".join([knowledge_texts[i] for i in K_I[0]])

    # 属性・履歴
    attr_context = "\n".join([f"- {k}: {v}" for k, v in customer_attrs.items()])
    history_context = "\n".join([f"Q{idx+1}: {h['q']}\nA{idx+1}: {h['a']}" for idx, h in enumerate(chat_history[-3:])])

    # ProductFilmMatcher ロジック（直接返答できる場合）
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

    # プロンプト構築（system_prompt.txt をベースに動的情報を追加）
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

    return jsonify({"response": answer})

@app.route("/", methods=["GET"])
def home():
    return "Contextual Chatbot API is running."

if __name__ == "__main__":
    app.run(debug=True)
