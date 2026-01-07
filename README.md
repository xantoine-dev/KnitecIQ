# OpenAI Chatbot Interface with Streamlit

## Overview

This Streamlit app collects property/contact info and then guides the user through a KniTec IQ chat questionnaire backed by OpenAI. Chat history stays in the browser session (not shared across users).

## Getting Started

### Dependencies

- `streamlit`
- `openai`
- `streamlit-authenticator`
- `python-dotenv`

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
- Add `OPENAI_API_KEY=...` to `.streamlit/secrets.toml` (preferred) or to `.env` in the repo root. `.env` is git-ignored.
- A sample template is available at `.streamlit/secrets.example.toml` (uses hashed passwords; no `pre_authorized` config is needed).

### Run

Only supported entrypoint:
```
streamlit run app.py
```
Do not run these directly (multipage navigation will break):
- `Contact_Information.py`
- `app_chat.py`
- files under `pages/`
Use the sidebar to open the `Chat_with_KnitecIQ` page after completing the intake form.

### Repository Structure (key files)
```
app.py                         # primary entry: contact intake then chat
Contact_Information.py         # legacy entrypoint (do not run directly)
app_chat.py                    # chat experience (used by pages wrappers)
contact_info/                  # modular contact intake page + assets
pages/Chat_with_KnitecIQ.py    # page wrapper to run chat as a page
assets/                        # shared assets (e.g., avatar, prompts)
data/                          # (legacy) chat cache location, git-ignored
.streamlit/                    # config.toml and local secrets.toml (git-ignored)
.env                           # OPENAI_API_KEY (git-ignored)
```

## How it Works

1. User signs in via `streamlit-authenticator` (secrets-driven).
2. Contact intake form validates required fields (name, address, city, state, zip, contact) and formats (2-letter state, ZIP/ZIP+4, email/phone).
3. On successful submit, user clicks Continue to Chat to switch to the chat page.
4. Chat uses OpenAI with the KniTec prompt; history stays in the current browser session and is not shared across users.
5. Past chat list is pruned automatically if history files are missing.

## Validation (manual)

- Contact form: verified required-field enforcement, state format (2 letters), ZIP/ZIP+4, email/phone validation, and clear/submit behaviors.
- Navigation: continue button switches to chat within the same Streamlit session.
- Chat: message send/receive works with stored histories; past chats prunes missing sessions.
