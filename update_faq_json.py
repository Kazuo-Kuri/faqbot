import json
import os
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import datetime

# ===== 設定 =====
SPREADSHEET_ID = '1ApH-A58jUCZSKwTBAyuPZlZTNsv_2RwKGSqZNyaHHfk'
RANGE_NAME = 'FAQ!A2:C'
CREDENTIALS_FILE = 'credentials.json'

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.join(BASE_DIR, 'faq_data.json')
SUGGESTIONS_PATH = os.path.join(BASE_DIR, 'faq_suggestions.json')
LOG_PATH = os.path.join(BASE_DIR, 'log.txt')

# ===== Google SheetsからFAQ取得 =====
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
creds = Credentials.from_service_account_file(
    os.path.join(BASE_DIR, CREDENTIALS_FILE), scopes=SCOPES
)
service = build('sheets', 'v4', credentials=creds)

sheet = service.spreadsheets()
result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=RANGE_NAME).execute()
values = result.get('values', [])

faq_list = []
for row in values:
    if len(row) >= 2:
        faq = {
            "question": row[0],
            "answer": row[1]
        }
        if len(row) >= 3:
            faq["category"] = row[2]
        faq_list.append(faq)

with open(JSON_PATH, 'w', encoding='utf-8') as f:
    json.dump(faq_list, f, ensure_ascii=False, indent=2)

print(f"✅ FAQデータを {JSON_PATH} に更新しました")

# ===== ログに書き出し =====
with open(LOG_PATH, 'a', encoding='utf-8') as log:
    log.write(f"[{datetime.datetime.now()}] FAQデータを更新しました（件数: {len(faq_list)}）\n")

# ===== 未回答ログからfaq_suggestions.jsonを生成 =====
suggestions = []

if os.path.exists(LOG_PATH):
    with open(LOG_PATH, 'r', encoding='utf-8') as log_file:
        for line in log_file:
            if '未回答:' in line:
                try:
                    question = line.strip().split('未回答:')[1].strip()
                    if question:
                        suggestions.append({
                            "question": question,
                            "count": 1,
                            "status": "未回答"
                        })
                except IndexError:
                    continue

# ===== 重複をマージ =====
merged = {}
for s in suggestions:
    q = s["question"]
    if q in merged:
        merged[q]["count"] += 1
    else:
        merged[q] = s

with open(SUGGESTIONS_PATH, 'w', encoding='utf-8') as f:
    json.dump(list(merged.values()), f, ensure_ascii=False, indent=2)

print(f"📝 未回答の質問 {len(merged)} 件を {SUGGESTIONS_PATH} に保存しました")
