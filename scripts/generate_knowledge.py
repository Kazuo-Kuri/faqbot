import json
import os
import time

import faiss
import gspread
import numpy as np
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from openai import OpenAI, OpenAIError, RateLimitError


# =========================================================
# 環境変数読み込み
# =========================================================

# GitHub Actions 以外のローカル実行時のみ .env を読み込む
if os.getenv("GITHUB_ACTIONS") != "true":
    load_dotenv()


# =========================================================
# OpenAI API設定
# =========================================================

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY is not set.")

client = OpenAI(api_key=OPENAI_API_KEY)


# =========================================================
# Google Sheets 認証
# =========================================================

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

credentials = Credentials.from_service_account_file(
    "credentials.json",
    scopes=SCOPES,
)

gc = gspread.authorize(credentials)


# =========================================================
# スプレッドシート設定
# =========================================================

SPREADSHEET_ID = "1ApH-A58jUCZSKwTBAyuPZlZTNsv_2RwKGSqZNyaHHfk"
SHEET_NAME = "knowledge"

spreadsheet = gc.open_by_key(SPREADSHEET_ID)
sheet = spreadsheet.worksheet(SHEET_NAME)


# =========================================================
# スプレッドシート読み込み
# =========================================================

records = sheet.get_all_records()

knowledge: dict[str, list[str]] = {}

for row in records:
    title = str(row.get("title", "")).strip()
    content = str(row.get("content", "")).strip()

    # title または content が空の行は除外
    if not title or not content:
        continue

    knowledge[title] = [content]


if not knowledge:
    raise RuntimeError(
        "knowledge シートに有効なデータがありません。"
    )


# =========================================================
# knowledge.json 保存
# =========================================================

os.makedirs("data", exist_ok=True)

knowledge_path = "data/knowledge.json"

with open(
    knowledge_path,
    "w",
    encoding="utf-8",
) as f:
    json.dump(
        knowledge,
        f,
        ensure_ascii=False,
        indent=2,
    )

print(f"✅ {knowledge_path} を保存しました。")


# =========================================================
# Embedding用テキスト生成
# =========================================================

texts: list[str] = [
    f"{title}：{content[0]}"
    for title, content in knowledge.items()
]

EMBED_MODEL = "text-embedding-3-small"
BATCH_SIZE = 100


# =========================================================
# Embedding取得関数
# =========================================================

def get_embeddings_batch(
    text_batch: list[str],
    retries: int = 3,
    delay: int = 3,
) -> list[np.ndarray]:
    """
    OpenAI Embeddings APIからベクトルを取得する。

    一時的なOpenAI APIエラーは再試行する。
    RateLimit / quotaエラーは再試行せず終了する。
    """

    for attempt in range(1, retries + 1):
        try:
            response = client.embeddings.create(
                model=EMBED_MODEL,
                input=text_batch,
            )

            vectors: list[np.ndarray] = [
                np.asarray(
                    item.embedding,
                    dtype=np.float32,
                )
                for item in response.data
            ]

            return vectors

        except RateLimitError as e:
            print("")
            print("❌ OpenAI API の利用上限または残高不足です。")
            print(f"詳細: {e}")
            print("")
            print(
                "OpenAI Platform の Billing を確認してください。"
            )

            # クレジット切れの場合、
            # リトライしても解消しないため即終了
            raise

        except OpenAIError as e:
            print(
                f"⚠️ OpenAI API error "
                f"(attempt {attempt}/{retries}): {e}"
            )

            if attempt >= retries:
                raise RuntimeError(
                    "OpenAI APIへの接続に複数回失敗しました。"
                ) from e

            print(
                f"🔄 {delay}秒後に再試行します..."
            )

            time.sleep(delay)

        except Exception as e:
            print(
                f"❌ 予期しないエラーが発生しました: {e}"
            )
            raise

    # 型チェック対策
    raise RuntimeError(
        "Embedding取得処理が予期せず終了しました。"
    )


# =========================================================
# ベクトル生成
# =========================================================

print("🔄 ベクトルを再生成しています...")

all_vectors: list[np.ndarray] = []

for i in range(
    0,
    len(texts),
    BATCH_SIZE,
):
    batch = texts[
        i:i + BATCH_SIZE
    ]

    vectors = get_embeddings_batch(batch)

    all_vectors.extend(vectors)

    processed = min(
        i + len(batch),
        len(texts),
    )

    print(
        f"✅ Processed {processed}/{len(texts)}"
    )


# =========================================================
# ベクトルチェック
# =========================================================

if not all_vectors:
    raise RuntimeError(
        "Embeddingデータが生成されませんでした。"
    )


# =========================================================
# NumPy配列へ変換
# =========================================================

vector_data = np.asarray(
    all_vectors,
    dtype=np.float32,
)

if vector_data.ndim != 2:
    raise RuntimeError(
        f"vector_data の形式が不正です。"
        f" shape={vector_data.shape}"
    )


# =========================================================
# FAISSインデックス生成
# =========================================================

dimension = int(vector_data.shape[1])

index = faiss.IndexFlatL2(dimension)

# faiss の型定義とPylanceの相性により
# 誤検出される場合があるため type: ignore を指定
index.add(vector_data)  # type: ignore


# =========================================================
# ベクトルデータ保存
# =========================================================

vector_path = "data/vector_data.npy"
index_path = "data/index.faiss"

np.save(
    vector_path,
    vector_data,
)

faiss.write_index(
    index,
    index_path,
)


# =========================================================
# 完了
# =========================================================

print("")
print(f"✅ ベクトルデータを保存しました: {vector_path}")
print(f"✅ FAISSインデックスを保存しました: {index_path}")
print("")
print(
    "🎉 knowledge.json とベクトルデータの更新が完了しました。"
)