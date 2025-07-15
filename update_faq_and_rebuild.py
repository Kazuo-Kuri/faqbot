import os
import json
import numpy as np
import faiss
from google.oauth2 import service_account
from googleapiclient.discovery import build
import openai

# === ローカル実行時のみ .env を読み込む ===
if os.getenv("GITHUB_ACTIONS") != "true":
    from dotenv import load_dotenv
    load_dotenv()

# === OpenAI APIキー設定 ===
openai.api_key = os.getenv("OPENAI_API_KEY")

# === credentials.json を直接読み込み ===
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
with open("credentials.json", "r", encoding="utf-8") as f:
    credentials_info = json.load(f)
credentials = service_account.Credentials.from_service_account_info(
    credentials_info, scopes=SCOPES
)

# === スプレッドシート設定 ===
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID") or '1ApH-A58jUCZSKwTBAyuPZlZTNsv_2RwKGSqZNyaHHfk'
RANGE_NAME = 'FAQ!A1:C'

sheet_service = build('sheets', 'v4', credentials=credentials).spreadsheets()
result = sheet_service.values().get(spreadsheetId=SPREADSHEET_ID, range=RANGE_NAME).execute()
values = result.get('values', [])

# === faq.json を生成 ===
faq_list = []
for row in values[1:]:  # 1行目はヘッダー
    if len(row) >= 2 and row[0].strip() and row[1].strip():
        entry = {"question": row[0].strip(), "answer": row[1].strip()}
        if len(row) >= 3 and row[2].strip():
            entry["category"] = row[2].strip()
        faq_list.append(entry)

os.makedirs("data", exist_ok=True)
with open("data/faq.json", "w", encoding="utf-8") as f:
    json.dump(faq_list, f, ensure_ascii=False, indent=2)

print("✅ data/faq.json を保存しました。")

# === knowledge.json を読み込み ===
with open("data/knowledge.json", "r", encoding="utf-8") as f:
    knowledge_dict = json.load(f)
knowledge_contents = [
    f"{category}：{text}"
    for category, texts in knowledge_dict.items()
    for text in texts
]

# === metadata（任意）===
metadata_note = ""
metadata_path = "data/metadata.json"
if os.path.exists(metadata_path):
    with open(metadata_path, "r", encoding="utf-8") as f:
        metadata = json.load(f)
        metadata_note = f"【ファイル情報】{metadata.get('title', '')}（種類：{metadata.get('type', '')}、優先度：{metadata.get('priority', '')}）"

# === ベクトルを再生成 ===
EMBED_MODEL = "text-embedding-3-small"
search_corpus = [item["question"] for item in faq_list] + knowledge_contents + [metadata_note]

def get_embedding(text):
    response = openai.embeddings.create(model=EMBED_MODEL, input=text)
    return np.array(response.data[0].embedding, dtype="float32")

print("🔄 ベクトルを再生成しています...")
vector_data = np.array([get_embedding(text) for text in search_corpus], dtype="float32")

dimension = vector_data.shape[1]
index = faiss.IndexFlatL2(dimension)
index.add(vector_data)

# === 保存 ===
np.save("data/vector_data.npy", vector_data)
faiss.write_index(index, "data/index.faiss")

print("✅ ベクトルデータとFAISSインデックスを保存しました。")
