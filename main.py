import threading
import time

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import pipeline


load_dotenv()

app = FastAPI()


class EmailRequest(BaseModel):
    description: str


def auto_refresh():
    while True:
        time.sleep(300)
        pipeline.refresh_emails()


@app.on_event("startup")
def startup_event():
    threading.Thread(target=pipeline.refresh_emails, daemon=True).start()
    threading.Thread(target=auto_refresh, daemon=True).start()


@app.get("/health")
def health():
    return {
        "status": "ok",
        "llm_backend": pipeline.get_llm_backend(),
        "refresh": pipeline.get_progress(),
    }


@app.get("/progress")
def get_progress():
    return pipeline.get_progress()


@app.get("/emails")
def read_emails():
    return pipeline.get_emails()


@app.get("/emails/raw")
def read_raw_emails():
    return pipeline.get_raw_emails()


@app.get("/emails/{category}")
def read_emails_by_category(category: str):
    return pipeline.get_emails(category)


@app.post("/emails/{email_id}/generate-reply")
def generate_reply_by_id(email_id: str):
    return pipeline.generate_ai_reply(email_id)


@app.post("/api/emails/{email_id}/draft")
def create_draft(email_id: str):
    return pipeline.create_gmail_draft(email_id)


@app.post("/api/emails/{email_id}/status/{status}")
def update_email_status(email_id: str, status: str):
    return pipeline.update_reply_status(email_id, status)


@app.post("/needs-reply")
def needs_reply_api(data: EmailRequest):
    result = pipeline.evaluate_reply_from_text(data.description)
    return {
        "result": "Needs Reply" if result["needs_reply"] else "No Reply Needed",
        **result,
        "source": "rules",
    }


@app.post("/generate-reply")
def generate_reply(data: EmailRequest):
    return pipeline.generate_reply_from_text(data.description)


@app.post("/refresh")
def refresh_emails_post():
    threading.Thread(target=pipeline.refresh_emails, daemon=True).start()
    return {"message": "Refreshing emails"}


@app.get("/refresh")
def refresh_emails_get():
    return refresh_emails_post()


app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def root():
    return FileResponse("templates/index.html")
