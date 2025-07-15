import json
from keyword_filter import extract_keywords  # 追加：キーワード抽出を利用

class ProductFilmMatcher:
    def __init__(self, json_path="data/product_film_color_matrix.json"):
        with open(json_path, "r", encoding="utf-8") as f:
            self.data = json.load(f)

    def get_films_for_product(self, product_name):
        product = next((p for p in self.data if p in product_name), None)
        if not product:
            return {"matched": False, "message": "該当する製品種が見つかりませんでした。"}
        films = list(self.data[product].keys())
        return {
            "matched": True,
            "product": product,
            "films": films,
            "message": f"{product}で使用できるフィルムは：{', '.join(films)}です。"
        }

    def get_colors_for_film_in_product(self, product_name, film_name):
        for product, films in self.data.items():
            if product_name in product:
                for film, colors in films.items():
                    if film_name in film:
                        return {
                            "matched": True,
                            "product": product,
                            "film": film,
                            "colors": colors,
                            "message": f"{product}の{film}では以下の色が使用できます：{', '.join(colors)}。"
                        }
        return {"matched": False, "message": "該当する製品とフィルムの組み合わせが見つかりませんでした。"}

    def get_products_for_film(self, film_name):
        matched_products = []
        for product, films in self.data.items():
            if any(film_name in film for film in films):
                matched_products.append(product)
        if matched_products:
            return {
                "matched": True,
                "film": film_name,
                "products": matched_products,
                "message": f"{film_name}を使用できる製品は：{', '.join(matched_products)}です。"
            }
        return {"matched": False, "message": "該当するフィルムに対応する製品が見つかりませんでした。"}

    def get_films_for_color(self, color_name):
        matched = set()
        for product, films in self.data.items():
            for film, colors in films.items():
                if color_name in colors:
                    matched.add(film)
        if matched:
            return {
                "matched": True,
                "color": color_name,
                "films": list(matched),
                "message": f"{color_name}の印刷が可能なフィルムは：{', '.join(matched)}です。"
            }
        return {"matched": False, "message": "該当する印刷色が見つかりませんでした。"}

    # ✅ 統合版 match(): ユーザーの入力からキーワードを抽出し、最適な情報を返す
    def match(self, user_input):
        keywords = extract_keywords(user_input)

        # 色＋フィルム＋製品が全部ある場合（最も詳細な指定）
        if keywords["product"] and keywords["film"] and keywords["color"]:
            detail = self.get_colors_for_film_in_product(keywords["product"], keywords["film"])
            if detail["matched"]:
                return detail["message"]

        # 色 → フィルム（例：「シルバーは使えますか？」）
        if keywords["color"]:
            color_info = self.get_films_for_color(keywords["color"])
            if color_info["matched"]:
                return color_info["message"]

        # フィルム → 製品（例：「NY15を使える製品は？」）
        if keywords["film"]:
            film_info = self.get_products_for_film(keywords["film"])
            if film_info["matched"]:
                return film_info["message"]

        # 製品 → フィルム（例：「チャック袋で使えるフィルムは？」）
        if keywords["product"]:
            prod_info = self.get_films_for_product(keywords["product"])
            if prod_info["matched"]:
                return prod_info["message"]

        # どれにもマッチしなかった
        return None
