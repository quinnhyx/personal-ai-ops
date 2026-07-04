# Personal AI Ops Agent

A local-first AI Email Assistant that fetches Gmail messages, classifies them with rules, decides whether each email needs a reply, and drafts replies only when needed.

## Core Rules

- No OpenAI API.
- No paid-token model is required.
- Default LLM backend is local Ollama at `http://127.0.0.1:11434`.
- DeepSeek is supported only when explicitly configured.
- If the LLM is unavailable, reply drafting falls back to local rules.

## Pipeline

1. Fetch Gmail messages from the past 24 hours into `EMAIL_CACHE_RAW`.
2. Classify emails with keyword rules into:
   `Job`, `Newsletter`, `Alert`, `Finance`, `Travel`, `Social Media`, `Education`, `Shopping`, `Personal`, `Other`.
3. Decide `reply_required` with rules only.
4. Generate an English reply with the configured free/local LLM only when `reply_required = true`.

## LLM Backends

Default local setup:

```bash
ollama pull qwen3:8b
ollama serve
```

Environment:

```bash
cp .env.example .env
```

Default `.env`:

```env
LLM_BACKEND=ollama
OLLAMA_BASE_URL=http://127.0.0.1:11434/api/generate
OLLAMA_MODEL=qwen3:8b
```

Optional DeepSeek-compatible endpoint:

```env
LLM_BACKEND=deepseek
DEEPSEEK_API_KEY=your_key
DEEPSEEK_BASE_URL=https://api.deepseek.com/chat/completions
DEEPSEEK_MODEL=deepseek-chat
```

## Run

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

Open:

```text
http://127.0.0.1:8000
```

## API

- `GET /health`
- `GET /progress`
- `GET /emails`
- `GET /emails/raw`
- `GET /emails/{category}`
- `POST /emails/{email_id}/generate-reply`
- `POST /api/emails/{email_id}/draft`
- `POST /api/emails/{email_id}/status/{status}`
- `POST /refresh`

The draft endpoint currently returns draft text plus a Gmail URL placeholder. It does not send email.

Legacy-compatible endpoints:

- `POST /needs-reply`
- `POST /generate-reply`

## Project Structure

```text
personal-ai-ops/
├─ main.py              # FastAPI app
├─ pipeline.py          # Email pipeline, raw cache, processed cache, AI cache
├─ gmail_tool.py        # Gmail API integration
├─ email_category.py    # Rule-based classification
├─ reply_rules.py       # Rule-based reply-required detection and fallback templates
├─ llm_client.py        # Unified Ollama / DeepSeek LLM interface
├─ frontend/index.html  # Dashboard
├─ requirements.txt
├─ credentials.json
├─ token.pkl
└─ .env
```
