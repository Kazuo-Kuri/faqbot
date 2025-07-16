import re

# 製品・フィルム・色一覧
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

# 色名（正規化対応）
color_variants = {
    "黒": ["黒", "ブラック"],
    "白": ["白", "ホワイト"],
    "赤": ["赤", "レッド"],
    "青": ["青", "ブルー"],
    "茶": ["茶", "ブラウン"],
    "ゴールド": ["ゴールド", "金", "金色"],
    "シルバー": ["シルバー", "銀", "銀色"]
}

def normalize_colors(text):
    """文章中に含まれる色名を正規化して複数抽出"""
    found = []
    for canonical, variants in color_variants.items():
        if any(v in text for v in variants):
            found.append(canonical)
    return list(set(found))

def find_all_matches(text, candidates):
    """候補リストに含まれるすべてのキーワードを抽出"""
    return [item for item in candidates if item in text]

def extract_keywords(text):
    """製品・フィルム・色に関するキーワードを抽出"""
    found_products = find_all_matches(text, products)
    found_films = find_all_matches(text, films)
    found_colors = normalize_colors(text)

    return {
        "product": found_products,
        "film": found_films,
        "color": found_colors
    }
