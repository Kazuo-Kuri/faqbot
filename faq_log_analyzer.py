import json
import os
from collections import Counter
from difflib import SequenceMatcher

# ログファイルとFAQファイル
LOG_FILE = "log.txt"
FAQ_FILE = "faq_data.json"
OUTPUT_FILE = "faq_suggestions.json"

# 類似度のしきい値（既存FAQと70%以上似ていたら除外）
SIMILARITY_THRESHOLD = 0.7

# FAQの質問リスト読み込み
with open(FAQ_FILE, "r", encoding="utf-8") as f:
    faq_data = json.load(f)
    existing_questions = [item["question"] for item in faq_data]

# ログから質問だけを抽出
questions_logged = []
with open(LOG_FILE, "r", encoding="utf-8", errors="ignore") as f:
    for line in f:
        if "ユーザーの質問:" in line:
            q = line.strip().split("ユーザーの質問:")[-1].strip()
            if q:
                questions_logged.append(q)

# 質問の出現頻度カウント
counter = Counter(questions_logged)

# 既存FAQと比較し、類似度が低いものだけ抽出
suggestions = []
for question, freq in counter.most_common():
    similar = any(
        SequenceMatcher(None, question, existing_q).ratio() > SIMILARITY_THRESHOLD
        for existing_q in existing_questions
    )
    if not similar:
        suggestions.append({"question": question, "count": freq})

# 出力
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(suggestions, f, ensure_ascii=False, indent=2)

print(f"✅ FAQ追加候補を {OUTPUT_FILE} に出力しました（件数: {len(suggestions)}）")
