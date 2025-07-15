import os
import json
import numpy as np
import faiss
import openai
from dotenv import load_dotenv

# === 初期設定 ===
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# === パス設定 ===
FAQ_PATH = "data/faq.json"
KNOWLEDGE_PATH = "data/knowledge.json"
METADATA_PATH = "data/metadata.json"
VECTOR_PATH = "data/vector_data.npy"
INDEX_PATH = "data/index.faiss"
EMBED_MODEL = "text-embedding-3-small"

# === Embedding取得関数 ===
def get_embedding(text):
    response = openai.embeddings.create(
        model=EMBED_MODEL,
        input=text
    )
    return np.array(response.data[0].embedding, dtype="float32")

# === データ読み込み ===
with open(FAQ_PATH, "r", encoding="utf-8") as f:
    faq_items = json.load(f)
faq_questions = [item["question"] for item in faq_items]

with open(KNOWLEDGE_PATH, "r", encoding="utf-8") as f:
    knowledge_data = json.load(f)

# knowledge.json が dict または list の可能性に対応
if isinstance(knowledge_data, dict):
    knowledge_contents = [
        f"{category}：{text}"
        for category, texts in knowledge_data.items()
        for text in texts
    ]
elif isinstance(knowledge_data, list):
    knowledge_contents = [
        f"{item['title']}：{item['content']}" for item in knowledge_data
    ]
else:
    raise ValueError("knowledge.json の形式が不正です。")

# メタ情報（任意）
metadata_note = ""
if os.path.exists(METADATA_PATH):
    with open(METADATA_PATH, "r", encoding="utf-8") as f:
        metadata = json.load(f)
        metadata_note = f"【ファイル情報】{metadata.get('title', '')}（種類：{metadata.get('type', '')}、優先度：{metadata.get('priority', '')}）"

# === コーパス構築 ===
search_corpus = faq_questions + knowledge_contents + [metadata_note]

# === ベクトル化 & FAISS保存 ===
print("🔄 埋め込み生成中...")
vector_data = np.array([get_embedding(text) for text in search_corpus], dtype="float32")

print("🧠 FAISSインデックス作成...")
index = faiss.IndexFlatL2(vector_data.shape[1])
index.add(vector_data)

print("💾 ファイル保存中...")
np.save(VECTOR_PATH, vector_data)
faiss.write_index(index, INDEX_PATH)

print("✅ ベクトルデータとインデックスの再構築が完了しました。")
