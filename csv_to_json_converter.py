import csv
import json

csv_file = "faq.csv"
json_file = "faq_data.json"

faq_list = []

with open(csv_file, "r", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    for row in reader:
        if "question" in row and "answer" in row:
            faq = {
                "question": row["question"].strip(),
                "answer": row["answer"].strip()
            }
            if "category" in row:
                faq["category"] = row["category"].strip()
            faq_list.append(faq)
        else:
            raise ValueError("CSVには 'question' と 'answer' の列が必要です")

with open(json_file, "w", encoding="utf-8") as f:
    json.dump(faq_list, f, ensure_ascii=False, indent=2)

print(f"'{json_file}' に変換完了しました。")