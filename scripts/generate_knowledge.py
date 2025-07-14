import gspread
import json
from oauth2client.service_account import ServiceAccountCredentials

# 認証設定
scope = ['https://spreadsheets.google.com/feeds','https://www.googleapis.com/auth/drive']
credentials = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
gc = gspread.authorize(credentials)

# スプレッドシート読み込み（スプレッドシート名は適宜変更）
spreadsheet = gc.open("knowledge_sheet")
sheet = spreadsheet.sheet1
records = sheet.get_all_records()

# knowledge.json 形式に変換
knowledge = {row['title']: [row['content']] for row in records}

# ファイル出力
with open("data/knowledge.json", "w", encoding="utf-8") as f:
    json.dump(knowledge, f, ensure_ascii=False, indent=2)