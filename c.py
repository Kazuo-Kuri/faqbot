import csv

csv_file = "faq.csv"

with open(csv_file, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    print("読み取られたフィールド名（列名）:", reader.fieldnames)
    for row in reader:
        print(row)
