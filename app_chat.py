import time
import os
import streamlit as st
import google.generativeai as genai
import datetime
from pathlib import Path
from dotenv import load_dotenv
import google.api_core.exceptions as g_exceptions
import streamlit_authenticator as stauth

# --- Authentication gate ----------------------------------------------------
auth_config = st.secrets.get('auth')
if not auth_config:
    st.error('Auth configuration missing in secrets.')
    st.stop()

def _to_plain(obj):
    """Convert secrets mappings to plain dicts/lists to avoid mutation issues."""
    if isinstance(obj, dict):
        return {k: _to_plain(v) for k, v in obj.items()}
    try:
        # Handles secrets-like objects that implement .items()
        return {k: _to_plain(v) for k, v in obj.items()}
    except Exception:
        return obj

auth_config = _to_plain(auth_config)

authenticator = stauth.Authenticate(
    auth_config['credentials'],
    auth_config['cookie']['name'],
    auth_config['cookie']['key'],
    auth_config['cookie']['expiry_days'],
    auth_config.get('preauthorized', {}),
)

name, auth_status, username = authenticator.login(
    fields={'Form name': 'Login'},
    location='main',
)

if auth_status is False:
    st.error('Invalid username or password.')
    st.stop()
elif auth_status is None:
    st.warning('Please enter your credentials.')
    st.stop()
else:
    authenticator.logout('Logout', 'sidebar')
# ---------------------------------------------------------------------------

load_dotenv()
GOOGLE_API_KEY = st.secrets.get('GOOGLE_API_KEY') or os.environ.get('GOOGLE_API_KEY')
if not GOOGLE_API_KEY:
    st.error('GOOGLE_API_KEY is not set; please configure your environment (Streamlit secrets or env var).')
    st.stop()
genai.configure(api_key=GOOGLE_API_KEY)

MODEL_ROLE = 'ai'
AI_AVATAR_ICON = str(Path('assets/Knitec_IQ_avatar.png'))

# Session-scoped chat store keyed by chat_id; isolates chats per browser session.
if 'chat_store' not in st.session_state:
    st.session_state.chat_store = {}
if 'chat_id' not in st.session_state:
    st.session_state.chat_id = f'{time.time()}'
if 'chat_title' not in st.session_state:
    st.session_state.chat_title = 'New Chat'
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'gemini_history' not in st.session_state:
    st.session_state.gemini_history = []


