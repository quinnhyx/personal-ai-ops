import json
import os
import urllib.error
import urllib.request


OLLAMA_GENERATE_URL = "http://127.0.0.1:11434/api/generate"
DEEPSEEK_CHAT_URL = "https://api.deepseek.com/chat/completions"


def llm_call(prompt: str) -> str:
    """Unified free/local LLM interface.

    Default: Ollama on localhost, which does not require a paid token.
    Optional: DeepSeek-compatible chat endpoint when explicitly configured.
    """
    backend = os.getenv("LLM_BACKEND", "ollama").strip().lower()

    if backend == "deepseek":
        return _deepseek_call(prompt)
    if backend == "auto":
        try:
            return _ollama_call(prompt)
        except RuntimeError:
            if os.getenv("DEEPSEEK_API_KEY", "").strip():
                return _deepseek_call(prompt)
            raise
    return _ollama_call(prompt)


def _ollama_call(prompt: str) -> str:
    payload = {
        "model": os.getenv("OLLAMA_MODEL", "qwen3:8b"),
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.2,
        },
    }
    data = _post_json(os.getenv("OLLAMA_BASE_URL", OLLAMA_GENERATE_URL), payload)
    text = data.get("response", "")
    if not text:
        raise RuntimeError("Ollama response did not include text")
    return str(text).strip()


def _deepseek_call(prompt: str) -> str:
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is not set")

    payload = {
        "model": os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        "messages": [
            {
                "role": "system",
                "content": "You write polite, concise, professional English email replies.",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }
    data = _post_json(
        os.getenv("DEEPSEEK_BASE_URL", DEEPSEEK_CHAT_URL),
        payload,
        headers={"Authorization": f"Bearer {api_key}"},
    )
    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("DeepSeek response did not include text") from exc


def _post_json(url: str, payload: dict, headers: dict | None = None) -> dict:
    request_headers = {"Content-Type": "application/json"}
    if headers:
        request_headers.update(headers)

    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=request_headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"LLM API error {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"LLM API network error: {exc.reason}") from exc
