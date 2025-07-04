# RAG構成のFAQチャットボット（最小構成サンプル）

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 使用技術：OpenAI API, FAISS, FastAPI

import faiss
import openai
import uvicorn
from fastapi import FastAPI, Request
from pydantic import BaseModel
import numpy as np
import json
import os
from dotenv import load_dotenv

# .envファイルの読み込み
load_dotenv()

# OpenAI APIキーを環境変数から取得
openai.api_key = os.getenv("OPENAI_API_KEY")

# FAQデータの読み込み（最初にメモリに読み込んでおく）
with open("faq_data.json", "r", encoding="utf-8") as f:
    faq_items = json.load(f)
    questions = [item["question"] for item in faq_items]
    answers = [item["answer"] for item in faq_items]

# Embedding生成関数
EMBED_MODEL = "text-embedding-3-small"
def get_embedding(text):
    response = openai.embeddings.create(
        model=EMBED_MODEL,
        input=text
    )
    return np.array(response.data[0].embedding, dtype="float32")

# FAQ質問文のベクトル化とFAISSのインデックス構築
dimension = len(get_embedding("テスト"))
index = faiss.IndexFlatL2(dimension)
faq_vectors = np.array([get_embedding(q) for q in questions], dtype="float32")
index.add(faq_vectors)

# リクエストデータ型
class Query(BaseModel):
    question: str

@app.post("/chat")
async def chat(query: Query):
    user_q = query.question
    q_vector = get_embedding(user_q)
    D, I = index.search(np.array([q_vector]), k=3)

    # 上位3件のFAQをcontextとして使用
    context = "\n".join([f"Q: {questions[i]}\nA: {answers[i]}" for i in I[0]])

    prompt = f"以下はFAQです。ユーザーの質問に答えてください。\n\n{context}\n\nユーザーの質問: {user_q}\n回答:"

    completion = openai.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )
    answer = completion.choices[0].message.content
    return {"answer": answer}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
