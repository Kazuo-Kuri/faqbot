import os
import json
import time

import numpy as np
import faiss

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from openai import OpenAI, OpenAIError, RateLimitError


# =========================================================
# ローカル実行時のみ .env を読み込む
# =========================================================

if os.getenv("GITHUB_ACTIONS") != "true":
    from dotenv import load_dotenv

    load_dotenv()


# =========================================================
# OpenAI API設定
# =========================================================

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    raise ValueError(
        "OPENAI_API_KEY is not set or empty."
    )

client = OpenAI(
    api_key=OPENAI_API_KEY
)


# =========================================================
# Google認証
# =========================================================

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly"
]

with open(
    "credentials.json",
    "r",
    encoding="utf-8",
) as f:
    credentials_info = json.load(f)

credentials = service_account.Credentials.from_service_account_info(
    credentials_info,
    scopes=SCOPES,
)


# =========================================================
# Google Sheets設定
# =========================================================

SPREADSHEET_ID = (
    os.getenv("SPREADSHEET_ID")
    or "1ApH-A58jUCZSKwTBAyuPZlZTNsv_2RwKGSqZNyaHHfk"
)

RANGE_NAME = "FAQ!A1:C"


sheet_service = build(
    "sheets",
    "v4",
    credentials=credentials,
    cache_discovery=False,
).spreadsheets()


# =========================================================
# Google Sheets取得
# リトライ対応
# =========================================================

def get_sheet_values_with_retry(
    retries: int = 4,
    base_delay: int = 5,
) -> list[list[str]]:
    """
    Google Sheets APIからFAQデータを取得する。

    TimeoutError や一時的なGoogle APIエラーの場合、
    数回リトライしてから失敗させる。
    """

    for attempt in range(1, retries + 1):
        try:
            print(
                f"📥 Google SheetsからFAQを取得しています..."
                f" ({attempt}/{retries})"
            )

            result = (
                sheet_service
                .values()
                .get(
                    spreadsheetId=SPREADSHEET_ID,
                    range=RANGE_NAME,
                )
                .execute()
            )

            values = result.get(
                "values",
                [],
            )

            print(
                f"✅ Google Sheets取得完了: "
                f"{len(values)}行"
            )

            return values

        except TimeoutError as e:
            print(
                f"⚠️ Google Sheets API timeout "
                f"({attempt}/{retries}): {e}"
            )

        except HttpError as e:
            status_code = (
                e.resp.status
                if e.resp is not None
                else None
            )

            print(
                f"⚠️ Google Sheets API error "
                f"({attempt}/{retries}) "
                f"HTTP={status_code}: {e}"
            )

            # 認証・権限・存在しないSheetなど、
            # リトライしても改善しにくいエラー
            if status_code in {
                400,
                401,
                403,
                404,
            }:
                raise

        except Exception as e:
            print(
                f"⚠️ Google Sheets取得中に"
                f"予期しないエラー "
                f"({attempt}/{retries}): {e}"
            )

        if attempt >= retries:
            break

        # 5秒 → 10秒 → 15秒
        wait_seconds = base_delay * attempt

        print(
            f"🔄 {wait_seconds}秒後に再試行します..."
        )

        time.sleep(
            wait_seconds
        )

    raise RuntimeError(
        "Google Sheets APIからFAQデータを取得できませんでした。"
    )


values = get_sheet_values_with_retry()


# =========================================================
# faq.json生成
# =========================================================

faq_list: list[dict[str, str]] = []

# 1行目はヘッダー
for row in values[1:]:

    if len(row) < 2:
        continue

    question = str(row[0]).strip()
    answer = str(row[1]).strip()

    if not question or not answer:
        continue

    entry = {
        "question": question,
        "answer": answer,
    }

    if len(row) >= 3:
        category = str(row[2]).strip()

        if category:
            entry["category"] = category

    faq_list.append(
        entry
    )


if not faq_list:
    raise RuntimeError(
        "FAQシートから有効なFAQデータを取得できませんでした。"
    )


# =========================================================
# faq.json保存
# =========================================================

os.makedirs(
    "data",
    exist_ok=True,
)

FAQ_PATH = "data/faq.json"

with open(
    FAQ_PATH,
    "w",
    encoding="utf-8",
) as f:
    json.dump(
        faq_list,
        f,
        ensure_ascii=False,
        indent=2,
    )

print(
    f"✅ {FAQ_PATH} を保存しました。"
)


# =========================================================
# knowledge.json読み込み
# =========================================================

KNOWLEDGE_PATH = "data/knowledge.json"

if not os.path.exists(
    KNOWLEDGE_PATH
):
    raise FileNotFoundError(
        f"{KNOWLEDGE_PATH} が存在しません。"
    )

with open(
    KNOWLEDGE_PATH,
    "r",
    encoding="utf-8",
) as f:
    knowledge_dict = json.load(f)


knowledge_contents: list[str] = []

for category, texts in knowledge_dict.items():

    if not isinstance(
        texts,
        list,
    ):
        continue

    for text in texts:

        text_value = str(
            text
        ).strip()

        if not text_value:
            continue

        knowledge_contents.append(
            f"{category}：{text_value}"
        )


# =========================================================
# metadata読み込み
# =========================================================

metadata_note = ""

METADATA_PATH = "data/metadata.json"

