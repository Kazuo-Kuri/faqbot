import json
import os
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# ===== 設定 =====
SPREADSHEET_ID = '1asbjzo-G9I6SmztBG18iWuiTKetOJK20JwAyPF11fA4'
SHEET_NAME = 'Suggestions'
RANGE_NAME = f'{SHEET_NAME}!A2:C'
CREDENTIALS_FILE = 'credentials.json'
JSON_FILE = 'faq_suggestions.json'

# ===== 認証とサービス初期化 =====
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
service = build('sheets', 'v4', credentials=creds)
sheet = service.spreadsheets()

# ===== 既存の質問を取得 =====
result = sheet.values().get(
    spreadsheetId=SPREADSHEET_ID,
    range=RANGE_NAME
).execute()

existing_values = result.get("values", [])
existing_questions = set(row[0] for row in existing_values if len(row) > 0)

# ===== JSON読み込み =====
with open(JSON_FILE, 'r', encoding='utf-8') as f:
    suggestions = json.load(f)

# ===== 重複除外して新規だけ抽出 =====
new_entries = [
    [item["question"], item["count"], item["status"]]
    for item in suggestions
    if item["question"] not in existing_questions
]

if not new_entries:
    print("⚠️ 新規データはありません。書き込みは行われませんでした。")
else:
    # ===== 書き出し =====
    sheet.values().append(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{SHEET_NAME}!A2",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": new_entries}
    ).execute()

    print(f"✅ {len(new_entries)}件の新規データをスプレッドシートに追記しました。")
