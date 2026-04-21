from dotenv import load_dotenv
from fastapi import FastAPI, Body
from pydantic import BaseModel
import os
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from gmail_tool import list_messages, get_message_snippet, get_message_info
from email_category import classify_email, normalize_category
import threading
from concurrent.futures import ThreadPoolExecutor
import time
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = FastAPI()


# ===== 全局缓存 =====
EMAIL_CACHE = []
IS_LOADING = False
TOTAL_EMAILS = 0
PROCESSED_EMAILS = 0
progress_lock = threading.Lock()  # Thread-safe progress updates

class EmailRequest(BaseModel):
    description: str

def auto_refresh():
    while True:
        load_emails()
        time.sleep(300)  # 5 minutes

# ===== 加载邮件函数 =====
def load_emails():
    global EMAIL_CACHE, IS_LOADING, TOTAL_EMAILS, PROCESSED_EMAILS
    with progress_lock:
        IS_LOADING = True
        EMAIL_CACHE = []
        PROCESSED_EMAILS = 0

    messages = list_messages()
    with progress_lock:
        TOTAL_EMAILS = len(messages)

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = executor.map(process_single_email_with_progress, messages)
        EMAIL_CACHE = list(results)

    with progress_lock:
        IS_LOADING = False
        TOTAL_EMAILS = 0
        PROCESSED_EMAILS = 0

def process_single_email_with_progress(m):
    global PROCESSED_EMAILS

    snippet = get_message_snippet(m['id'])
    info = get_message_info(m['id'])
    category = classify_email(snippet)

    with progress_lock:
        PROCESSED_EMAILS += 1

    return {
        "From": info.get('sender', '(Unknown)'),
        "Title": info.get('title', '(No Subject)'),
        "Description": snippet,
        "Category": category,
    }

@app.on_event("startup")
def startup_event():
    threading.Thread(target=load_emails).start()
    threading.Thread(target=auto_refresh, daemon=True).start()

@app.get("/progress")
def get_progress():
    with progress_lock:
        if not IS_LOADING:
            return {"loading": False, "progress": 100}
        progress = min(100, int((PROCESSED_EMAILS / TOTAL_EMAILS) * 100) if TOTAL_EMAILS else 0)
        return {"loading": True, "progress": progress}

@app.post("/needs-reply")
def needs_reply_api(data: EmailRequest):
    email_text = data.description

    prompt = f"""
    Determine if this email requires a reply.

    Only answer YES or NO.

    Email:
    {email_text}
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            timeout=10 
        )

        answer = response.choices[0].message.content.strip().upper()

        if "YES" in answer:
            return {"result": "Needs Reply"}
        else:
            return {"result": "No Reply Needed"}

    except Exception as e:
        return {"result": f"Error: {str(e)}"}
    
@app.post("/generate-reply")
def generate_reply(data: EmailRequest):
    email_text = data.description

    prompt = f"""
    Write a polite and professional reply to the following email:

    {email_text}

    Keep it concise.
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        reply = response.choices[0].message.content.strip()
        return {"reply": reply}
    except Exception as e:
        return {"reply": f"(Error generating reply: {str(e)})"}

@app.get("/emails")
def read_emails():
    if IS_LOADING:
        return {"loading": True}
    return EMAIL_CACHE

@app.get("/emails/{category}")
def read_emails_by_category(category: str):
    normalized_query = normalize_category(category)

    return [
        e for e in EMAIL_CACHE
        if normalize_category(e["Category"]) == normalized_query
    ]

@app.get("/refresh")
def refresh_emails():
    threading.Thread(target=load_emails).start()
    return {"message": "Refreshing emails"}

app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")

@app.get("/")
async def root():
    return FileResponse("frontend/index.html")