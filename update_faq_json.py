import json
import os
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# === 設定 ===
SPREADSHEET_ID = '1ApH-A58jUCZSKwTBAyuPZlZTNsv_2RwKGSqZNyaHHfk'  # ← IDだけに修正
RANGE_NAME = 'FAQ!A2:B'
CREDENTIALS_FILE = 'credentials.json'

# === スクリプトと同じ場所にfaq_data.jsonを保存する ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.join(BASE_DIR, 'faq_data.json')

# === 認証とAPI呼び出し ===
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
creds = Credentials.from_service_account_file(
    os.path.join(BASE_DIR, CREDENTIALS_FILE), scopes=SCOPES
)
service = build('sheets', 'v4', credentials=creds)

sheet = service.spreadsheets()
result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=RANGE_NAME).execute()
values = result.get('values', [])

# === JSON形式に整形 ===
faq_list = []
for row in values:
    if len(row) >= 2:
        faq_list.append({
            "question": row[0],
            "answer": row[1]
        })

# === JSONファイルとして保存 ===
with open(JSON_PATH, 'w', encoding='utf-8') as f:
    json.dump(faq_list, f, ensure_ascii=False, indent=2)

print(f"✅ FAQデータを {JSON_PATH} に更新しました")

import datetime

log_path = os.path.join(BASE_DIR, 'log.txt')
with open(log_path, 'a', encoding='utf-8') as log:
    log.write(f"[{datetime.datetime.now()}] FAQデータを更新しました（件数: {len(faq_list)}）\n")
