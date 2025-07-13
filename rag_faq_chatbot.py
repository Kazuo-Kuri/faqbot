from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional
import faiss
import openai
import uvicorn
import numpy as np
import json
import os
from dotenv import load_dotenv
import datetime

# 環境変数読み込み
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# FAQデータ読み込み
with open("data/faq.json", "r", encoding="utf-8") as f:
    faq_items = json.load(f)

faq_questions = [item["question"] for item in faq_items]
faq_answers = [item["answer"] for item in faq_items]
faq_categories = [item.get("category", "") for item in faq_items]

# knowledge.json読み込み
with open("data/knowledge.json", "r", encoding="utf-8") as f:
    knowledge_items = json.load(f)

knowledge_contents = [f"{item['title']}：{item['content']}" for item in knowledge_items]

# metadata.json読み込み
with open("data/metadata.json", "r", encoding="utf-8") as f:
    metadata = json.load(f)

metadata_note = f"【ファイル情報】{metadata.get('title', '')}（種類：{metadata.get('type', '')}、優先度：{metadata.get('priority', '')}）"

# 検索対象データと種別
search_corpus = faq_questions + knowledge_contents + [metadata_note]
source_flags = ["faq"] * len(faq_questions) + ["knowledge"] * len(knowledge_contents) + ["metadata"]

# システムプロンプト読み込み
with open("system_prompt.txt", "r", encoding="utf-8") as f:
    system_prompt = f.read()

# Embeddingモデル
EMBED_MODEL = "text-embedding-3-small"

def get_embedding(text):
    response = openai.embeddings.create(
        model=EMBED_MODEL,
        input=text
    )
    return np.array(response.data[0].embedding, dtype="float32")

# FAISSインデックス作成
vector_data = np.array([get_embedding(text) for text in search_corpus], dtype="float32")
dimension = vector_data.shape[1]
index = faiss.IndexFlatL2(dimension)
index.add(vector_data)

# ログパス設定
LOCAL_LOG_PATH = os.path.join(os.path.dirname(__file__), "log.txt")
CLOUD_LOG_PATH = "/tmp/log.txt"
log_path = LOCAL_LOG_PATH if os.access(os.path.dirname(__file__), os.W_OK) else CLOUD_LOG_PATH

# FastAPIセットアップ
class Query(BaseModel):
    question: str
    category: Optional[str] = None

app = FastAPI()

@app.post("/chat")
async def chat(query: Query):
    user_q = query.question
    category_filter = query.category
    q_vector = get_embedding(user_q)

    D, I = index.search(np.array([q_vector]), k=7)

    faq_context = []
    reference_context = []

    for idx in I[0]:
        src = source_flags[idx]
        if src == "faq":
            if category_filter is None or faq_categories[idx] == category_filter:
                q = faq_questions[idx]
                a = faq_answers[idx]
                faq_context.append(f"Q: {q}\nA: {a}")
        elif src == "knowledge":
            ref_idx = idx - len(faq_questions)
            reference_context.append(f"【参考知識】{knowledge_contents[ref_idx]}")
        elif src == "metadata":
            reference_context.append(metadata_note)

    answer = ""
    if not faq_context:
        # 未回答ログ登録
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

        answer = "申し訳ございません。ただいまこちらで確認中です。詳細が分かり次第、改めてご案内いたします。"
    else:
        faq_part = "\n\n".join(faq_context[:3])
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
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
        )
        answer = completion.choices[0].message.content

    # ログ書き込み
    try:
        with open(log_path, "a", encoding="utf-8") as log:
            log.write(f"[{datetime.datetime.now()}] ユーザーの質問: {user_q}\n")
            log.write(f"[{datetime.datetime.now()}] 回答: {answer}\n")
    except Exception as e:
        print(f"⚠️ log.txt 書き込み失敗: {e}")

    return {"answer": answer}

# ローカル実行
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
