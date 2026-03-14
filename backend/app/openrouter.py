"""OpenRouter integration — free models ONLY.

We hit OpenRouter's public model catalog and keep every model whose id ends
in ":free". Premium models are never called, no matter what. Up to three free
models then independently review the quantitative output and vote
BUY / SELL / HOLD; their theses are returned to the frontend alongside the
vote tally.

If no OPENROUTER_API_KEY is configured, the app quietly degrades to
quant-only mode so the rest of the pipeline still works.
"""

import itertools
import json
import os
import re
import threading
import time
from typing import Dict, List, Optional

import httpx

MODELS_URL = "https://openrouter.ai/api/v1/models"
CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"

# Preferred free models, tried first if present in the live catalog.
PREFERRED_FREE = [
    "deepseek/deepseek-chat-v3-0324:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "google/gemma-3-27b-it:free",
    "qwen/qwen-2.5-72b-instruct:free",
    "mistralai/mistral-small-3.1-24b-instruct:free",
    "meta-llama/llama-3.2-3b-instruct:free",
]

_catalog_lock = threading.Lock()
_free_model_ids: Optional[List[str]] = None
_catalog_fetched_at: float = 0.0
CATALOG_TTL = 6 * 3600  # refresh catalog twice a day


def get_api_key() -> Optional[str]:
    return os.environ.get("OPENROUTER_API_KEY") or None


def _fetch_free_models() -> List[str]:
    """Live catalog lookup; every returned id is guaranteed `:free`."""
    global _free_model_ids, _catalog_fetched_at
    with _catalog_lock:
        if _free_model_ids is not None and time.time() - _catalog_fetched_at < CATALOG_TTL:
            return _free_model_ids
        worker_key = get_api_key()
        headers = {"Authorization": f"Bearer {worker_key}"} if worker_key else {}
        try:
            resp = httpx.get(MODELS_URL, headers=headers, timeout=30)
            resp.raise_for_status()
            data = resp.json().get("data", [])
            free_ids = [
                m["id"] for m in data
                if isinstance(m.get("id"), str) and m["id"].endswith(":free")
            ]
        except Exception:
            free_ids = []
        ordered = ([m for m in PREFERRED_FREE if m in free_ids]
                   + [m for m in free_ids if m not in PREFERRED_FREE])
        _free_model_ids = ordered
        _catalog_fetched_at = time.time()
        return _free_model_ids


SYSTEM_PROMPT = (
    "You are a rigorous equity research analyst reviewing a quantitative "
    "prediction produced for an Indian (NSE/BSE) stock. You receive computed "
    "statistics only; you have no other market access. Judge whether the "
    "quantitative evidence supports a trade, flag regime/valuation risks, and "
    "answer ONLY with a minified JSON object — no markdown, no code fences."
)


def _build_user_prompt(payload: Dict) -> str:
    spec = {
        "verdict": "BUY | SELL | HOLD (must agree with your reasoning over the data)",
        "thesis": "2-3 sentences grounded strictly in the provided statistics",
        "risks": "1-2 concrete risks to this trade view",
        "timing_note": "one sentence on whether to enter now or wait, and why",
    }
    return (
        "Quantitative prediction payload (computed by the analysis engine):\n"
        + json.dumps(payload, ensure_ascii=False)
        + "\n\nRespond ONLY with minified JSON with exactly these keys: "
        + json.dumps(spec, ensure_ascii=False)
    )


def _extract_json(text: str) -> Optional[Dict]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?|```$", "", text, flags=re.S).strip()
    match = re.search(r"\{.*\}", text, flags=re.S)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def _call_model(model_id: str, api_key: str, user_prompt: str) -> Optional[Dict]:
    try:
        resp = httpx.post(
            CHAT_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": "http://localhost:3000",
                "X-Title": "mycratrader",
            },
            json={
                "model": model_id,
                "max_tokens": 700,
                "temperature": 0.2,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
            },
            timeout=90,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        parsed = _extract_json(content)
        if parsed and "verdict" in parsed:
            parsed["model"] = model_id
            return parsed
    except Exception:
        return None
    return None


def consensus(payload: Dict, max_models: int = 3) -> Dict:
    """Query up to `max_models` free models and tally their votes."""
    api_key = get_api_key()
    if not api_key:
        return {"available": False, "reason": "OPENROUTER_API_KEY not set"}

    free_models = _fetch_free_models()
    if not free_models:
        return {"available": False, "reason": "No :free models found in OpenRouter catalog"}

    user_prompt = _build_user_prompt(payload)
    responses: List[Dict] = []
    for model_id in itertools.islice(free_models, max_models):
        result = _call_model(model_id, api_key, user_prompt)
        if result is not None:
            responses.append(result)

    if not responses:
        return {"available": False, "reason": "All free model calls failed (rate limits?)"}

    votes = [r.get("verdict", "").upper() for r in responses]
    tally: Dict[str, int] = {}
    for v in votes:
        for label in ("BUY", "SELL", "HOLD"):
            if v.startswith(label):
                tally[label] = tally.get(label, 0) + 1
                break
    final = max(tally, key=tally.get) if tally else "HOLD"

    return {
        "available": True,
        "final_verdict": final,
        "tally": tally,
        "models_used": [r.get("model", "?") for r in responses],
        "analyses": [
            {
                "model": r.get("model", "?"),
                "verdict": next((l for l in ("BUY", "SELL", "HOLD")
                                 if r.get("verdict", "").upper().startswith(l)), "HOLD"),
                "thesis": r.get("thesis", ""),
                "risks": r.get("risks", ""),
                "timing_note": r.get("timing_note", ""),
            }
            for r in responses
        ],
    }
