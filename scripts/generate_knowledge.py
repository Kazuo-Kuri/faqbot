import gspread
import json
from oauth2client.service_account import ServiceAccountCredentials

# 認証設定
scope = ['https://spreadsheets.google.com/feeds','https://www.googleapis.com/auth/drive']
credentials = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
gc = gspread.authorize(credentials)

# スプレッドシートIDで読み込み（例：URLの /d/ の後の部分）
spreadsheet = gc.open_by_key("1ApH-A58jUCZSKwTBAyuPZlZTNsv_2RwKGSqZNyaHHfk")  # ←ここを変更
sheet = spreadsheet.worksheet("knowledge")  # シート名を指定（または .sheet1）

records = sheet.get_all_records()
knowledge = {row['title']: [row['content']] for row in records}

with open("data/knowledge.json", "w", encoding="utf-8") as f:
    json.dump(knowledge, f, ensure_ascii=False, indent=2)
