from fastapi import FastAPI, HTTPException
from gmail_tool import list_messages, get_message_snippet, get_message_info
from email_classify import classify_email, normalize_category

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "AI Ops Agent Running"}


@app.get("/emails")
# For OPENAI
# def read_emails():
#     messages = list_messages()
#     emails_with_category = []
#     for m in messages:
#         snippet = get_message_snippet(m['id'])
#         category = classify_email(snippet)
#         emails_with_category.append({
#             "id": m['id'],
#             "snippet": snippet,
#             "category": category
#         })
#     return emails_with_category
# manually classify emails

# def read_emails():
#     messages = list_messages()
#     emails_with_category = []
#     for m in messages:
#         title = get_message_title(m['id'])
#         snippet = get_message_snippet(m['id'])
#         category = classify_email(snippet)
#         emails_with_category.append({
#             "title": title,
#             "snippet": snippet,
#             "category": category
#         })
#     return emails_with_category

# @app.get("/emails/{category}")
# def read_emails_by_category(category: str):
#     messages = list_messages()
#     normalized_query = normalize_category(category)
#     filtered = []
#     for m in messages:
#         title = get_message_title(m['id'])
#         snippet = get_message_snippet(m['id'])
#         cat = classify_email(snippet)
#         if normalize_category(cat) == normalized_query:
#             filtered.append({
#                 "title": title,
#                 "snippet": snippet,
#                 "category": cat
#             })
#     if not filtered:
#         raise HTTPException(status_code=404, detail=f"No emails found for category '{category}'")
#     return filtered

def read_emails():
    messages = list_messages()
    emails_with_category = []
    for m in messages:
        snippet = get_message_snippet(m['id'])
        info = get_message_info(m['id'])
        category = classify_email(snippet)
        emails_with_category.append({
            "From": info['sender'],
            "Title": info['title'],
            "Description": snippet,
            "Category": category
        })
    return emails_with_category

@app.get("/emails/{category}")
def read_emails_by_category(category: str):
    messages = list_messages()
    normalized_query = normalize_category(category)
    filtered = []
    for m in messages:
        snippet = get_message_snippet(m['id'])
        info = get_message_info(m['id'])
        cat = classify_email(snippet)
        if normalize_category(cat) == normalized_query:
            filtered.append({
                "From": info['sender'],
                "Title": info['title'],
                "Description": snippet,
                "Category": cat
            })
    return filtered