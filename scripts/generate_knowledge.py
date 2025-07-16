import os
import json
import numpy as np
import faiss
import gspread
import openai
from dotenv import load_dotenv
from oauth2client.service_account import ServiceAccountCredentials

# .env 読み込み（ローカル実行時）
load_dotenv()

# OpenAI APIキー設定
openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    raise ValueError("OPENAI_API_KEY is not set or empty.")

# 認証設定（gspread）
scope = ['https://spreadsheets.google.com/feeds','https://www.googleapis.com/auth/drive']
credentials = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
gc = gspread.authorize(credentials)

# スプレッドシート取得
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID") or "1ApH-A58jUCZSKwTBAyuPZlZTNsv_2RwKGSqZNyaHHfk"
sheet = gc.open_by_key(SPREADSHEET_ID).worksheet("knowledge")
records = sheet.get_all_records()

# knowledge.json を作成
knowledge_dict = {row['title']: [row['content']] for row in records}
os.makedirs("data", exist_ok=True)
with open("data/knowledge.json", "w", encoding="utf-8") as f:
    json.dump(knowledge_dict, f, ensure_ascii=False, indent=2)
print("✅ data/knowledge.json を保存しました。")

# ベクトル生成対象のリスト
texts = [f"{row['title']}：{row['content']}" for row in records]

# バッチ埋め込み関数
def get_embeddings_in_batches(texts, batch_size=100):
    vectors = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]
        response = openai.embeddings.create(
            model="text-embedding-3-small",
            input=batch
        )
        batch_vectors = [np.array(data.embedding, dtype="float32") for data in response.data]
        vectors.extend(batch_vectors)
    return np.array(vectors, dtype="float32")

# 埋め込み処理
print("🔄 knowledge のベクトルを生成中（バッチ処理）...")
vector_data = get_embeddings_in_batches(texts)
dimension = vector_data.shape[1]

# FAISSインデックス作成＆保存
index = faiss.IndexFlatL2(dimension)
index.add(vector_data)
np.save("data/vector_data_knowledge.npy", vector_data)
faiss.write_index(index, "data/index_knowledge.faiss")
print("✅ ベクトルと index_knowledge.faiss を保存しました。")
