from database.db import query_db


def search_products(query, limit=6):
    search = f"%{query.lower()}%"
    return query_db(
        "SELECT * FROM products WHERE LOWER(name) LIKE ? OR LOWER(category) LIKE ? OR LOWER(aisle) LIKE ? ORDER BY stock DESC LIMIT ?",
        (search, search, search, limit)
    )


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
