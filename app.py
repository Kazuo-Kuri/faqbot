from flask import Flask, request, jsonify
from flask_cors import CORS
from google.oauth2 import service_account
from googleapiclient.discovery import build
import openai
import faiss
import numpy as np
import os
import json
import time
import base64
from datetime import datetime
from dotenv import load_dotenv
from product_film_matcher import ProductFilmMatcher
from keyword_filter import extract_keywords
from query_expander import expand_query

# === 初期設定 ===
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

app = Flask(__name__)
CORS(app)

# === セッション履歴管理 ===
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

# === データ読み込み ===
with open("data/faq.json", "r", encoding="utf-8") as f:
    faq_items = json.load(f)
faq_questions = [item["question"] for item in faq_items]
faq_answers = [item["answer"] for item in faq_items]

with open("data/knowledge.json", "r", encoding="utf-8") as f:
    knowledge_dict = json.load(f)
knowledge_contents = [
    f"{category}：{text}"
    for category, texts in knowledge_dict.items()
    for text in texts
]

metadata_note = ""
metadata_path = "data/metadata.json"
if os.path.exists(metadata_path):
    with open(metadata_path, "r", encoding="utf-8") as f:
        metadata = json.load(f)
        metadata_note = f"{metadata.get('title', '')}（種類：{metadata.get('type', '')}、優先度：{metadata.get('priority', '')}）"

# === コーパス定義（順序維持が重要）===
search_corpus = faq_questions + knowledge_contents  # metadata_note は検索対象に含めない
source_flags = ["faq"] * len(faq_questions) + ["knowledge"] * len(knowledge_contents)

# === EmbeddingとFAISSインデックス ===
EMBED_MODEL = "text-embedding-3-small"
VECTOR_PATH = "data/vector_data.npy"
INDEX_PATH = "data/index.faiss"

def get_embedding(text):
    response = openai.embeddings.create(model=EMBED_MODEL, input=text)
    return np.array(response.data[0].embedding, dtype="float32")

# キャッシュロード（存在しない場合は作成）
if os.path.exists(VECTOR_PATH) and os.path.exists(INDEX_PATH):
    vector_data = np.load(VECTOR_PATH)
    index = faiss.read_index(INDEX_PATH)
else:
    vector_data = np.array([get_embedding(text) for text in search_corpus], dtype="float32")
    index = faiss.IndexFlatL2(vector_data.shape[1])
    index.add(vector_data)
    np.save(VECTOR_PATH, vector_data)
    faiss.write_index(index, INDEX_PATH)

# === Google Sheets設定 ===
SPREADSHEET_ID = "1asbjzo-G9I6SmztBG18iWuiTKetOJK20JwAyPF11fA4"
UNANSWERED_SHEET = "faq_suggestions"
FEEDBACK_SHEET = "feedback_log"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

credentials_info = json.loads(
    base64.b64decode(os.environ["GOOGLE_CREDENTIALS"]).decode("utf-8")
)
credentials = service_account.Credentials.from_service_account_info(
    credentials_info, scopes=SCOPES
)
sheet_service = build("sheets", "v4", credentials=credentials).spreadsheets()

# === 補助ツール ===
pf_matcher = ProductFilmMatcher("data/product_film_color_matrix.json")

with open("system_prompt.txt", "r", encoding="utf-8") as f:
    base_prompt = f.read()

# === チャットエンドポイント ===
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
    expanded_q = expand_query(user_q, session_history)
    q_vector = get_embedding(expanded_q)

    D, I = index.search(np.array([q_vector]), k=7)
    faq_context = []
    reference_context = []

    for idx in I[0]:
        src = source_flags[idx]
        if src == "faq":
            q = faq_questions[idx]
            a = faq_answers[idx]
            faq_context.append(f"Q: {q}\nA: {a}")
        elif src == "knowledge":
            ref_idx = idx - len(faq_questions)
            reference_context.append(f"【参考知識】{knowledge_contents[ref_idx]}")

    # 製品フィルムマッチャーから補足情報を取得
    film_match_info = pf_matcher.match(user_q)
    if film_match_info:
        reference_context.append(f"【製品カラー情報】{film_match_info}")

    # metadata_note を GPTへの参考情報にのみ追加（検索には含めていない）
    if metadata_note:
        reference_context.append(f"【参考ファイル情報】{metadata_note}")

    if not faq_context and not reference_context:
        answer = "申し訳ございません。ただいまこちらで確認中です。詳細が分かり次第、改めてご案内いたします。"
    else:
        faq_part = "\n\n".join(faq_context[:3]) if faq_context else "該当するFAQは見つかりませんでした。"
        ref_part = "\n".join(reference_context[:2]) if reference_context else ""
        prompt = f"""以下は当社のFAQおよび参考情報です。これらを参考に、ユーザーの質問に製造元の立場でご回答ください。

【FAQ】
{faq_part}

【参考情報】
{ref_part}

ユーザーの質問: {user_q}
回答:"""

        completion = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": base_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
        )
        answer = completion.choices[0].message.content

    if "申し訳" in answer:
        new_row = [[
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            user_q,
            "未回答",
            1
        ]]
        sheet_service.values().append(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{UNANSWERED_SHEET}!A2:D",
            valueInputOption="RAW",
            body={"values": new_row}
        ).execute()

    add_to_session_history(session_id, "assistant", answer)

    return jsonify({
        "response": answer,
        "original_question": user_q,
        "expanded_question": expanded_q
    })

# === フィードバック記録 ===
@app.route("/feedback", methods=["POST"])
def feedback():
    data = request.get_json()
    question = data.get("question")
    answer = data.get("answer")
    feedback_value = data.get("feedback")
    reason = data.get("reason", "")

    if not all([question, answer, feedback_value]):
        return jsonify({"error": "不完全なフィードバックデータです"}), 400

    row = [[
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        question,
        answer,
        feedback_value,
        reason
    ]]
    sheet_service.values().append(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{FEEDBACK_SHEET}!A2:E",
        valueInputOption="RAW",
        body={"values": row}
    ).execute()

    return jsonify({"status": "success"})

@app.route("/", methods=["GET"])
def home():
    return "Integrated Chatbot API is running."

if __name__ == "__main__":
    app.run(debug=True)
