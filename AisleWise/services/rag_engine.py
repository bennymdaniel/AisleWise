from .retriever import (
    search_products,
    search_category,
    alternative_products,
    cheapest_products,
    list_products,
    low_stock_products,
    product_location_lookup,
    recommend_products_by_category,
    recommend_cheaper_alternatives,
    recommend_products_under_budget,
)
from .llm import generate_response


def build_context(products):
    if not products:
        return "No matching store products were found."

    lines = []
    for product in products[:8]:
        description = product["description"] if product["description"] else "No description available."
        lines.append(
            "Product:\n"
            f"Name: {product['name']}\n"
            f"Category: {product['category']}\n"
            f"Price: ₹{product['price']:.2f}\n"
            f"Stock: {product['stock']}\n"
            f"Aisle: {product['aisle']}\n"
            f"Description: {description}\n"
        )
    return "\n".join(lines)


def answer_customer_question(query):
    query_lower = query.lower()
    products = []
    fallback_message = (
        "Please ask store related questions. For example:\n"
        "1. What products do we have?\n"
        "2. Where are washrooms?\n"
        "3. Where is milk?\n"
        "4. Where can I find bread?\n"
        "5. What is the cheapest product?"
    )

    catalog_request = any(
        phrase in query_lower
        for phrase in [
            "what products",
            "what do you have",
            "what's available",
            "whats available",
            "available products",
            "show products",
            "list products",
            "what items",
            "what stock",
        ]
    )

    if catalog_request:
        products = list_products()
    elif "where" in query_lower or "find" in query_lower or "aisle" in query_lower:
        products = product_location_lookup(query)
    elif "under" in query_lower or "below" in query_lower or "₹" in query_lower:
        budget = 100
        words = [w.replace("₹", "") for w in query_lower.split() if "₹" in w or w.isdigit()]
        if words:
            try:
                budget = int(words[-1])
            except ValueError:
                budget = 100
        products = recommend_products_under_budget(budget)
    elif "cheapest" in query_lower:
        products = cheapest_products()
    elif "alternative" in query_lower or "alternatives" in query_lower:
        words = query_lower.replace("alternatives to", "").strip().split()
        if words:
            products = alternative_products(" ".join(words))
        else:
            products = cheapest_products()
    elif "healthy" in query_lower or "gluten-free" in query_lower or "gluten free" in query_lower:
        products = search_category("snacks")
    elif "category" in query_lower or any(cat in query_lower for cat in ["dairy", "snacks", "beverages", "bakery", "frozen", "personal care", "household"]):
        products = search_category(query_lower)
    else:
        return fallback_message

    context = build_context(products)
    return generate_response(query, context)


def quick_context(query):
    products = search_products(query)
    if not products:
        products = cheapest_products()
    return build_context(products)
