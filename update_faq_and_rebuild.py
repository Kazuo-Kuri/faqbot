import json
import os
import tempfile
import time
from pathlib import Path

import faiss
import numpy as np
from google.auth.exceptions import TransportError
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from openai import OpenAI, OpenAIError, RateLimitError


if os.getenv("GITHUB_ACTIONS") != "true":
    from dotenv import load_dotenv

    load_dotenv()


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY is not set or empty.")

client = OpenAI(api_key=OPENAI_API_KEY)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
SPREADSHEET_ID = (
    os.getenv("SPREADSHEET_ID")
    or "1ApH-A58jUCZSKwTBAyuPZlZTNsv_2RwKGSqZNyaHHfk"
)
RANGE_NAME = "FAQ!A1:C"
FAQ_PATH = Path("data/faq.json")
KNOWLEDGE_PATH = Path("data/knowledge.json")
METADATA_PATH = Path("data/metadata.json")
VECTOR_PATH = Path("data/vector_data.npy")
INDEX_PATH = Path("data/index.faiss")
EMBED_MODEL = "text-embedding-3-small"
BATCH_SIZE = 100
PERMANENT_GOOGLE_HTTP_STATUSES = {400, 401, 403, 404}


def build_sheet_service():
    with open("credentials.json", "r", encoding="utf-8") as file:
        credentials_info = json.load(file)

    credentials = service_account.Credentials.from_service_account_info(
        credentials_info,
        scopes=SCOPES,
    )
    return build(
        "sheets",
        "v4",
        credentials=credentials,
        cache_discovery=False,
    ).spreadsheets()


def get_sheet_values_with_retry(
    sheet_service,
    retries: int = 4,
    base_delay: int = 5,
) -> list[list[str]]:
    """FAQを取得し、タイムアウト・429・5xxのみ再試行する。"""
    for attempt in range(1, retries + 1):
        try:
            print(
                "📥 Google SheetsからFAQを取得しています... "
                f"({attempt}/{retries})"
            )
            result = (
                sheet_service.values()
                .get(spreadsheetId=SPREADSHEET_ID, range=RANGE_NAME)
                .execute()
            )
            values = result.get("values", [])
            print(f"✅ Google Sheets取得完了: {len(values)}行")
            return values
        except HttpError as error:
            status_code = getattr(error.resp, "status", None)
            print(
                "⚠️ Google Sheets API error "
                f"({attempt}/{retries}) HTTP={status_code}: {error}"
            )
            if status_code in PERMANENT_GOOGLE_HTTP_STATUSES:
                raise
            if status_code is not None and not (
                status_code in {408, 429} or status_code >= 500
            ):
                raise
        except (TimeoutError, ConnectionError, OSError, TransportError) as error:
            print(
                "⚠️ Google Sheets の一時的な通信エラー "
                f"({attempt}/{retries}): {error}"
            )

        if attempt >= retries:
            break

        wait_seconds = base_delay * attempt
        print(f"🔄 {wait_seconds}秒後に再試行します...")
        time.sleep(wait_seconds)

    raise RuntimeError("Google Sheets APIからFAQデータを取得できませんでした。")


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


def build_faq_list(values: list[list[str]]) -> list[dict[str, str]]:
    faq_list: list[dict[str, str]] = []
    for row in values[1:]:
        if len(row) < 2:
            continue
        question = str(row[0]).strip()
        answer = str(row[1]).strip()
        if not question or not answer:
            continue

        entry = {"question": question, "answer": answer}
        if len(row) >= 3:
            category = str(row[2]).strip()
            if category:
                entry["category"] = category
        faq_list.append(entry)

    if not faq_list:
        raise RuntimeError("FAQシートから有効なFAQデータを取得できませんでした。")
    return faq_list


def load_knowledge_contents() -> list[str]:
    if not KNOWLEDGE_PATH.exists():
        raise FileNotFoundError(f"{KNOWLEDGE_PATH} が存在しません。")

    with KNOWLEDGE_PATH.open("r", encoding="utf-8") as file:
        knowledge_dict = json.load(file)

    if not isinstance(knowledge_dict, dict):
        raise RuntimeError("knowledge.json の形式が不正です。")

    contents: list[str] = []
    for category, texts in knowledge_dict.items():
        if not isinstance(texts, list):
            continue
        category_value = str(category).strip()
        for text in texts:
            text_value = str(text).strip()
            if category_value and text_value:
                contents.append(f"{category_value}：{text_value}")

    if not contents:
        raise RuntimeError("knowledge.json に有効なKnowledgeがありません。")
    return contents


def load_metadata_note() -> str:
    if not METADATA_PATH.exists():
        return ""

    with METADATA_PATH.open("r", encoding="utf-8") as file:
        metadata = json.load(file)

    if not isinstance(metadata, dict):
        raise RuntimeError("metadata.json の形式が不正です。")

    title = str(metadata.get("title", "")).strip()
    metadata_type = str(metadata.get("type", "")).strip()
    priority = str(metadata.get("priority", "")).strip()
    if not (title or metadata_type or priority):
        return ""

    return (
        f"【ファイル情報】{title}"
        f"（種類：{metadata_type}、優先度：{priority}）"
    )


def is_quota_exhausted(error: OpenAIError) -> bool:
    error_text = str(error).lower()
    body = getattr(error, "body", None)
    if body is not None:
        error_text += f" {body}".lower()
    return any(
        marker in error_text
        for marker in (
            "credit_balance_exhausted",
            "insufficient_quota",
            "no credits remaining",
        )
    )


def is_temporary_openai_error(error: OpenAIError) -> bool:
    status_code = getattr(error, "status_code", None)
    return status_code is None or status_code in {408, 409, 429} or status_code >= 500


