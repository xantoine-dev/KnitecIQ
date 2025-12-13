import time
import os
import datetime
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI, OpenAIError
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
OPENAI_API_KEY = st.secrets.get('OPENAI_API_KEY') or os.environ.get('OPENAI_API_KEY')
if not OPENAI_API_KEY:
    st.error('OPENAI_API_KEY is not set; please configure your environment (Streamlit secrets or env var).')
    st.stop()
OPENAI_MODEL = os.environ.get('OPENAI_MODEL') or 'gpt-4.1-nano'


@st.cache_resource(show_spinner=False)
def get_openai_client(api_key: str) -> OpenAI:
    """Cache the OpenAI client so HTTP connections can be reused across reruns."""
    return OpenAI(api_key=api_key)


client = get_openai_client(OPENAI_API_KEY)

MODEL_ROLE = 'assistant'
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
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []


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
        st.session_state.messages = list(chat.get('messages', []))  # copy to avoid aliasing
        st.session_state.chat_history = list(chat.get('chat_history', []))  # copy to avoid aliasing
    else:
        st.session_state.chat_id = chat_id
        st.session_state.chat_title = default_chat_title(chat_id)
        st.session_state.messages = []
        st.session_state.chat_history = []


_load_chat(st.session_state.chat_id)

def seed_intro_message() -> None:
    """Ensure a visible intro message and matching history on fresh chats."""
    if st.session_state.messages:
        return
    intro_msg = (
        "I'm Knitec IQ, a chatbot that will guide you through the KniTec Installation "
        "Questionnaire one question at a time and then summarize your answers."
    )
    st.session_state.messages.append(
        dict(
            role=MODEL_ROLE,
            content=intro_msg,
            avatar=AI_AVATAR_ICON,
        )
    )
    st.session_state.chat_history.append({"role": MODEL_ROLE, "content": intro_msg})
    st.session_state.chat_store[st.session_state.chat_id] = dict(
        title=st.session_state.chat_title,
        messages=list(st.session_state.messages),
        chat_history=list(st.session_state.chat_history),
    )


seed_intro_message()

# Sidebar: past chats disabled for now (per-session only) to avoid navigation bugs.
# TODO: Re-enable a reliable past-chats selector once state sync issues are resolved.
with st.sidebar:
    st.write('# Chat')
    if st.button('Start new chat'):
        fresh_chat_id = f'{time.time()}'
        st.session_state.chat_store[st.session_state.chat_id] = dict(
            title=st.session_state.chat_title,
            messages=list(st.session_state.messages),
            chat_history=list(st.session_state.chat_history),
        )
        _load_chat(fresh_chat_id)

    st.text_input(
        'Chat title',
        value=st.session_state.chat_title,
        key='chat_title_input',
        disabled=True,
        help='Past chats navigation is temporarily disabled.',
    )
    st.session_state.chat_store[st.session_state.chat_id] = dict(
        title=st.session_state.chat_title,
        messages=list(st.session_state.messages),
        chat_history=list(st.session_state.chat_history),
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
    st.session_state.chat_history.append({'role': 'user', 'content': prompt})
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
    # Persist user turn immediately to avoid losing the first message on rerun.
    st.session_state.chat_store[st.session_state.chat_id] = dict(
        title=st.session_state.chat_title,
        messages=list(st.session_state.messages),
        chat_history=list(st.session_state.chat_history),
    )
    # Display assistant response immediately with a "thinking" placeholder,
    # then stream tokens into the same message bubble.
    full_response = ''
    with st.chat_message(
        name=MODEL_ROLE,
        avatar=AI_AVATAR_ICON,
    ):
        message_placeholder = st.empty()
        message_placeholder.markdown('_Knitec IQ is thinking..._')

        try:
            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[{'role': 'system', 'content': SYSTEM_PROMPT}] + st.session_state.chat_history,
                stream=True,
            )

            for chunk in response:
                delta = chunk.choices[0].delta
                content_piece = getattr(delta, 'content', None) or ''
                if not content_piece:
                    continue
                if isinstance(content_piece, str):
                    text_piece = content_piece
                else:
                    text_piece = ''.join(getattr(part, 'text', '') or str(part) for part in content_piece)
                full_response += text_piece
                message_placeholder.markdown(full_response + '▌')

            if not full_response:
                full_response = '(No response.)'
            message_placeholder.markdown(full_response)
        except OpenAIError as exc:
            full_response = '(No response due to API error.)'
            message_placeholder.markdown(full_response)
            st.error(f'OpenAI API error: {exc}')

    st.session_state.messages.append(
        dict(
            role=MODEL_ROLE,
            content=full_response,
            avatar=AI_AVATAR_ICON,
        )
    )
    if full_response and full_response != '(No response due to API error.)':
        st.session_state.chat_history.append({'role': 'assistant', 'content': full_response})

    st.session_state.chat_store[st.session_state.chat_id] = dict(
        title=st.session_state.chat_title,
        messages=list(st.session_state.messages),
        chat_history=list(st.session_state.chat_history),
    )

st.markdown(
    '<div class="chat-footer-note">KnitecIQ can make mistakes—please double-check important information.</div>',
    unsafe_allow_html=True,
)
