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

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# Load FAQ data
with open("data/faq.json", "r", encoding="utf-8") as f:
    faq_items = json.load(f)

questions = [item["question"] for item in faq_items]
answers = [item["answer"] for item in faq_items]
categories = [item.get("category", "") for item in faq_items]

# Load system prompt
with open("system_prompt.txt", "r", encoding="utf-8") as f:
    system_prompt = f.read()

# Embedding
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

# Log path
LOCAL_LOG_PATH = os.path.join(os.path.dirname(__file__), "log.txt")
CLOUD_LOG_PATH = "/tmp/log.txt"
log_path = LOCAL_LOG_PATH if os.access(os.path.dirname(__file__), os.W_OK) else CLOUD_LOG_PATH

# FastAPI setup
class Query(BaseModel):
    question: str
    category: Optional[str] = None

app = FastAPI()

@app.post("/chat")
async def chat(query: Query):
    user_q = query.question
    category_filter = query.category
    q_vector = get_embedding(user_q)

    D, I = index.search(np.array([q_vector]), k=5)
    matched = [i for i in I[0] if category_filter is None or categories[i] == category_filter]

    answer = ""
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

        answer = "申し訳ございません。ただいまこちらで確認中です。詳細が分かり次第、改めてご案内いたします。"
    else:
        context = "\n".join([f"Q: {questions[i]}\nA: {answers[i]}" for i in matched[:3]])
        prompt = f"以下は当社FAQの一部です。これらを参考に、ユーザーの質問に製造元の立場でお答えください。\n\n{context}\n\nユーザーの質問: {user_q}\n回答:"

        completion = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
        )
        answer = completion.choices[0].message.content

    # ログ書き込み（FAQヒット／未ヒット共通）
    try:
        with open(log_path, "a", encoding="utf-8") as log:
            log.write(f"[{datetime.datetime.now()}] ユーザーの質問: {user_q}\n")
            log.write(f"[{datetime.datetime.now()}] 回答: {answer}\n")
    except Exception as e:
        print(f"⚠️ log.txt 書き込み失敗: {e}")

    return {"answer": answer}

# ローカル起動用
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