if os.path.exists(
    METADATA_PATH
):
    with open(
        METADATA_PATH,
        "r",
        encoding="utf-8",
    ) as f:
        metadata = json.load(f)

    title = str(
        metadata.get(
            "title",
            "",
        )
    ).strip()

    metadata_type = str(
        metadata.get(
            "type",
            "",
        )
    ).strip()

    priority = str(
        metadata.get(
            "priority",
            "",
        )
    ).strip()

    if (
        title
        or metadata_type
        or priority
    ):
        metadata_note = (
            f"【ファイル情報】"
            f"{title}"
            f"（種類：{metadata_type}、"
            f"優先度：{priority}）"
        )


# =========================================================
# 検索対象テキスト作成
# =========================================================

search_corpus: list[str] = [
    item["question"]
    for item in faq_list
]

search_corpus.extend(
    knowledge_contents
)

# 空metadataはEmbedding対象にしない
if metadata_note:
    search_corpus.append(
        metadata_note
    )


if not search_corpus:
    raise RuntimeError(
        "Embedding対象データがありません。"
    )


# =========================================================
# Embedding設定
# =========================================================

EMBED_MODEL = "text-embedding-3-small"

BATCH_SIZE = 100


# =========================================================
# Embedding生成
# =========================================================

def get_embeddings_in_batches(
    texts: list[str],
    batch_size: int = BATCH_SIZE,
    retries: int = 3,
    base_delay: int = 5,
) -> np.ndarray:

    vectors: list[np.ndarray] = []

    total = len(texts)

    for start in range(
        0,
        total,
        batch_size,
    ):
        batch = texts[
            start:start + batch_size
        ]

        for attempt in range(
            1,
            retries + 1,
        ):
            try:
                response = (
                    client
                    .embeddings
                    .create(
                        model=EMBED_MODEL,
                        input=batch,
                    )
                )

                batch_vectors = [
                    np.asarray(
                        item.embedding,
                        dtype=np.float32,
                    )
                    for item
                    in response.data
                ]

                vectors.extend(
                    batch_vectors
                )

                processed = min(
                    start + len(batch),
                    total,
                )

                print(
                    f"✅ Embedding "
                    f"{processed}/{total}"
                )

                break

            # ---------------------------------------------
            # クレジット不足・Rate Limit
            # ---------------------------------------------

            except RateLimitError as e:

                error_text = str(e)

                print("")
                print(
                    "❌ OpenAI API RateLimit / "
                    "Quotaエラー"
                )
                print(
                    error_text
                )
                print("")

                # credit_balance_exhausted は
                # 再試行しても改善しない
                if (
                    "credit_balance_exhausted"
                    in error_text
                    or
                    "insufficient_quota"
                    in error_text
                    or
                    "no credits remaining"
                    in error_text.lower()
                ):
                    print(
                        "OpenAI APIのクレジット残高を"
                        "確認してください。"
                    )
                    raise

                if attempt >= retries:
                    raise

                wait_seconds = (
                    base_delay
                    * attempt
                )

                print(
                    f"🔄 {wait_seconds}秒後に"
                    f"再試行します..."
                )

                time.sleep(
                    wait_seconds
                )

            # ---------------------------------------------
            # その他OpenAI APIエラー
            # ---------------------------------------------

            except OpenAIError as e:

                print(
                    f"⚠️ OpenAI API error "
                    f"({attempt}/{retries}): {e}"
                )

                if attempt >= retries:
                    raise RuntimeError(
                        "OpenAI Embedding APIへの"
                        "接続に複数回失敗しました。"
                    ) from e

                wait_seconds = (
                    base_delay
                    * attempt
                )

                print(
                    f"🔄 {wait_seconds}秒後に"
                    f"再試行します..."
                )

                time.sleep(
                    wait_seconds
                )

        else:
            raise RuntimeError(
                "Embedding取得処理が"
                "予期せず終了しました。"
            )


    if not vectors:
        raise RuntimeError(
            "Embeddingベクトルが"
            "生成されませんでした。"
        )

    return np.asarray(
        vectors,
        dtype=np.float32,
    )


# =========================================================
# ベクトル再生成
# =========================================================

print(
    "🔄 ベクトルをバッチで再生成しています..."
)

vector_data = get_embeddings_in_batches(
    search_corpus
)


# =========================================================
# ベクトル形式チェック
# =========================================================

if vector_data.ndim != 2:
    raise RuntimeError(
        f"vector_data の形式が不正です。"
        f" shape={vector_data.shape}"
    )

if vector_data.shape[0] == 0:
    raise RuntimeError(
        "vector_data が空です。"
    )


# =========================================================
# FAISSインデックス生成
# =========================================================

dimension = int(
    vector_data.shape[1]
)

index = faiss.IndexFlatL2(
    dimension
)

# faiss-cpu の型定義とPylanceの不整合による
# reportCallIssue を回避
index.add(
    vector_data
)  # type: ignore


# =========================================================
# 保存
# =========================================================

VECTOR_PATH = "data/vector_data.npy"
INDEX_PATH = "data/index.faiss"

np.save(
    VECTOR_PATH,
    vector_data,
)

faiss.write_index(
    index,
    INDEX_PATH,
)


# =========================================================
# 完了
# =========================================================

print("")
print(
    f"✅ ベクトルデータを保存しました: "
    f"{VECTOR_PATH}"
)

print(
    f"✅ FAISSインデックスを保存しました: "
    f"{INDEX_PATH}"
)

print("")
print(
    "🎉 FAQ・Knowledge・FAISSインデックスの"
    "更新が完了しました。"
)