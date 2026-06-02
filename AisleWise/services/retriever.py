import difflib
import re

from database.db import query_db


def _normalize_text(value):
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()


def _score_product(query, product):
    query_text = _normalize_text(query)
    if not query_text:
        return 0.0

    fields = [
        product["name"],
        product["category"],
        product["aisle"],
        product["description"] or "",
    ]
    field_text = " ".join(_normalize_text(field) for field in fields if field)
    if not field_text:
        return 0.0

    best_ratio = max(
        difflib.SequenceMatcher(None, query_text, _normalize_text(field)).ratio()
        for field in fields
        if field
    )

    query_tokens = set(query_text.split())
    field_tokens = set(field_text.split())
    token_overlap = len(query_tokens & field_tokens)
    if query_tokens:
        best_ratio += (token_overlap / len(query_tokens)) * 0.25

    return min(best_ratio, 1.0)


def search_products(query, limit=6):
    search = f"%{query.lower()}%"
    return query_db(
        "SELECT * FROM products WHERE LOWER(name) LIKE ? OR LOWER(category) LIKE ? OR LOWER(aisle) LIKE ? ORDER BY stock DESC LIMIT ?",
        (search, search, search, limit)
    )


def search_products_fuzzy(query, limit=6, threshold=0.45):
    products = query_db("SELECT * FROM products")
    ranked = [
        (product, _score_product(query, product))
        for product in products
    ]
    ranked = [item for item in ranked if item[1] >= threshold]
    ranked.sort(key=lambda item: item[1], reverse=True)
    return [product for product, _score in ranked[:limit]]


def search_category(category, limit=8):
    search = f"%{category.lower()}%"
    return query_db(
        "SELECT * FROM products WHERE LOWER(category) LIKE ? ORDER BY price ASC LIMIT ?",
        (search, limit)
    )


def cheapest_products(limit=5):
    return query_db(
        "SELECT * FROM products ORDER BY price ASC LIMIT ?",
        (limit,)
    )


def list_products(limit=8):
    return query_db(
        "SELECT * FROM products ORDER BY name ASC LIMIT ?",
        (limit,)
    )


def low_stock_products(limit=6):
    return query_db(
        "SELECT * FROM products WHERE stock < 5 ORDER BY stock ASC LIMIT ?",
        (limit,)
    )


def product_location_lookup(product_name, limit=5):
    search = f"%{product_name.lower()}%"
    return query_db(
        "SELECT * FROM products WHERE LOWER(name) LIKE ? ORDER BY stock DESC LIMIT ?",
        (search, limit)
    )


def alternative_products(product_name, limit=6):
    product = query_db(
        "SELECT * FROM products WHERE LOWER(name) = ? LIMIT 1",
        (product_name.lower(),),
        one=True
    )
    if product is None:
        return []
    return query_db(
        "SELECT * FROM products WHERE LOWER(category) = ? AND LOWER(name) != ? ORDER BY price ASC LIMIT ?",
        (product["category"].lower(), product_name.lower(), limit)
    )


def recommend_products_by_category(category, limit=6):
    return search_category(category, limit)


def recommend_cheaper_alternatives(product_name, limit=5):
    product = query_db(
        "SELECT * FROM products WHERE LOWER(name) = ? LIMIT 1",
        (product_name.lower(),),
        one=True
    )
    if not product:
        return []
    return query_db(
        "SELECT * FROM products WHERE LOWER(category) = ? AND price < ? ORDER BY price ASC LIMIT ?",
        (product["category"].lower(), product["price"], limit)
    )


def recommend_products_under_budget(budget, category=None, limit=6):
    if category:
        return query_db(
            "SELECT * FROM products WHERE price <= ? AND LOWER(category) LIKE ? ORDER BY price ASC LIMIT ?",
            (budget, f"%{category.lower()}%", limit)
        )
    return query_db(
        "SELECT * FROM products WHERE price <= ? ORDER BY price ASC LIMIT ?",
        (budget, limit)
    )
