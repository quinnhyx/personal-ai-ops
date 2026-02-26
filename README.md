# Personal AI Ops Agent
A lightweight personal AI-powered email assistant that fetches your Gmail messages, classifies them into categories, and serves them via an API. Designed for quick insights, filtering, and dashboard integration.

## Features
- Fetch emails from Gmail received in the past 24 hours

- Classify emails into multiple categories:

- Job, Newsletter, Alert, Ad, Finance, Travel

- Social Media, Education, Event, Shopping

- Personal, Other

- Return email subject, sender name, snippet, and category

- Filter emails by category via `/emails/{category}` endpoint

- Manual keyword-based classification (no paid API required)

- Ready for integration with dashboards or automation workflows

## Tech Stack
- **Backend**: Python, FastAPI

- **Email API**: Gmail API (`google-api-python-client`)

- **Optional AI**: OpenAI GPT-3.5 for more advanced classification

- **Environment**: `python-dotenv` for API keys, virtual environment `.venv`

## Setup & Installation
1. Clone the repository
```bash
git clone https://github.com/YOUR_USERNAME/personal-ai-ops.git
cd personal-ai-ops
```
2. Create a virtual environment and activate it
```bash
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
# Windows CMD
.\.venv\Scripts\activate.bat
# macOS / Linux
source .venv/bin/activate
```
3. Install dependencies
```bash
pip install -r requirements.txt
```
4. Set up Gmail API

- Go to Google Cloud Console

- Create a new project and enable Gmail API

- Download `credentials.json` and place it in the project root

- Add your Gmail address as a test user if the app is unverified

- Do not upload `credentials.json` onto Github

5. Run the FastAPI server
```bash
uvicorn main:app --reload
```
Server runs on: `http://127.0.0.1:8000`

Endpoints:

`/emails` → all emails with categories

`/emails/{category}` → filtered emails by category

## Example Response
```JSON
[
  {
    "title": "Monster Job of the Week",
    "sender": "Taylor Monster",
    "snippet": "Find out who is hiring for your role...",
    "category": "Job"
  },
  {
    "title": "$1000 Kikoff Scholarship",
    "sender": "Kikoff Credit",
    "snippet": "A new special eligibility scholarship has arrived...",
    "category": "Newsletter"
  }
]
```

## Optional: Use OpenAI for classification

Paste OpenAI API key and set `OPENAI_API_KEY` in `.env`
```bash
# Don't upload Gmail API key onto github
cp .env.example .env
```
Modify `classify_email` in `email_classify.py` to use GPT-3.5

## Project Structure
```
personal-ai-ops/
│
├─ main.py             # FastAPI app with endpoints
├─ gmail_tool.py       # Gmail API integration
├─ email_classify.py   # Email classification logic
├─ requirements.txt    # Python dependencies
├─ credentials.json    # Gmail OAuth credentials (not committed)
├─ token.pkl           # Saved OAuth token (generated)
└─ .env                # Environment variables (API keys)
```