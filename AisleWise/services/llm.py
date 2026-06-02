import os
import re
import requests
from flask import current_app
from dotenv import load_dotenv

load_dotenv()

# Read model name from environment, default to user's requested model
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
# Use stable v1 endpoint
GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1/models/{model}:generate"

SYSTEM_PROMPT = (
    "You are Keryx, an AI supermarket assistant for AisleWise. "
    "Only answer using the information provided in the store context. "
    "Do not invent products or aisles. Recommend alternatives when appropriate. "
    "Mention aisle locations and prices when available. If information is unavailable, say so clearly."
)


def generate_response(query, context):
    api_key = os.environ.get("GEMINI_API_KEY")
    # Helpful guidance if user left placeholder in .env
    if not api_key or "YOUR_GEMINI" in api_key or api_key.strip() == "":
        return (
            "Keryx is unavailable because the Gemini API key is not configured or looks like a placeholder. "
            "Set `GEMINI_API_KEY` in your environment or .env (and restart the app)."
        )

    prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        f"Store Context:\n{context}\n\n"
        f"Customer Question: {query}\n\n"
        "Answer as a helpful supermarket assistant using only the store context."
    )

    url = GEMINI_ENDPOINT.format(model=os.environ.get("GEMINI_MODEL", GEMINI_MODEL))
    payload = {
        "prompt": {"text": prompt},
        "temperature": 0.2,
        "maxOutputTokens": 512,
        "topP": 0.95,
        "candidateCount": 1,
    }

    params = {"key": api_key}

    def _redact(text: str) -> str:
        if not text:
            return text
        try:
            redacted = re.sub(re.escape(api_key), "[REDACTED]", text)
        except Exception:
            redacted = text
        redacted = re.sub(r"(key=)[^&\s]+", r"\1[REDACTED]", redacted, flags=re.IGNORECASE)
        return redacted

    try:
        resp = requests.post(url, params=params, json=payload, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        # support both v1 and v1beta2 response shapes
        candidates = data.get("candidates") or data.get("outputs") or []
        if candidates:
            # v1beta2: candidates[0]['output'] ; v1: outputs[0]['content'][0]['text']
            first = candidates[0]
            if isinstance(first, dict) and "output" in first:
                return first.get("output")
            # v1 outputs structure
            outputs = data.get("outputs")
            if outputs and isinstance(outputs, list):
                # try to extract text content
                first_out = outputs[0]
                content = first_out.get("content") or []
                for c in content:
                    if c.get("type") == "text":
                        return c.get("text")
            # fallback
            return str(first)
    except requests.HTTPError as e:
        try:
            status = e.response.status_code
            body = e.response.text
            detail = f"HTTP {status}: {_redact(body)}"
        except Exception:
            detail = _redact(str(e))
        if current_app:
            current_app.logger.error("Gemini HTTP error: %s", detail)
        return f"Keryx could not reach the Gemini service: {detail}"
    except Exception as e:
        detail = _redact(str(e))
        if current_app:
            current_app.logger.exception("Gemini request failed: %s", detail)
        return f"Keryx could not reach the Gemini service: {detail}"
