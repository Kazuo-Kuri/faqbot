import json
import os
import datetime
from collections import Counter
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# === 設定 ===
SPREADSHEET_ID = '1ApH-A58jUCZSKwTBAyuPZlZTNsv_2RwKGSqZNyaHHfk'
RANGE_NAME = 'FAQ!A2:C'
CREDENTIALS_FILE = 'credentials.json'

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FAQ_JSON_PATH = os.path.join(BASE_DIR, 'faq_data.json')
SUGGESTION_JSON_PATH = os.path.join(BASE_DIR, 'faq_suggestions.json')
LOG_PATH = os.path.join(BASE_DIR, 'log.txt')

# === Google Sheets から FAQ データを取得 ===
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

# === faq_data.json に書き込み ===
with open(FAQ_JSON_PATH, 'w', encoding='utf-8') as f:
    json.dump(faq_list, f, ensure_ascii=False, indent=2)

print(f"✅ FAQデータを {FAQ_JSON_PATH} に更新しました")

# === ログから未回答を抽出し、faq_suggestions.json を生成 ===
try:
    with open(LOG_PATH, 'r', encoding='utf-8') as f:
        lines = f.readlines()
except FileNotFoundError:
    print("⚠️ log.txt が見つかりません。")
    lines = []

questions = []
answers = []
for line in lines:
    if "ユーザーの質問:" in line:
        question = line.split("ユーザーの質問:")[-1].strip()
        questions.append(question)
    elif "回答:" in line:
        answer = line.split("回答:")[-1].strip()
        answers.append(answer)

unanswered = []
faq_answers = [entry["answer"] for entry in faq_list]

# 未回答と思われる回答パターンに基づいて抽出（完全一致でなくても可）
default_responses = [
    "申し訳ありませんが、",
    "FAQには",
    "含まれていません",
    "直接お問い合わせ",
    "現在のFAQには含まれておりません"
]

for q, a in zip(questions, answers):
    if any(x in a for x in default_responses):
        unanswered.append(q)

# カウントしてリスト化
counter = Counter(unanswered)
suggestions = [
    {"question": q, "count": count, "status": "未回答"}
    for q, count in counter.items()
]

# 書き出し
with open(SUGGESTION_JSON_PATH, "w", encoding="utf-8") as f:
    json.dump(suggestions, f, ensure_ascii=False, indent=2)

print(f"✅ {len(suggestions)} 件の未回答を {SUGGESTION_JSON_PATH} に書き出しました")

# === ログ出力 ===
with open(LOG_PATH, 'a', encoding='utf-8') as log:
    log.write(f"[{datetime.datetime.now()}] FAQデータを更新しました（件数: {len(faq_list)}）\n")