def get_embeddings_in_batches(
    texts: list[str],
    batch_size: int = BATCH_SIZE,
    retries: int = 3,
    base_delay: int = 5,
) -> np.ndarray:
    vectors: list[np.ndarray] = []
    total = len(texts)

    for start in range(0, total, batch_size):
        batch = texts[start : start + batch_size]
        for attempt in range(1, retries + 1):
            try:
                response = client.embeddings.create(
                    model=EMBED_MODEL,
                    input=batch,
                )
                batch_vectors = [
                    np.asarray(item.embedding, dtype=np.float32)
                    for item in response.data
                ]
                if len(batch_vectors) != len(batch):
                    raise RuntimeError(
                        "Embedding APIの応答数が入力数と一致しません。 "
                        f"input={len(batch)}, response={len(batch_vectors)}"
                    )
                vectors.extend(batch_vectors)
                print(f"✅ Embedding {len(vectors)}/{total}")
                break
            except RateLimitError as error:
                if is_quota_exhausted(error):
                    print("❌ OpenAI APIのクレジット残高が不足しています。")
                    raise
                print(
                    "⚠️ OpenAI API rate limit "
                    f"({attempt}/{retries}): {error}"
                )
                if attempt >= retries:
                    raise RuntimeError(
                        "OpenAI Embedding APIへの接続に複数回失敗しました。"
                    ) from error
                wait_seconds = base_delay * attempt
                print(f"🔄 {wait_seconds}秒後に再試行します...")
                time.sleep(wait_seconds)
            except OpenAIError as error:
                if is_quota_exhausted(error):
                    print("❌ OpenAI APIのクレジット残高が不足しています。")
                    raise
                print(
                    "⚠️ OpenAI API error "
                    f"({attempt}/{retries}): {error}"
                )
                if not is_temporary_openai_error(error):
                    raise
                if attempt >= retries:
                    raise RuntimeError(
                        "OpenAI Embedding APIへの接続に複数回失敗しました。"
                    ) from error
                wait_seconds = base_delay * attempt
                print(f"🔄 {wait_seconds}秒後に再試行します...")
                time.sleep(wait_seconds)
        else:
            raise RuntimeError("Embedding取得処理が予期せず終了しました。")

    if not vectors:
        raise RuntimeError("Embeddingベクトルが生成されませんでした。")
    return np.asarray(vectors, dtype=np.float32)


def save_index_atomically(vector_data: np.ndarray, index) -> None:
    VECTOR_PATH.parent.mkdir(parents=True, exist_ok=True)
    vector_fd, vector_temp_name = tempfile.mkstemp(
        dir=VECTOR_PATH.parent,
        prefix=f".{VECTOR_PATH.name}.",
        suffix=".tmp.npy",
    )
    index_fd, index_temp_name = tempfile.mkstemp(
        dir=INDEX_PATH.parent,
        prefix=f".{INDEX_PATH.name}.",
        suffix=".tmp.faiss",
    )
    os.close(vector_fd)
    os.close(index_fd)
    vector_temp = Path(vector_temp_name)
    index_temp = Path(index_temp_name)

    try:
        np.save(vector_temp, vector_data)
        faiss.write_index(index, str(index_temp))

        saved_vectors = np.load(vector_temp)
        saved_index = faiss.read_index(str(index_temp))
        if saved_vectors.shape != vector_data.shape or saved_index.ntotal != index.ntotal:
            raise RuntimeError("一時保存したvector_dataとFAISS indexの検証に失敗しました。")

        os.replace(vector_temp, VECTOR_PATH)
        os.replace(index_temp, INDEX_PATH)
    finally:
        if vector_temp.exists():
            vector_temp.unlink()
        if index_temp.exists():
            index_temp.unlink()


def main() -> None:
    sheet_service = build_sheet_service()
    faq_list = build_faq_list(get_sheet_values_with_retry(sheet_service))
    write_json_atomically(FAQ_PATH, faq_list)
    print(f"✅ {FAQ_PATH} を保存しました。")

    knowledge_contents = load_knowledge_contents()
    metadata_note = load_metadata_note()

    # 検索順序: FAQ questions → Knowledge contents → metadata
    search_corpus = [item["question"] for item in faq_list]
    search_corpus.extend(knowledge_contents)
    if metadata_note:
        search_corpus.append(metadata_note)

    print(f"FAQ件数: {len(faq_list)}")
    print(f"Knowledge件数: {len(knowledge_contents)}")
    print(f"metadata件数: {1 if metadata_note else 0}")
    print(f"総Embedding件数: {len(search_corpus)}")

    vector_data = get_embeddings_in_batches(search_corpus)
    if vector_data.ndim != 2 or vector_data.shape[0] == 0:
        raise RuntimeError(f"vector_data の形式が不正です。 shape={vector_data.shape}")

    index = faiss.IndexFlatL2(int(vector_data.shape[1]))
    index.add(vector_data)  # type: ignore

    corpus_count = len(search_corpus)
    vector_count = int(vector_data.shape[0])
    index_count = int(index.ntotal)
    print(f"FAISS index件数: {index_count}")
    if not (corpus_count == vector_count == index_count):
        raise RuntimeError(
            "検索コーパス・Embedding・FAISSの件数が一致しません。 "
            f"corpus={corpus_count}, vectors={vector_count}, index={index_count}"
        )

    save_index_atomically(vector_data, index)
    print(f"✅ ベクトルデータを保存しました: {VECTOR_PATH}")
    print(f"✅ FAISSインデックスを保存しました: {INDEX_PATH}")
    print("🎉 FAQ・Knowledge・metadata・FAISSインデックスの更新が完了しました。")


if __name__ == "__main__":
    main()
