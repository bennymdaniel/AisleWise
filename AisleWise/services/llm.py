import requests

from config import GEMINI_API_KEY, GEMINI_API_URL, GEMINI_MODEL


def _build_prompt(query, context=""):
    prompt = (
        "You are a helpful grocery store assistant. "
        "Answer clearly, briefly, and only using the provided store context when relevant.\n\n"
    )
    if context:
        prompt += f"Store context:\n{context}\n\n"
    prompt += f"Customer question: {query}\n\nAnswer:"
    return prompt


def generate_response(query, context=""):
    placeholder_key = GEMINI_API_KEY.lower().startswith(("replace_with_", "your_"))
    if not GEMINI_API_KEY or placeholder_key:
        return "The AI assistant is not configured yet. Please add your Gemini API key to the .env file."

    url = f"{GEMINI_API_URL}?key={GEMINI_API_KEY}"
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": _build_prompt(query, context)}],
            }
        ],
        "generationConfig": {
            "temperature": 0.4,
            "maxOutputTokens": 512,
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
            if text:
                return text
        return "I could not generate a response right now. Please try again."
    except requests.RequestException:
        return f"I could not reach the Gemini API using model {GEMINI_MODEL}. Please check your .env settings and network connection."