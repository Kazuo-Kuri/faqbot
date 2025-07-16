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

    def get_films_for_color(self, color_names):
        matched = set()
        for product, films in self.data.items():
            for film, colors in films.items():
                if any(c in colors for c in color_names):
                    matched.add(film)
        if matched:
            return {
                "matched": True,
                "type": "color_to_films",
                "color": ", ".join(color_names),
                "films": list(matched)
            }
        return {"matched": False, "message": "該当する印刷色が見つかりませんでした。"}

    def get_products_for_color(self, color_names):
        matched_products = set()
        for product, films in self.data.items():
            for colors in films.values():
                if any(c in colors for c in color_names):
                    matched_products.add(product)
        if matched_products:
            return {
                "matched": True,
                "type": "color_to_products",
                "color": ", ".join(color_names),
                "products": list(matched_products)
            }
        return {"matched": False, "message": "該当する印刷色に対応する製品が見つかりませんでした。"}

    def get_film_colors_for_color(self, color_names):
        matched_colors = set()
        for product, films in self.data.items():
            for film, colors in films.items():
                if any(c in colors for c in color_names):
                    matched_colors.add(film)
        if matched_colors:
            return {
                "matched": True,
                "type": "color_to_film_colors",
                "color": ", ".join(color_names),
                "film_colors": list(matched_colors)
            }
        return {"matched": False, "message": "印刷色に対応するフィルム色が見つかりませんでした。"}

    def match(self, user_input, history=None):
        keywords = extract_keywords(user_input)

        products = keywords.get("product", [])
        films = keywords.get("film", [])
        colors = keywords.get("color", [])

        if products and films and colors:
            for p in products:
                for f in films:
                    info = self.get_colors_for_film_in_product(p, f)
                    if info["matched"] and any(c in info["colors"] for c in colors):
                        return info

        if products and films:
            for p in products:
                for f in films:
                    info = self.get_colors_for_film_in_product(p, f)
                    if info["matched"]:
                        return info

        if products:
            for p in products:
                result = self.get_films_for_product(p)
                if result["matched"]:
                    return result

        if films:
            for f in films:
                result = self.get_products_for_film(f)
                if result["matched"]:
                    return result

        if colors:
            for getter in [
                self.get_products_for_color,
                self.get_film_colors_for_color,
                self.get_films_for_color
            ]:
                result = getter(colors)
                if result["matched"]:
                    return result

        return {"matched": False, "type": "no_match", "message": "製品・フィルム・色のいずれも見つかりませんでした。"}

    def format_match_info(self, info):
        if not isinstance(info, dict):
            return ""

        match_type = info.get("type")
        lines = ["【製品フィルム・カラー情報】"]

        if match_type == "product_to_films":
            lines.append(f"- 製品「{info['product']}」で選択可能なフィルム：")
            lines.append(f"- {', '.join(info['films'])}")

        elif match_type == "product_film_to_colors":
            lines.append(f"- 「{info['product']} × {info['film']}」で使用可能な印刷色：")
            lines.append(f"- {', '.join(info['colors'])}")

        elif match_type == "film_to_products":
            lines.append(f"- フィルム「{info['film']}」が使用できる製品：")
            lines.append(f"- {', '.join(info['products'])}")

        elif match_type == "color_to_films":
            lines.append(f"- 印刷色「{info['color']}」に対応可能なフィルム：")
            lines.append(f"- {', '.join(info['films'])}")

        elif match_type == "color_to_products":
            lines.append(f"- 印刷色「{info['color']}」に対応可能な製品：")
            lines.append(f"- {', '.join(info['products'])}")
            lines.append(f"\nこれらの製品では、{info['color']}の印刷色を**選択**することが可能です。")

        elif match_type == "color_to_film_colors":
            lines.append(f"- 印刷色「{info['color']}」に対応可能なフィルム（製品問わず）：")
            lines.append(f"- {', '.join(info['film_colors'])}")

        return "\n".join(lines)
