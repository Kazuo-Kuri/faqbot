import re

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
    # 色名（表記ゆれを含む）
    color_variants = {
        "黒": ["黒", "ブラック"],
        "白": ["白", "ホワイト"],
        "赤": ["赤", "レッド"],
        "青": ["青", "ブルー"],
        "茶": ["茶", "ブラウン"],
        "ゴールド": ["ゴールド", "金", "金色"],
        "シルバー": ["シルバー", "銀", "銀色"]
    }

    def find_keyword(text, candidates):
        for item in candidates:
            if item in text:
                return item
        return None

    def find_color(text):
        for canonical, variants in color_variants.items():
            for variant in variants:
                if variant in text:
                    return canonical
        return None

    found_product = find_keyword(text, products)
    found_film = find_keyword(text, films)
    found_color = find_color(text)

    return {
        "product": found_product,
        "film": found_film,
        "color": found_color
    }
