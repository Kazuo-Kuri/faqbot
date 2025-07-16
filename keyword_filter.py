import re

def extract_keywords(text):
    # 正規化マッピング
    normalize_map = {
        "シルバ": "シルバー",
        "金": "ゴールド",
        "銀": "シルバー",
        "白色": "白",
        "黒色": "黒",
        "赤色": "赤",
        "青色": "青",
        "茶色": "茶",
        "金色": "ゴールド",
        "銀色": "シルバー"
    }

    # 正規化処理（すべて統一表記に変換）
    for k, v in normalize_map.items():
        text = text.replace(k, v)

    # キーワード定義
    color_keywords = ["黒", "青", "赤", "茶", "白", "シルバー", "ゴールド"]
    product_keywords = ["X型", "X増量タイプ", "VFR型", "VFR増量タイプ", "ディップスタイル", "個包装コーヒーバッグ"]
    film_keywords = [
        "白光沢フィルム", "白マットフィルム", "黒光沢フィルム", "黒マットフィルム", "赤フィルム",
        "クラフト包材", "紙リサイクルマーク付き包材", "ハイバリア特殊紙"
    ]

    result = {"product": [], "film": [], "color": []}

    # キーワード検出（完全一致ではなく正規表現で柔軟に）
    for word in product_keywords:
        if re.search(re.escape(word), text):
            result["product"].append(word)

    for word in film_keywords:
        if re.search(re.escape(word), text):
            result["film"].append(word)

    for word in color_keywords:
        if re.search(re.escape(word), text):
            result["color"].append(word)

    print("🟡 抽出結果:", result)  # デバッグログ

    return result
