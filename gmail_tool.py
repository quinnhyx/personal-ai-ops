import os.path
import pickle
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from datetime import datetime, timedelta
import re

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def get_gmail_service():
    creds = None
    if os.path.exists('token.pkl'):
        with open('token.pkl', 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.pkl', 'wb') as token:
            pickle.dump(creds, token)
    service = build('gmail', 'v1', credentials=creds)
    return service

# Fetch emails within past 24 hours
def list_messages(past_hours=24):
    service = get_gmail_service()
    since = datetime.utcnow() - timedelta(hours=past_hours)
    query = f"after:{int(since.timestamp())}"  # Gmail API uses epoch seconds
    results = service.users().messages().list(
        userId='me',
        q=query,
        maxResults=100  # can adjust as needed
    ).execute()
    messages = results.get('messages', [])
    return messages

# Get the title of emails
def get_message_title(message_id):
    service = get_gmail_service()
    message = service.users().messages().get(userId='me', id=message_id, format='metadata', metadataHeaders=['Subject']).execute()
    headers = message.get('payload', {}).get('headers', [])
    for h in headers:
        if h['name'] == 'Subject':
            return h['value']
    return "(No Subject)"

# Fetch header and sender
def get_message_info(message_id):
    """
    Returns a dict with 'title' (subject) and 'sender' (just the name) of the email.
    """
    service = get_gmail_service()
    message = service.users().messages().get(
        userId='me', 
        id=message_id, 
        format='metadata', 
        metadataHeaders=['Subject', 'From']
    ).execute()
    
    headers = message.get('payload', {}).get('headers', [])
    info = {"title": "(No Subject)", "sender": "(Unknown Sender)"}
    
    for h in headers:
        if h['name'] == 'Subject':
            info['title'] = h['value']
        elif h['name'] == 'From':
            # Extract just the name part before the <email>
            match = re.match(r'([^<]+)', h['value'])
            if match:
                info['sender'] = match.group(1).strip()
            else:
                info['sender'] = h['value']
    
    return info

# Get a brief intro of emails
def get_message_snippet(message_id):
    service = get_gmail_service()
    message = service.users().messages().get(userId='me', id=message_id).execute()
    return message['snippet']
