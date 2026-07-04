import threading
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from email_category import classify_email, normalize_category
from gmail_tool import get_message_detail, list_messages
from llm_client import llm_call
from reply_rules import generate_reply as fallback_reply
from reply_rules import evaluate_reply_need
from reply_rules import is_reply_required


EMAIL_CACHE_RAW = []
EMAIL_CACHE_PROCESSED = []
AI_CACHE = {}
DRAFT_CACHE = {}
LAST_REFRESH_ERROR = ""

IS_LOADING = False
TOTAL_EMAILS = 0
PROCESSED_EMAILS = 0
CACHE_LOCK = threading.Lock()


def refresh_emails() -> None:
    global EMAIL_CACHE_RAW, EMAIL_CACHE_PROCESSED, IS_LOADING, TOTAL_EMAILS, PROCESSED_EMAILS, LAST_REFRESH_ERROR

    with CACHE_LOCK:
        IS_LOADING = True
        EMAIL_CACHE_RAW = []
        EMAIL_CACHE_PROCESSED = []
        TOTAL_EMAILS = 0
        PROCESSED_EMAILS = 0
        LAST_REFRESH_ERROR = ""

    try:
        messages = list_messages()
        with CACHE_LOCK:
            TOTAL_EMAILS = len(messages)

        with ThreadPoolExecutor(max_workers=8) as executor:
            raw_emails = list(executor.map(_fetch_raw_email, messages))

        processed = [_process_email(email) for email in raw_emails]

        with CACHE_LOCK:
            EMAIL_CACHE_RAW = raw_emails
            EMAIL_CACHE_PROCESSED = processed
    except Exception as exc:
        with CACHE_LOCK:
            LAST_REFRESH_ERROR = str(exc)
            EMAIL_CACHE_RAW = []
            EMAIL_CACHE_PROCESSED = []
    finally:
        with CACHE_LOCK:
            IS_LOADING = False


def _fetch_raw_email(message: dict) -> dict:
    global PROCESSED_EMAILS

    detail = get_message_detail(message["id"])
    raw_email = {
        "id": message["id"],
        "sender": detail.get("sender", "(Unknown Sender)"),
        "to": detail.get("to", "Me"),
        "title": detail.get("title", "(No Subject)"),
        "snippet": detail.get("snippet", ""),
        "timestamp": detail.get("timestamp", ""),
    }

    with CACHE_LOCK:
        PROCESSED_EMAILS += 1

    return raw_email


def _process_email(raw_email: dict) -> dict:
    category = classify_email(
        " ".join([raw_email.get("title", ""), raw_email.get("sender", ""), raw_email.get("snippet", "")])
    )
    email = {
        **raw_email,
        "category": category,
    }
    reply_eval = evaluate_reply_need(email)
    email.update(reply_eval)
    email["reply_required"] = reply_eval["needs_reply"]
    email["draft_text"] = ""
    email["draft_url"] = ""

    # Backward-compatible fields for the existing dashboard.
    email["From"] = email["sender"]
    email["Title"] = email["title"]
    email["Description"] = email["snippet"]
    email["Category"] = email["category"]
    email["ReplyRequired"] = email["reply_required"]
    return email


def get_progress() -> dict:
    with CACHE_LOCK:
        if not IS_LOADING:
            return {"loading": False, "progress": 100, "error": LAST_REFRESH_ERROR}
        progress = min(100, int((PROCESSED_EMAILS / TOTAL_EMAILS) * 100) if TOTAL_EMAILS else 0)
        return {"loading": True, "progress": progress, "error": LAST_REFRESH_ERROR}


def get_emails(category: str | None = None) -> list[dict] | dict:
    with CACHE_LOCK:
        if IS_LOADING:
            return {"loading": True}
        emails = list(EMAIL_CACHE_PROCESSED)

    if category:
        normalized = normalize_category(category)
        emails = [email for email in emails if normalize_category(email["category"]) == normalized]
    return emails


def get_raw_emails() -> list[dict]:
    with CACHE_LOCK:
        return list(EMAIL_CACHE_RAW)


def get_email(email_id: str) -> dict | None:
    with CACHE_LOCK:
        for email in EMAIL_CACHE_PROCESSED:
            if email["id"] == email_id:
                return dict(email)
    return None


