import json
import re
from functools import wraps

import requests

from config import GEMINI_API_KEY, GEMINI_API_URL, GEMINI_MODEL
from .retriever import (
    alternative_products,
    cheapest_products,
    list_products,
    low_stock_products,
    product_location_lookup,
    recommend_products_under_budget,
    search_category,
    search_products,
    search_products_fuzzy,
)


TOOLS = {}

STORE_PROMPT_TEMPLATE = """
You are Keryx, the AI shopping assistant of AisleWise.

Your primary responsibility is helping customers shop inside the supermarket.

Rules:
1. Only use information provided in the retrieved store context.
2. Never invent:
- Products
- Prices
- Stock quantities
- Aisle locations
- Discounts
- Categories
3. If information is not found in the store database, respond:
"I could not find that information in the current store database."
4. Recommend alternatives only from retrieved products.
5. Mention:
- Product name
- Price
- Stock availability
- Aisle location
when available.
6. Help users:
- Find products
- Compare products
- Discover alternatives
- Browse categories
- Find budget-friendly options
- Find healthy options
7. Stay strictly within the supermarket shopping domain.
8. Politely decline unrelated questions.

Example:
User: "Who won the World Cup?"
Response: "I'm designed to assist with shopping and store-related queries. I couldn't find that information in the store database."
""".strip()


def tool(func):
    """Register a callable as an agent tool."""
    TOOLS[func.__name__] = func
    return func


def _placeholder_api_key():
    return not GEMINI_API_KEY or GEMINI_API_KEY.lower().startswith(("replace_with_", "your_"))


def _normalize_text(value):
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()


def _build_prompt(query, context=""):
    prompt = STORE_PROMPT_TEMPLATE + "\n\n"
    if context:
        prompt += f"Store context:\n{context}\n\n"
    prompt += f"Customer question: {query}\n\nAnswer:"
    return prompt


def _tool_catalog():
    lines = []
    for name, func in TOOLS.items():
        doc = (func.__doc__ or "").strip().replace("\n", " ")
        lines.append(f"- {name}: {doc}")
    return "\n".join(lines)


def _call_gemini(prompt, temperature=0.2, max_output_tokens=512):
    if _placeholder_api_key():
        return None

    url = f"{GEMINI_API_URL}?key={GEMINI_API_KEY}"
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}],
            }
        ],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_output_tokens,
        },
    }

    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        candidates = data.get("candidates", [])
        if candidates:
            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            text = "".join(part.get("text", "") for part in parts).strip()
            return text or None
    except requests.RequestException:
        return None
    return None


def _extract_json(text):
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None


def _fallback_message():
    return "I could not find that information in the current store database."


def _format_products(products, limit=5):
    items = products[:limit]
    if not items:
        return None

    names = [item["name"] for item in items]
    if len(names) == 1:
        item = items[0]
        return f"{item['name']} is available in aisle {item['aisle']} for ₹{item['price']:.2f}."

    return "We have " + ", ".join(names[:-1]) + f", and {names[-1]}."


def _build_context(products):
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


@tool
def search_tool(query, limit=6):
    """Search the product database for a product, category, or aisle. Uses exact keyword matching first and fuzzy matching for misspelled words or close spellings. Returns exact matches directly; otherwise returns the nearest store results for the LLM to refine."""
    exact_matches = search_products(query, limit)
    if exact_matches:
        return {
            "mode": "context",
            "context": _build_context(exact_matches),
            "products": exact_matches,
        }

    fuzzy_matches = search_products_fuzzy(query, limit)
    if fuzzy_matches:
        return {
            "mode": "context",
            "context": _build_context(fuzzy_matches),
            "products": fuzzy_matches,
        }

    return {"mode": "none", "response": None, "products": []}


@tool
def list_products_tool(limit=8):
    """List the store catalog for broad questions like 'what products do you have?'. Use this when the user wants a general inventory overview."""
    products = list_products(limit)
    return {"mode": "context", "context": _build_context(products), "products": products}


@tool
def find_location_tool(query, limit=5):
    """Find the aisle or shelf location for a product or store place question like where milk is or where washrooms are."""
    products = product_location_lookup(query, limit)
    if not products:
        products = search_products_fuzzy(query, limit)
    if not products:
        return {"mode": "none", "response": None, "products": []}

    return {"mode": "context", "context": _build_context(products), "products": products}


def _normalize_tool_args(tool_name, args):
    normalized = dict(args or {})
    if tool_name in {"find_location_tool", "search_tool", "alternatives_tool"}:
        if "query" not in normalized and "product_name" in normalized:
            normalized["query"] = normalized.pop("product_name")
    return normalized


@tool
def cheapest_products_tool(limit=5):
    """Return the cheapest products in the store when the user asks for the lowest priced items."""
    products = cheapest_products(limit)
    return {"mode": "context", "context": _build_context(products), "products": products}


@tool
def search_category_tool(category, limit=8):
    """Search products by category such as dairy, snacks, beverages, bakery, frozen foods, personal care, or household."""
    products = search_category(category, limit)
    if not products:
        return {"mode": "none", "response": None, "products": []}
    return {"mode": "context", "context": _build_context(products), "products": products}


