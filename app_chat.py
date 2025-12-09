import time
import os
import joblib
import streamlit as st
import google.generativeai as genai
from pathlib import Path
from dotenv import load_dotenv
import google.api_core.exceptions as g_exceptions

load_dotenv()
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')
if not GOOGLE_API_KEY:
    st.error('GOOGLE_API_KEY is not set; please configure your environment.')
    st.stop()
genai.configure(api_key=GOOGLE_API_KEY)

new_chat_id = f'{time.time()}'
MODEL_ROLE = 'ai'
AI_AVATAR_ICON = str(Path('assets/Knitec_IQ_avatar.png'))

def safe_dump(obj, dest_path: str) -> None:
    """Write with a temp file and atomic replace to avoid partial writes."""
    target = Path(dest_path)
    tmp = target.with_suffix(target.suffix + '.tmp')
    joblib.dump(obj, tmp)
    tmp.replace(target)

Path('data').mkdir(exist_ok=True)

# Load past chats (if available)
try:
    past_chats: dict = joblib.load('data/past_chats_list')
except FileNotFoundError:
    past_chats = {}
except Exception as exc:
    st.warning(f'Past chat list was unreadable, starting fresh. ({exc})')
    past_chats = {}

# Sidebar allows a list of past chats
with st.sidebar:
    st.write('# Past Chats')
    if st.session_state.get('chat_id') is None:
        st.session_state.chat_id = st.selectbox(
            label='Pick a past chat',
            options=[new_chat_id] + list(past_chats.keys()),
            format_func=lambda x: past_chats.get(x, 'New Chat'),
            placeholder='_',
        )
    else:
        # This will happen the first time AI response comes in
        st.session_state.chat_id = st.selectbox(
            label='Pick a past chat',
            options=[new_chat_id, st.session_state.chat_id] + list(past_chats.keys()),
            index=1,
            format_func=lambda x: past_chats.get(x, 'New Chat' if x != st.session_state.chat_id else st.session_state.chat_title),
            placeholder='_',
        )
    # Save new chats after a message has been sent to AI
    # TODO: Give user a chance to name chat
    st.session_state.chat_title = f'ChatSession-{st.session_state.chat_id}'

st.write('# Chat with Gemini')

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

# Chat history (allows to ask multiple questions)
try:
    st.session_state.messages = joblib.load(
        f'data/{st.session_state.chat_id}-st_messages'
    )
    st.session_state.gemini_history = joblib.load(
        f'data/{st.session_state.chat_id}-gemini_messages'
    )
    print('old cache')
except FileNotFoundError:
    st.session_state.messages = []
    st.session_state.gemini_history = []
    print('new_cache made')
except Exception as exc:
    st.warning(f'Cached chat history unreadable, starting clean. ({exc})')
    st.session_state.messages = []
    st.session_state.gemini_history = []
    print('new_cache made')
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
    # Save this as a chat for later
    if st.session_state.chat_id not in past_chats.keys():
        past_chats[st.session_state.chat_id] = st.session_state.chat_title
        safe_dump(past_chats, 'data/past_chats_list')
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
    # Save to file
    safe_dump(
        st.session_state.messages,
        f'data/{st.session_state.chat_id}-st_messages',
    )
    safe_dump(
        st.session_state.gemini_history,
        f'data/{st.session_state.chat_id}-gemini_messages',
    )
