import gspread
import json
from oauth2client.service_account import ServiceAccountCredentials
import os

# GitHub Secrets（JSON文字列）から credentials.json を一時生成
with open("credentials.json", "w") as f:
    f.write(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])

# 認証
scope = ['https://spreadsheets.google.com/feeds','https://www.googleapis.com/auth/drive']
credentials = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
gc = gspread.authorize(credentials)

# スプレッドシート読み込み（スプレッドシート名は必要に応じて変更）
spreadsheet = gc.open("knowledge_sheet")
sheet = spreadsheet.sheet1
records = sheet.get_all_records()

# title: [content] の形式でJSON生成
knowledge = {row['title']: [row['content']] for row in records}

# 出力
with open("data/knowledge.json", "w", encoding="utf-8") as f:
    json.dump(knowledge, f, ensure_ascii=False, indent=2)
