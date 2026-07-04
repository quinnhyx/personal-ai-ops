import re


NEEDS_REPLY_PATTERNS = [
    r"\?",
    r"\bplease (reply|respond|confirm|review|send|provide|let me know)\b",
    r"\b(can|could|would|will) you\b",
    r"\blet me know\b",
    r"\bconfirm\b",
    r"\bfeedback\b",
    r"\bavailable\b",
    r"\bschedule\b",
    r"\binterview\b",
    r"\bmeeting\b",
    r"\bcall\b",
    r"\brsvp\b",
    r"\baction required\b",
    r"\bneed you to\b",
    r"\bplease send\b",
    r"\bplease provide\b",
    r"\bplease confirm\b",
    r"\bwhat do you think\b",
    r"\bwhen are you available\b",
]

NO_REPLY_PATTERNS = [
    r"\bno[- ]?reply\b",
    r"\bdo not reply\b",
    r"\bunsubscribe\b",
    r"\bnewsletter\b",
    r"\bdigest\b",
    r"\breceipt\b",
    r"\binvoice\b",
    r"\bshipped\b",
    r"\bdelivered\b",
    r"\btracking\b",
    r"\bverification code\b",
    r"\bsecurity alert\b",
    r"\bnotification\b",
    r"\bpromotion\b",
    r"\bsale\b",
    r"\boffer\b",
    r"\bjob alert\b",
    r"\bnew jobs\b",
    r"\blinkedin job\b",
    r"\bpeople are viewing\b",
    r"\bweekly summary\b",
    r"\bmarketing\b",
    r"\badvertisement\b",
    r"\brecommended for you\b",
    r"\bsocial notification\b",
    r"\bpayment receipt\b",
    r"\border confirmation\b",
    r"\bsystem notification\b",
    r"\bautomated message\b",
    r"\bthis is an automated\b",
]

CONVERSATIONAL_SENDER_PATTERNS = [
    r"\bprofessor\b",
    r"\brecruiter\b",
    r"\bhiring manager\b",
    r"\bhr\b",
    r"\badvisor\b",
    r"\bteacher\b",
]

ACTION_PATTERNS = [
    r"\?",
    r"\bplease (reply|respond|confirm|review|send|provide|let me know)\b",
    r"\b(can|could|would|will) you\b",
    r"\blet me know\b",
    r"\bplease confirm\b",
    r"\bplease provide\b",
    r"\bplease send\b",
    r"\baction required\b",
    r"\brsvp\b",
]

IMPORTANT_CONTEXT_PATTERNS = [
    r"\b(job interview|interview|recruiter|hr|hiring manager)\b",
    r"\b(professor|teacher|advisor|university|class|assignment)\b",
    r"\b(deadline|urgent|important|application|offer letter)\b",
]


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip().lower()


def needs_reply(text: str) -> bool:
    normalized = _normalize(text)
    if not normalized:
        return False

    if any(re.search(pattern, normalized) for pattern in NO_REPLY_PATTERNS):
        return False

    return any(re.search(pattern, normalized) for pattern in NEEDS_REPLY_PATTERNS)


def reply_status(text: str) -> str:
    return "Needs Reply" if needs_reply(text) else "No Reply Needed"


def evaluate_reply_need(email: dict) -> dict:
    text = _normalize(
        " ".join(
            [
                str(email.get("sender", "")),
                str(email.get("title", "")),
                str(email.get("snippet", "")),
                str(email.get("category", "")),
            ]
        )
    )
    category = str(email.get("category", "")).lower()
    sender = _normalize(str(email.get("sender", "")))

    if any(re.search(pattern, text) for pattern in NO_REPLY_PATTERNS):
        return {
            "needs_reply": False,
            "reply_status": "no_reply_needed",
            "reply_confidence": 10,
            "reply_reason": "Looks like a notification, subscription, promotion, receipt, or automated email.",
        }

    score = 0
    reasons = []

    action_hits = [pattern for pattern in ACTION_PATTERNS if re.search(pattern, text)]
    if action_hits:
        score += 45
        reasons.append("Contains a direct question or explicit action request.")

    important_hits = [pattern for pattern in IMPORTANT_CONTEXT_PATTERNS if re.search(pattern, text)]
    if important_hits:
        score += 25
        reasons.append("Context looks important: interview, recruiter, professor, school, or deadline.")

    if category in {"personal", "education", "job"}:
        score += 15
        reasons.append(f"Category is {email.get('category')}.")

    if any(re.search(pattern, sender) for pattern in CONVERSATIONAL_SENDER_PATTERNS):
        score += 15
        reasons.append("Sender looks like a real person or institution contact.")

    if category in {"newsletter", "shopping", "social media", "finance", "alert"}:
        score -= 25
        reasons.append(f"Category {email.get('category')} is usually informational.")

    confidence = max(0, min(100, score))
    if confidence >= 70:
        status = "needs_reply"
        needs = True
    elif confidence >= 40:
        status = "pending_review"
        needs = False
    else:
        status = "no_reply_needed"
        needs = False

    return {
        "needs_reply": needs,
        "reply_status": status,
        "reply_confidence": confidence,
        "reply_reason": " ".join(reasons) or "No strong signal that this requires a reply.",
    }


def is_reply_required(email: dict) -> bool:
    return evaluate_reply_need(email)["needs_reply"]


def generate_reply(text: str) -> str:
    normalized = _normalize(text)

    if not needs_reply(normalized):
        return (
            "This email looks like it may not need a reply. If you still want to respond, you can use:\n\n"
            "Hi,\n\nThanks for the update. I have received it.\n\nBest,\nYixuan"
        )

    if any(word in normalized for word in ["interview", "meeting", "schedule", "available", "call"]):
        return (
            "Hi,\n\n"
            "Thank you for reaching out. I would be happy to coordinate a time. "
            "Please let me know what times work best for you, and I will confirm my availability.\n\n"
            "Best,\nYixuan"
        )

    return (
        "Hi,\n\n"
        "Thanks for reaching out. I have received your message and will review the details. "
        "I will get back to you shortly.\n\n"
        "Best,\nYixuan"
    )
