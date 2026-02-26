import os
from openai import OpenAI
from dotenv import load_dotenv
import re

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# For openai
# def classify_email(snippet):
#     prompt = f"Classify this email into Job / Newsletter / Alert / Personal:\n\n{snippet}"
#     response = client.chat.completions.create(
#         model="gpt-3.5-turbo",
#         messages=[{"role": "user", "content": prompt}],
#         max_tokens=30
#     )
#     category = response.choices[0].message.content.strip()
#     return category

CATEGORIES = [
    "job",
    "newsletter",
    "alert",
    "ad",
    "finance",
    "travel",
    "social media",
    "education",
    "event",
    "shopping",
    "personal",
    "other"
]

def normalize_category(cat: str) -> str:
    """Lowercase, remove non-alphanumeric chars for matching."""
    return re.sub(r"[^a-z0-9]", "", cat.lower())

# manually classify
def classify_email(snippet):
    """Classify email into multiple common categories using keywords."""
    text = snippet.lower()

    if any(word in text for word in ["job", "hiring", "career", "position", "interview", "opportunity"]):
        return "Job"
    elif any(word in text for word in ["newsletter", "update", "news", "digest", "subscription"]):
        return "Newsletter"
    elif any(word in text for word in ["alert", "security", "system", "warning", "codespace", "password"]):
        return "Alert"
    elif any(word in text for word in ["offer", "sale", "deal", "promotion", "discount", "free", "win", "coupon"]):
        return "Ad"
    elif any(word in text for word in ["invoice", "payment", "receipt", "bill", "transaction", "account", "bank"]):
        return "Finance"
    elif any(word in text for word in ["booking", "flight", "hotel", "reservation", "itinerary", "ticket"]):
        return "Travel"
    elif any(word in text for word in ["facebook", "linkedin", "twitter", "instagram", "notification", "friend request"]):
        return "Social Media"
    elif any(word in text for word in ["course", "class", "assignment", "exam", "lecture", "school", "university", "scholarship"]):
        return "Education"
    elif any(word in text for word in ["webinar", "event", "meet", "conference", "register", "join"]):
        return "Event"
    elif any(word in text for word in ["order", "shipped", "tracking", "delivery", "purchase", "amazon", "ebay"]):
        return "Shopping"
    elif any(word in text for word in ["hi", "hello", "dear", "friend", "family", "meet", "call"]):
        return "Personal"
    else:
        return "Other"