import base64
from datetime import datetime, timezone
from email.message import EmailMessage

import httplib2
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow, InstalledAppFlow
from google_auth_httplib2 import AuthorizedHttp
from googleapiclient.discovery import build

from backend.config.settings import CREDENTIALS_PATH, GMAIL_API_TIMEOUT_SECONDS, GMAIL_SCOPES, LEGACY_TOKEN_PATH
from backend.providers.base import EmailProvider
from backend.storage import repositories as repo


class GmailProvider(EmailProvider):
    provider_name = "gmail"

    def __init__(self, account: dict | None = None):
        self.account = account
        self._service = None

    @classmethod
    def build_auth_url(cls, redirect_uri: str, state: str | None = None) -> tuple[str, str]:
        flow = Flow.from_client_secrets_file(str(CREDENTIALS_PATH), scopes=GMAIL_SCOPES, redirect_uri=redirect_uri)
        auth_url, state = flow.authorization_url(access_type="offline", include_granted_scopes="true", prompt="consent", state=state)
        return auth_url, state

    @classmethod
    def connect_with_code(cls, code: str, redirect_uri: str) -> dict:
        flow = Flow.from_client_secrets_file(str(CREDENTIALS_PATH), scopes=GMAIL_SCOPES, redirect_uri=redirect_uri)
        flow.fetch_token(code=code)
        return cls._save_credentials(flow.credentials)

    @classmethod
    def connect_with_local_oauth(cls) -> dict:
        flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), GMAIL_SCOPES)
        return cls._save_credentials(flow.run_local_server(port=0))

    @classmethod
    def _save_credentials(cls, creds) -> dict:
        service = _build_gmail_service(creds)
        email = service.users().getProfile(userId="me").execute().get("emailAddress", "me")
        account = repo.upsert_account(email=email, provider=cls.provider_name, display_name=email)
        repo.save_oauth_token(account["id"], cls.provider_name, creds.refresh_token, creds.token, creds.expiry.isoformat() if creds.expiry else None, list(creds.scopes or GMAIL_SCOPES))
        return account

    def list_messages(self, since: datetime, max_results: int) -> list[dict]:
        since_utc = since.astimezone(timezone.utc)
        query = f"after:{int(since_utc.timestamp())}"
        print(f"[GmailProvider] messages.list q={query} max_results={max_results}", flush=True)
        messages = []
        page_token = None
        while len(messages) < max_results:
            result = self._gmail_service().users().messages().list(userId="me", q=query, maxResults=min(100, max_results - len(messages)), pageToken=page_token).execute()
            messages.extend(result.get("messages", []))
            page_token = result.get("nextPageToken")
            if not page_token:
                break
        return messages

    def get_message_detail(self, message_id: str) -> dict:
        message = self._gmail_service().users().messages().get(userId="me", id=message_id, format="full").execute()
        headers = {item.get("name", ""): item.get("value", "") for item in message.get("payload", {}).get("headers", [])}
        bodies = _extract_bodies(message.get("payload", {}))
        return {
            "provider_message_id": message.get("id", message_id),
            "provider_thread_id": message.get("threadId", ""),
            "sender": headers.get("From", "(Unknown Sender)"),
            "recipients": headers.get("To", ""),
            "subject": headers.get("Subject", "(No Subject)"),
            "snippet": message.get("snippet", ""),
            "body_text": bodies["body_text"],
            "body_html": bodies["body_html"],
            "headers": headers,
            "received_at": _format_internal_date(message.get("internalDate")),
        }

    def create_draft(self, message_id: str, reply_body: str) -> dict:
        original = self.get_message_detail(message_id)
        draft = EmailMessage()
        draft["To"] = original.get("sender", "")
        subject = original.get("subject", "(No Subject)")
        draft["Subject"] = subject if subject.lower().startswith("re:") else f"Re: {subject}"
        draft.set_content(reply_body)
        raw = base64.urlsafe_b64encode(draft.as_bytes()).decode("ascii")
        result = self._gmail_service().users().drafts().create(userId="me", body={"message": {"raw": raw, "threadId": original.get("provider_thread_id")}}).execute()
        draft_id = result.get("id", "")
        return {"draft_id": draft_id, "draft_url": self.get_open_url(draft_id=draft_id)}

    def get_open_url(self, message_id: str | None = None, thread_id: str | None = None, draft_id: str | None = None) -> str:
        if draft_id:
            return "https://mail.google.com/mail/u/0/#drafts"
        if thread_id:
            return f"https://mail.google.com/mail/u/0/#inbox/{thread_id}"
        if message_id:
            return f"https://mail.google.com/mail/u/0/#search/rfc822msgid:{message_id}"
        return "https://mail.google.com/mail/u/0/#inbox"

    def refresh_access_token(self) -> None:
        creds = self._credentials()
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        self._service = _build_gmail_service(creds)

    def _gmail_service(self):
        if not self._service:
            self.refresh_access_token()
        return self._service

    def _credentials(self):
        if self.account:
            token = repo.get_oauth_token(self.account["id"], self.provider_name)
            if token:
                return Credentials(token=token.get("access_token") or None, refresh_token=token.get("refresh_token") or None, token_uri="https://oauth2.googleapis.com/token", client_id=_client_config().get("client_id"), client_secret=_client_config().get("client_secret"), scopes=(token.get("scopes") or " ".join(GMAIL_SCOPES)).split())
        if LEGACY_TOKEN_PATH.exists():
            import pickle
            with LEGACY_TOKEN_PATH.open("rb") as token_file:
                return pickle.load(token_file)
        raise RuntimeError("No connected Gmail account. Use Connect Gmail first.")


def _client_config() -> dict:
    import json
    try:
        data = json.loads(CREDENTIALS_PATH.read_text())
    except Exception:
        return {}
    return data.get("installed") or data.get("web") or {}


def _build_gmail_service(creds):
    http = AuthorizedHttp(creds, http=httplib2.Http(timeout=GMAIL_API_TIMEOUT_SECONDS))
    return build("gmail", "v1", http=http, cache_discovery=False)


def _format_internal_date(value: str | None) -> str:
    if not value:
        return ""
    return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc).isoformat()


def _extract_bodies(payload: dict) -> dict:
    text_chunks = []
    html_chunks = []

    def walk(part: dict) -> None:
        mime_type = part.get("mimeType", "")
        data = part.get("body", {}).get("data")
        if data:
            decoded = _decode_body(data)
            if decoded:
                if mime_type == "text/html":
                    html_chunks.append(decoded)
                elif mime_type == "text/plain":
                    text_chunks.append(decoded)
        for child in part.get("parts", []):
            walk(child)

    walk(payload)
    return {
        "body_text": "\n".join(chunk.strip() for chunk in text_chunks if chunk.strip()).strip(),
        "body_html": "\n".join(chunk.strip() for chunk in html_chunks if chunk.strip()).strip(),
    }


def _decode_body(data: str) -> str:
    try:
        padded = data + "=" * (-len(data) % 4)
        return base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8", errors="replace")
    except Exception:
        return ""
