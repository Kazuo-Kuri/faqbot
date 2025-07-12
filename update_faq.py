import os
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build

# スプレッドシートの設定
SPREADSHEET_ID = '1ApH-A58jUCZSKwTBAyuPZlZTNsv_2RwKGSqZNyaHHfk'
RANGE_NAME = 'FAQ!A1:C'  # A列:question, B列:answer, C列:category（任意）

# 認証情報ファイルを読み込む
SERVICE_ACCOUNT_FILE = 'credentials.json'
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']

credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES
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

# データ整形
faq_list = []
for i, row in enumerate(values[1:]):  # 1行目はヘッダーなのでスキップ
    if len(row) >= 2 and row[0].strip() and row[1].strip():
        faq = {
            'question': row[0].strip(),
            'answer': row[1].strip()
        }
        if len(row) >= 3 and row[2].strip():
            faq['category'] = row[2].strip()
        faq_list.append(faq)

# 出力フォルダの準備
os.makedirs('data', exist_ok=True)

# JSONファイルとして保存
output_path = 'data/faq.json'
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(faq_list, f, ensure_ascii=False, indent=2)

print(f'✅ {output_path} を生成しました。')
