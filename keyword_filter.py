def extract_keywords(text):
    products = [
        "VFR型", "VFR増量タイプ", "X型", "X増量タイプ",
        "ディップスタイル", "水出しコーヒー", "個包装コーヒーバッグ"
    ]
    films = [
        "白光沢フィルム", "白マットフィルム", "黒光沢フィルム", "黒マットフィルム",
        "赤フィルム", "青光沢フィルム", "青マットフィルム", "緑フィルム",
        "クラフト包材", "サンドベージュフィルム",
        "紙リサイクルマーク付き包材(アルミあり)", "ハイバリア特殊紙(アルミ無し)"
    ]
    colors = ["黒", "白", "赤", "青", "茶", "ゴールド", "金", "シルバー", "銀"]

    # ゆらぎマッピング（正規化）
    color_map = {"金": "ゴールド", "銀": "シルバー"}

    found_product = next((p for p in products if p in text), None)
    found_film = next((f for f in films if f in text), None)
    found_color = next((c for c in colors if c in text), None)

    # 色の正規化
    if found_color in color_map:
        found_color = color_map[found_color]

    return {
        "product": found_product,
        "film": found_film,
        "color": found_color
    }