def inject_chat_styles() -> None:
    """Inject a calmer visual system for chat and sidebar."""
    st.markdown(
        """
        <style>
          :root {
            --primary: #1d4ed8;
            --text: #0f172a;
            --muted: #475467;
            --surface: #f7f9fc;
            --card: #ffffff;
            --border: #e5e7eb;
          }
          html, body, .stApp {
            background: var(--surface);
            color: var(--text);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Inter", sans-serif;
          }
          .block-container {
            max-width: 1080px;
            padding: 24px 32px 140px;
          }
          h1 {
            color: var(--text);
            font-weight: 700;
          }
          h2, h3, h4, h5, h6 {
            color: var(--text);
            font-weight: 600;
          }
          /* Sidebar */
          [data-testid="stSidebar"] {
            background: #f2f4f7;
            border-right: 1px solid var(--border);
          }
          [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
            color: var(--text);
          }
          [data-testid="stSidebar"] .stSelectbox > div[data-baseweb="select"] {
            border-radius: 12px;
            border: 1px solid var(--border);
            background: #fff;
          }
          [data-testid="stSidebar"] .stTextInput > div > div > input {
            border-radius: 12px;
            border: 1px solid var(--border);
          }
          /* Chat cards */
          [data-testid="stChatMessage"] {
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 16px;
            box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06);
            margin-bottom: 14px;
          }
          [data-testid="stChatMessage"] p {
            color: var(--text);
            line-height: 1.6;
          }
          /* Chat input */
          textarea, div[data-baseweb="textarea"] textarea {
            background: #eef1f6 !important;
            border: 1px solid var(--border) !important;
            border-radius: 20px !important;
            color: var(--text) !important;
            padding: 12px 16px !important;
          }
          div[data-baseweb="textarea"] {
            border-radius: 20px !important;
            border: 1px solid var(--border) !important;
            background: #eef1f6 !important;
          }
          /* Buttons */
          .stButton button, button[kind="secondary"], button[kind="primary"] {
            border-radius: 12px;
            font-weight: 600;
          }
          button[kind="primary"] {
            background: var(--primary);
            border-color: var(--primary);
            color: #fff;
          }
          button[kind="secondary"] {
            background: #eef2ff;
            border: 1px solid var(--border);
            color: var(--text);
          }
          button:hover {
            transform: translateY(-1px);
            box-shadow: 0 10px 22px rgba(29, 78, 216, 0.16);
          }
          .chat-footer-note {
            margin-top: 12px;
            padding-bottom: 12px;
            text-align: center;
            color: var(--muted);
            font-size: 13px;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )


def default_chat_title(chat_id: str) -> str:
    """Fallback title using timestamp if chat_id is a timestamp; otherwise use generic."""
    try:
        ts = float(chat_id)
        dt = datetime.datetime.fromtimestamp(ts)
        return dt.strftime('Chat %Y-%m-%d %H:%M')
    except Exception:
        return 'New Chat'


def friendly_title_from_prompt(prompt: str, chat_id: str) -> str:
    """Create a human-friendly title from the first user prompt."""
    words = (prompt or '').strip().split()
    if not words:
        return default_chat_title(chat_id)
    snippet = ' '.join(words[:8])
    if len(words) > 8:
        snippet += '...'
    return snippet


inject_chat_styles()

# Load chat data from the session store into working state.
def _load_chat(chat_id: str) -> None:
    chat = st.session_state.chat_store.get(chat_id)
    if chat:
        st.session_state.chat_id = chat_id
        st.session_state.chat_title = chat.get('title') or default_chat_title(chat_id)
        st.session_state.messages = list(chat.get('messages', []))
        st.session_state.gemini_history = list(chat.get('gemini_history', []))
    else:
        st.session_state.chat_id = chat_id
        st.session_state.chat_title = default_chat_title(chat_id)
        st.session_state.messages = []
        st.session_state.gemini_history = []


_load_chat(st.session_state.chat_id)

# Sidebar allows a list of past chats (per-session only)
with st.sidebar:
    st.write('# Past Chats')
    past_chats = {cid: data.get('title', default_chat_title(cid)) for cid, data in st.session_state.chat_store.items()}
    select_options = [st.session_state.chat_id] + [cid for cid in past_chats if cid != st.session_state.chat_id]
    selected_chat = st.selectbox(
        label='Pick a past chat',
        options=select_options,
        format_func=lambda x: past_chats.get(x, default_chat_title(x)),
    )
    if selected_chat != st.session_state.chat_id:
        _load_chat(selected_chat)

    if st.button('Start new chat'):
        fresh_chat_id = f'{time.time()}'
        _load_chat(fresh_chat_id)

    new_title = st.text_input(
        'Chat title',
        value=st.session_state.chat_title,
        key='chat_title_input',
    )
    if new_title != st.session_state.chat_title:
        st.session_state.chat_title = new_title
    st.session_state.chat_store[st.session_state.chat_id] = dict(
        title=st.session_state.chat_title,
        messages=st.session_state.messages,
        gemini_history=st.session_state.gemini_history,
    )

st.write('# Chat with Knitec IQ')

# Load Knitec IQ instructions as system prompt
prompt_path = Path('assets/prompts/Knitec_IQ_Instructions_Trimmed.txt')
try:
    SYSTEM_PROMPT = prompt_path.read_text()
except FileNotFoundError:
    st.warning('Prompt file missing; using a minimal fallback prompt.')
    SYSTEM_PROMPT = 'You are Knitec IQ assistant.'
except Exception as exc:
    st.warning(f'Could not read prompt file, using fallback. ({exc})')
    SYSTEM_PROMPT = 'You are Knitec IQ assistant.'

# Use requested Gemini model
st.session_state.model = genai.GenerativeModel(
    'gemini-2.5-flash',
    system_instruction=SYSTEM_PROMPT,
)
st.session_state.chat = st.session_state.model.start_chat(
    history=st.session_state.gemini_history,
)

# Display chat messages from history on app rerun
for message in st.session_state.messages:
    with st.chat_message(
        name=message['role'],
        avatar=message.get('avatar'),
    ):
        st.markdown(message['content'])

# React to user input
if prompt := st.chat_input('Your message here...'):
    # Save this as a chat for later in this session
    if st.session_state.chat_id not in st.session_state.chat_store:
        if not st.session_state.chat_title or st.session_state.chat_title == 'New Chat':
            st.session_state.chat_title = friendly_title_from_prompt(prompt, st.session_state.chat_id)
    # Display user message in chat message container
    with st.chat_message('user'):
        st.markdown(prompt)
    # Add user message to chat history
    st.session_state.messages.append(
        dict(
            role='user',
            content=prompt,
        )
    )
    ## Send message to AI
    try:
        response = st.session_state.chat.send_message(
            prompt,
            stream=True,
        )
    except g_exceptions.ResourceExhausted as exc:
        retry_secs = getattr(getattr(exc, 'retry_delay', None), 'seconds', None)
        wait_hint = f' Please retry after ~{retry_secs}s.' if retry_secs else ''
        st.error(f'Gemini rate limit hit.{wait_hint}')
        response = None
    except g_exceptions.GoogleAPIError as exc:
        st.error(f'Gemini API error: {exc}')
        response = None

    if response is None:
        st.session_state.messages.append(
            dict(
                role=MODEL_ROLE,
                content='(No response due to API error.)',
                avatar=AI_AVATAR_ICON,
            )
        )
    else:
        # Display assistant response in chat message container
        with st.chat_message(
            name=MODEL_ROLE,
            avatar=AI_AVATAR_ICON,
        ):
            message_placeholder = st.empty()
            full_response = ''
            assistant_response = response
            # Streams in a chunk at a time
            for chunk in response:
                # Simulate stream of chunk
                text = getattr(chunk, 'text', '') or ''
                if not text:
                    continue
                for ch in text.split(' '):
                    full_response += ch + ' '
                    time.sleep(0.05)
                    # Rewrites with a cursor at end
                    message_placeholder.write(full_response + '▌')
            # Write full message with placeholder
            message_placeholder.write(full_response)

        # Add assistant response to chat history
        st.session_state.messages.append(
            dict(
                role=MODEL_ROLE,
                content=st.session_state.chat.history[-1].parts[0].text,
                avatar=AI_AVATAR_ICON,
            )
        )
        st.session_state.gemini_history = st.session_state.chat.history

    st.session_state.chat_store[st.session_state.chat_id] = dict(
        title=st.session_state.chat_title,
        messages=st.session_state.messages,
        gemini_history=st.session_state.gemini_history,
    )

st.markdown(
    '<div class="chat-footer-note">KnitecIQ can make mistakes—please double-check important information.</div>',
    unsafe_allow_html=True,
)
