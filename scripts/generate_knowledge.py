import json
import os
import tempfile
import time
from pathlib import Path

import gspread
from dotenv import load_dotenv
from google.auth.exceptions import GoogleAuthError, TransportError
from google.oauth2.service_account import Credentials
from gspread.exceptions import APIError, SpreadsheetNotFound, WorksheetNotFound
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import Timeout as RequestsTimeout


if os.getenv("GITHUB_ACTIONS") != "true":
    load_dotenv()


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]
SPREADSHEET_ID = (
    os.getenv("SPREADSHEET_ID")
    or "1ApH-A58jUCZSKwTBAyuPZlZTNsv_2RwKGSqZNyaHHfk"
)
SHEET_NAME = "knowledge"
KNOWLEDGE_PATH = Path("data/knowledge.json")
PERMANENT_HTTP_STATUSES = {400, 401, 403, 404}


def get_status_code(error: APIError) -> int | None:
    response = getattr(error, "response", None)
    return getattr(response, "status_code", None)


def get_knowledge_records_with_retry(
    retries: int = 4,
    base_delay: int = 5,
) -> list[dict]:
    """Google Sheets の knowledge シートを一時障害時のみ再取得する。"""
    try:
        credentials = Credentials.from_service_account_file(
            "credentials.json",
            scopes=SCOPES,
        )
        client = gspread.authorize(credentials)
    except (GoogleAuthError, ValueError, OSError) as error:
        raise RuntimeError("Google Sheets の認証に失敗しました。") from error

    for attempt in range(1, retries + 1):
        try:
            print(
                "📥 Google SheetsからKnowledgeを取得しています... "
                f"({attempt}/{retries})"
            )
            sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)
            records = sheet.get_all_records()
            print(f"✅ Google Sheets取得完了: {len(records)}行")
            return records
        except (SpreadsheetNotFound, WorksheetNotFound) as error:
            raise RuntimeError(
                "Spreadsheetまたはknowledgeシートが見つかりません。"
            ) from error
        except APIError as error:
            status_code = get_status_code(error)
            print(
                "⚠️ Google Sheets API error "
                f"({attempt}/{retries}) HTTP={status_code}: {error}"
            )
            if status_code in PERMANENT_HTTP_STATUSES:
                raise
            if status_code is not None and not (
                status_code in {408, 429} or status_code >= 500
            ):
                raise
        except (
            TimeoutError,
            ConnectionError,
            TransportError,
            RequestsConnectionError,
            RequestsTimeout,
        ) as error:
            print(
                "⚠️ Google Sheets の一時的な通信エラー "
                f"({attempt}/{retries}): {error}"
            )

        if attempt >= retries:
            break

        wait_seconds = base_delay * attempt
        print(f"🔄 {wait_seconds}秒後に再試行します...")
        time.sleep(wait_seconds)

    raise RuntimeError(
        "Google Sheets APIからKnowledgeデータを取得できませんでした。"
    )


def write_json_atomically(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            json.dump(value, temp_file, ensure_ascii=False, indent=2)
            temp_file.write("\n")
            temp_file.flush()
            os.fsync(temp_file.fileno())
            temp_path = Path(temp_file.name)
        os.replace(temp_path, path)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


def main() -> None:
    records = get_knowledge_records_with_retry()
    knowledge: dict[str, list[str]] = {}

    for row in records:
        title = str(row.get("title", "")).strip()
        content = str(row.get("content", "")).strip()
        if not title or not content:
            continue
        knowledge[title] = [content]

    if not knowledge:
        raise RuntimeError("knowledge シートに有効なデータがありません。")

    write_json_atomically(KNOWLEDGE_PATH, knowledge)
    print(f"✅ {KNOWLEDGE_PATH} を保存しました（{len(knowledge)}件）。")


if __name__ == "__main__":
    main()
