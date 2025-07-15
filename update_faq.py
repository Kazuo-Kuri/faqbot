import os
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build

# スプレッドシートの設定
SPREADSHEET_ID = '1ApH-A58jUCZSKwTBAyuPZlZTNsv_2RwKGSqZNyaHHfk'
RANGE_NAME = 'FAQ!A1:C'

# credentials.json を読み込む
with open("credentials.json", "r", encoding="utf-8") as f:
    credentials_info = json.load(f)

SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
credentials = service_account.Credentials.from_service_account_info(
    credentials_info, scopes=SCOPES
)

# Sheets APIクライアントを作成
service = build('sheets', 'v4', credentials=credentials)
sheet = service.spreadsheets()

# データ取得
result = sheet.values().get(
    spreadsheetId=SPREADSHEET_ID,
    range=RANGE_NAME
).execute()
values = result.get('values', [])

# JSON化処理
faq_list = []
for i, row in enumerate(values[1:]):  # 1行目はヘッダー
    if len(row) >= 2 and row[0].strip() and row[1].strip():
        faq = {
            'question': row[0].strip(),
            'answer': row[1].strip()
        }
        if len(row) >= 3 and row[2].strip():
            faq['category'] = row[2].strip()
        faq_list.append(faq)

# 出力
os.makedirs('data', exist_ok=True)
with open('data/faq.json', 'w', encoding='utf-8') as f:
    json.dump(faq_list, f, ensure_ascii=False, indent=2)

print("✅ data/faq.json を生成しました。")
