import re

def extract_keywords(text):
    # 前処理：表記揺れや類義語を統一
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
    for k, v in normalize_map.items():
        text = text.replace(k, v)

    # 色キーワード
    color_keywords = ["黒", "青", "赤", "茶", "白", "シルバー", "ゴールド"]

    # 製品やフィルムのキーワードは省略（必要に応じて追加）
    product_keywords = ["X型", "X増量タイプ", "VFR型", "VFR増量タイプ", "ディップスタイル", "個包装コーヒーバッグ"]
    film_keywords = ["白光沢フィルム", "白マットフィルム", "黒光沢フィルム", "黒マットフィルム", "赤フィルム",
                     "クラフト包材", "紙リサイクルマーク付き包材", "ハイバリア特殊紙"]

    result = {"product": [], "film": [], "color": []}

    for word in product_keywords:
        if word in text:
            result["product"].append(word)

    for word in film_keywords:
        if word in text:
            result["film"].append(word)

    for word in color_keywords:
        if word in text:
            result["color"].append(word)

    return result
