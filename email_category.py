import re


CATEGORIES = [
    "job",
    "newsletter",
    "alert",
    "finance",
    "travel",
    "social media",
    "education",
    "shopping",
    "personal",
    "other"
]

def normalize_category(cat: str) -> str:
    """Lowercase, remove non-alphanumeric chars for matching."""
    return re.sub(r"[^a-z0-9]", "", cat.lower())

# Main classification function using keyword matching
def classify_email(snippet):
    """Classify email into multiple common categories using keywords."""
    text = snippet.lower()

    if any(word in text for word in ["job", "hiring", "career", "position", "interview", "opportunity"]):
        return "Job"
    elif any(word in text for word in ["newsletter", "update", "news", "digest", "subscription"]):
        return "Newsletter"
    elif any(word in text for word in ["alert", "security", "system", "warning", "codespace", "password"]):
        return "Alert"
    elif any(word in text for word in ["invoice", "payment", "receipt", "bill", "transaction", "account", "bank"]):
        return "Finance"
    elif any(word in text for word in ["booking", "flight", "hotel", "reservation", "itinerary", "ticket"]):
        return "Travel"
    elif any(word in text for word in ["facebook", "linkedin", "twitter", "instagram", "notification", "friend request"]):
        return "Social Media"
    elif any(word in text for word in ["course", "class", "assignment", "exam", "lecture", "school", "university", "scholarship"]):
        return "Education"
    elif any(word in text for word in ["order", "shipped", "tracking", "delivery", "purchase", "amazon", "ebay", "offer", "sale", "deal", "promotion", "discount", "coupon"]):
        return "Shopping"
    elif any(word in text for word in ["hi", "hello", "dear", "friend", "family", "meet", "call"]):
        return "Personal"
    else:
        return "Other"