@tool
def low_stock_tool(limit=6):
    """Show products with low stock for restocking or inventory questions."""
    products = low_stock_products(limit)
    return {"mode": "context", "context": _build_context(products), "products": products}


@tool
def budget_tool(budget, category=None, limit=6):
    """Recommend products under a budget, optionally filtered by category."""
    products = recommend_products_under_budget(budget, category=category, limit=limit)
    return {"mode": "context", "context": _build_context(products), "products": products}


@tool
def alternatives_tool(query, limit=6):
    """Find alternative products or cheaper substitutes for a named product."""
    products = alternative_products(query, limit)
    if not products:
        return {"mode": "none", "response": None, "products": []}
    return {"mode": "context", "context": _build_context(products), "products": products}


def _heuristic_plan(query):
    query_lower = query.lower()
    if any(phrase in query_lower for phrase in ["what products", "what do you have", "available products", "show products", "list products", "what items", "what stock"]):
        return {"tool": "list_products_tool", "args": {"limit": 8}}
    if any(word in query_lower for word in ["where", "find", "aisle", "washroom", "toilet"]):
        return {"tool": "find_location_tool", "args": {"query": query, "limit": 5}}
    if "under" in query_lower or "below" in query_lower or "budget" in query_lower or "₹" in query_lower:
        digits = [token.replace("₹", "") for token in query_lower.split() if token.replace("₹", "").isdigit()]
        budget = int(digits[-1]) if digits else 100
        return {"tool": "budget_tool", "args": {"budget": budget, "limit": 6}}
    if "cheapest" in query_lower or "lowest" in query_lower:
        return {"tool": "cheapest_products_tool", "args": {"limit": 5}}
    if "alternative" in query_lower or "alternatives" in query_lower or "substitute" in query_lower:
        return {"tool": "alternatives_tool", "args": {"query": query, "limit": 6}}
    if "low stock" in query_lower or "restock" in query_lower:
        return {"tool": "low_stock_tool", "args": {"limit": 6}}
    category_matches = [category for category in ["dairy", "snacks", "beverages", "bakery", "frozen", "personal care", "household"] if category in query_lower]
    if category_matches:
        return {"tool": "search_category_tool", "args": {"category": category_matches[0], "limit": 8}}
    return {"tool": "search_tool", "args": {"query": query, "limit": 6}}


def _choose_tool(query):
    if not query or not query.strip():
        return {"tool": "fallback", "args": {}}

    prompt = (
        "You are a tool router for a grocery store assistant. Choose the best tool for the user query. "
        "Use the tool docstrings to decide.\n\n"
        f"Available tools:\n{_tool_catalog()}\n\n"
        "Return only valid JSON with this shape:\n"
        '{"tool": "tool_name_or_fallback", "args": {}}\n\n'
        f"User query: {query}"
    )
    raw = _call_gemini(prompt, temperature=0.0, max_output_tokens=128)
    plan = _extract_json(raw)
    if isinstance(plan, dict):
        tool_name = plan.get("tool")
        args = plan.get("args") or {}
        if tool_name in TOOLS:
            return {"tool": tool_name, "args": args}
        if tool_name == "fallback":
            return {"tool": "fallback", "args": {}}

    return _heuristic_plan(query)


def generate_response(query, context=""):
    if _placeholder_api_key():
        return "The AI assistant is not configured yet. Please add your Gemini API key to the .env file."

    prompt = _build_prompt(query, context)

    raw = _call_gemini(prompt, temperature=0.4, max_output_tokens=512)
    if raw:
        return raw
    return "I could not generate a response right now. Please try again."


def answer_customer_question(query):
    plan = _choose_tool(query)
    tool_name = plan.get("tool")

    if tool_name == "fallback":
        return {"response": generate_response(query, _fallback_message()), "products": []}

    tool_func = TOOLS.get(tool_name)
    if tool_func is None:
        return {"response": generate_response(query, _fallback_message()), "products": []}

    tool_args = _normalize_tool_args(tool_name, plan.get("args") or {})
    result = tool_func(**tool_args)
    mode = result.get("mode")
    products = result.get("products") or []

    serializable_products = []
    for p in products:
        serializable_products.append({
            "id": p["id"],
            "name": p["name"],
            "category": p["category"],
            "price": p["price"],
            "stock": p["stock"],
            "aisle": p["aisle"],
            "description": p["description"]
        })

    if (mode == "direct" and result.get("response")) or (mode == "context" and result.get("context")):
        context = result.get("context") or result.get("response") or _build_context(products)
        return {"response": generate_response(query, context), "products": serializable_products}

    if tool_name == "search_tool":
        return {"response": generate_response(query, _fallback_message()), "products": []}

    if products:
        return {"response": generate_response(query, _build_context(products)), "products": serializable_products}

    return {"response": generate_response(query, _fallback_message()), "products": []}


def quick_context(query):
    result = search_tool(query)
    if result.get("mode") == "context" and result.get("context"):
        return result["context"]
    if result.get("products"):
        return _build_context(result["products"])
    products = cheapest_products()
    return _build_context(products)