# Gemini Chatbot Interface with Streamlit

## Overview

This Streamlit app collects property/contact info and then guides the user through a KniTec IQ chat questionnaire backed by Gemini. It stores chat history for later recall.

## Getting Started

### Dependencies

- `streamlit`
- `google-generativeai`
- `streamlit-authenticator`
- `joblib`, `python-dotenv`

### Setup

1) Create and activate a virtual environment:
```
python3 -m venv .venv
source .venv/bin/activate
```

2) Install dependencies:
```
pip install -r requirements.txt
```

3) Secrets and keys:
- Create `.streamlit/secrets.toml` with `auth` credentials (see example in contact_info/app.py expectations).
- Add `GOOGLE_API_KEY=...` to `.env` in the repo root. `.env` is git-ignored.

### Run

Primary entry (includes contact intake then chat):
```
streamlit run Contact_Information.py
```
Alternate multipage entry:
```
streamlit run app.py
```
Direct chat (skips intake):
```
streamlit run app_chat.py
```
Chat page inside the same session:
```
streamlit run pages/02_chat.py
```

### Repository Structure (key files)
```
Contact_Information.py        # primary entry: contact intake then chat
app.py                        # alternate multipage entry
app_chat.py                   # chat experience (used by pages wrappers)
contact_info/                 # modular contact intake page + assets
pages/02_Chat_with_KnitecIQ.py# page wrapper to run chat as a page
pages/02_chat.py              # (alternate) page wrapper to run chat as a page
assets/                       # shared assets (e.g., avatar, prompts)
data/                         # chat history (git-ignored)
.streamlit/                   # config.toml and local secrets.toml (git-ignored)
.env                          # GOOGLE_API_KEY (git-ignored)
```

## How it Works

1. User signs in via `streamlit-authenticator` (secrets-driven).
2. Contact intake form validates required fields (name, address, city, state, zip, contact) and formats (2-letter state, ZIP/ZIP+4, email/phone).
3. On successful submit, user is redirected to the chat page.
4. Chat uses Gemini with the KniTec prompt, saving history per session in `data/`.
5. Past chat list is pruned automatically if history files are missing.

## Validation (manual)
- Contact form: verified required-field enforcement, state format (2 letters), ZIP/ZIP+4, email/phone validation, and clear/submit behaviors.
- Navigation: submit triggers redirect to chat within the same Streamlit session.
- Chat: message send/receive works with stored histories; past chats prunes missing sessions.