def generate_ai_reply(email_id: str) -> dict:
    email = get_email(email_id)
    if not email:
        return {"reply": "Email not found.", "draft_text": "", "draft_url": "", "source": "error"}

    if email["reply_status"] == "no_reply_needed":
        return {
            "reply": "No reply required for this email.",
            "draft_text": "",
            "draft_url": "",
            "source": "rules",
        }

    if email_id in AI_CACHE:
        return {
            "reply": AI_CACHE[email_id],
            "draft_text": AI_CACHE[email_id],
            "draft_url": DRAFT_CACHE.get(email_id, {}).get("draft_url", ""),
            "source": "cache",
        }

    prompt = _build_reply_prompt(email)
    try:
        reply = llm_call(prompt)
        source = "llm"
    except Exception:
        reply = fallback_reply(email["snippet"])
        source = "rules-fallback"

    AI_CACHE[email_id] = reply
    return {"reply": reply, "draft_text": reply, "draft_url": "", "source": source}


def create_gmail_draft(email_id: str) -> dict:
    """Create a draft-shaped response.

    This is intentionally a placeholder until Gmail compose scopes and a draft
    URL strategy are wired. It never sends email.
    """
    email = get_email(email_id)
    if not email:
        return {"draft_text": "", "draft_url": "", "status": "error", "message": "Email not found."}

    generated = generate_ai_reply(email_id)
    draft_text = generated.get("draft_text") or generated.get("reply", "")
    if not draft_text or generated.get("source") == "rules":
        return {
            "draft_text": draft_text,
            "draft_url": "",
            "status": "skipped",
            "message": "This email is marked as no reply needed.",
        }

    draft_url = _gmail_search_url(email)
    DRAFT_CACHE[email_id] = {
        "draft_text": draft_text,
        "draft_url": draft_url,
    }
    _update_email(email_id, {
        "reply_status": "draft_created",
        "reply_required": True,
        "needs_reply": True,
        "draft_text": draft_text,
        "draft_url": draft_url,
    })
    return {
        "draft_text": draft_text,
        "draft_url": draft_url,
        "status": "draft_created",
        "message": "Draft text generated. Gmail draft API placeholder returned a Gmail search URL.",
        "source": generated.get("source", "unknown"),
    }


def generate_reply_from_text(text: str) -> dict:
    email = {
        "id": "ad-hoc",
        "sender": "",
        "title": "",
        "snippet": text,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "category": classify_email(text),
    }
    email["reply_required"] = is_reply_required(email)
    if not email["reply_required"]:
        return {"reply": "No reply required for this email.", "source": "rules"}

    try:
        return {"reply": llm_call(_build_reply_prompt(email)), "source": "llm"}
    except Exception:
        return {"reply": fallback_reply(text), "source": "rules-fallback"}


def reply_required_from_text(text: str) -> bool:
    email = {
        "sender": "",
        "title": "",
        "snippet": text,
        "category": classify_email(text),
    }
    return is_reply_required(email)


def evaluate_reply_from_text(text: str) -> dict:
    email = {
        "sender": "",
        "title": "",
        "snippet": text,
        "category": classify_email(text),
    }
    return evaluate_reply_need(email)


def update_reply_status(email_id: str, status: str) -> dict:
    if status not in {"needs_reply", "pending_review", "no_reply_needed", "draft_created"}:
        return {"ok": False, "message": "Invalid reply status."}

    confidence_by_status = {
        "needs_reply": 80,
        "pending_review": 55,
        "no_reply_needed": 20,
        "draft_created": 100,
    }
    updated = _update_email(email_id, {
        "reply_status": status,
        "needs_reply": status in {"needs_reply", "draft_created"},
        "reply_required": status in {"needs_reply", "draft_created"},
        "reply_confidence": confidence_by_status[status],
        "reply_reason": "Manually updated by user.",
    })
    return {"ok": updated, "message": "Updated." if updated else "Email not found."}


def get_llm_backend() -> str:
    return os.getenv("LLM_BACKEND", "ollama")


def _build_reply_prompt(email: dict) -> str:
    return f"""Write a polite, concise, professional English email reply body only.

Rules:
- Return only the email body.
- Do not explain your reasoning.
- Do not invent facts, dates, attachments, availability, phone numbers, or commitments.
- Do not say the email was sent.
- Do not send anything. This text will be reviewed by the user before becoming a Gmail draft.

Sender: {email.get("sender", "")}
Subject: {email.get("title", "")}
Email:
{email.get("snippet", "")}

Return only the reply body."""


def _update_email(email_id: str, updates: dict) -> bool:
    with CACHE_LOCK:
        for email in EMAIL_CACHE_PROCESSED:
            if email["id"] == email_id:
                email.update(updates)
                email["ReplyRequired"] = email.get("reply_required", False)
                return True
    return False


def _gmail_search_url(email: dict) -> str:
    query = email.get("title") or email.get("sender") or ""
    return "https://mail.google.com/mail/u/0/#search/" + query.replace(" ", "+")
