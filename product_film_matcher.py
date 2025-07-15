import json
from keyword_filter import extract_keywords

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
            "type": "product_to_films",
            "product": product,
            "films": films
        }

    def get_colors_for_film_in_product(self, product_name, film_name):
        for product, films in self.data.items():
            if product_name in product:
                for film, colors in films.items():
                    if film_name in film:
                        return {
                            "matched": True,
                            "type": "product_film_to_colors",
                            "product": product,
                            "film": film,
                            "colors": colors
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
                "type": "film_to_products",
                "film": film_name,
                "products": matched_products
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
                "type": "color_to_films",
                "color": color_name,
                "films": list(matched)
            }
        return {"matched": False, "message": "該当する印刷色が見つかりませんでした。"}

    def match(self, user_input):
        keywords = extract_keywords(user_input)
        product = keywords.get("product")
        film = keywords.get("film")
        color = keywords.get("color")

        if product and film and color:
            # 3つ揃っている場合は色に対応するフィルムを確認
            color_info = self.get_colors_for_film_in_product(product, film)
            if color_info["matched"] and color in color_info.get("colors", []):
                return color_info

        if product and film:
            return self.get_colors_for_film_in_product(product, film)

        if product:
            return self.get_films_for_product(product)

        if film:
            return self.get_products_for_film(film)

        if color:
            return self.get_films_for_color(color)

        return {"matched": False, "message": "製品・フィルム・色のいずれも見つかりませんでした。"}
