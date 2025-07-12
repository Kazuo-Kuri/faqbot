from fastapi import FastAPI, Request
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

with open("faq_data.json", "r", encoding="utf-8") as f:
    faq_items = json.load(f)

questions = [item["question"] for item in faq_items]
answers = [item["answer"] for item in faq_items]
categories = [item.get("category", "") for item in faq_items]

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

        return {"answer": "申し訳ございません。FAQには該当の情報が含まれていません。詳細につきましては、メールもしくはお問合せフォームよりお問合せをお願いいたします。"}

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

    return {"answer": answer}