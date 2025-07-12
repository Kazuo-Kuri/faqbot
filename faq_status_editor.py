from google.oauth2 import service_account
from googleapiclient.discovery import build

# === 設定 ===
SPREADSHEET_ID = "1asbjzo-G9I6SmztBG18iWuiTKetOJK20JwAyPF11fA4"
SHEET_NAME = "faq_suggestions"  # シート名
RANGE = f"{SHEET_NAME}!A2:D"    # A列:question, B列:count, C列:status, D列:timestamp

# 認証情報
SERVICE_ACCOUNT_FILE = "credentials.json"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# === Google Sheets API に接続 ===
credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES)
service = build("sheets", "v4", credentials=credentials)
sheet = service.spreadsheets()

# === データ取得 ===
result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=RANGE).execute()
values = result.get("values", [])

# === 未回答の抽出 ===
unanswered = [(i + 2, row) for i, row in enumerate(values) if len(row) > 2 and row[2] == "未回答"]

if not unanswered:
    print("✅ 未回答はありません。")
else:
    print("🔎 未回答一覧：")
    for row_num, row in unanswered:
        print(f"{row_num}: {row[0]}")

    try:
        # ステータス変更
        target_row = int(input("🔢 ステータスを更新したい行番号を入力してください: "))
        new_status = input("📝 新しいステータスを入力してください（例: 回答済み）: ").strip()

        status_range = f"{SHEET_NAME}!C{target_row}"
        response = sheet.values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=status_range,
            valueInputOption="RAW",
            body={"values": [[new_status]]}
        ).execute()

        print(f"✅ ステータスを「{new_status}」に更新しました。")
    except Exception as e:
        print(f"⚠ エラーが発生しました: {e}")
