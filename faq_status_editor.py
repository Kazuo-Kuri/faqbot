import json
import os

FILE_PATH = "faq_suggestions.json"
STATUSES = ["未回答", "保留", "対応済"]

# JSON読み込み
if not os.path.exists(FILE_PATH):
    print("❌ faq_suggestions.json が見つかりません")
    exit()

with open(FILE_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

# デフォルトステータスを補完
for item in data:
    if "status" not in item:
        item["status"] = "未回答"

while True:
    print("\n--- FAQ Suggestion List ---")
    for i, item in enumerate(data):
        print(f"{i+1}. [{item['status']}] {item['question']} (count: {item['count']})")

    choice = input("\n番号を選んで status を変更（Enterで終了）: ").strip()
    if choice == "":
        break

    try:
        idx = int(choice) - 1
        if 0 <= idx < len(data):
            print("新しいステータスを選択:")
            for i, status in enumerate(STATUSES):
                print(f"  {i+1}. {status}")
            status_choice = input("番号を入力: ").strip()
            if status_choice.isdigit() and 1 <= int(status_choice) <= len(STATUSES):
                data[idx]["status"] = STATUSES[int(status_choice) - 1]
                print("✅ 更新されました")
            else:
                print("⚠️ 無効な選択です")
        else:
            print("⚠️ 番号が範囲外です")
    except ValueError:
        print("⚠️ 数字を入力してください")

# 保存
with open(FILE_PATH, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
print("\n💾 保存完了: faq_suggestions.json")
