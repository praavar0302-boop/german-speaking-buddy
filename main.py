import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from levels import LEVEL_POLICIES, format_level_policy
from providers import stream_gemini_response, stream_openrouter_response


APP_DIR = Path(__file__).resolve().parent

load_dotenv(APP_DIR / ".env")

st.set_page_config(
    page_title="German Speaking Buddy",
    page_icon="🇩🇪",
    layout="centered",
)

st.markdown(
    """
    <style>
        .block-container {
            max-width: 850px;
            padding-top: 2rem;
            padding-bottom: 5rem;
        }
        [data-testid="stChatMessage"] {
            border: 1px solid rgba(128, 128, 128, 0.18);
            border-radius: 16px;
            padding: 0.35rem 0.75rem;
        }
        .session-note {
            color: #6b7280;
            margin-bottom: 1.5rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


def initialize_state():
    defaults = {
        "session_active": False,
        "conversation_history": [],
        "provider": None,
        "level": None,
        "mode": None,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def reset_session():
    st.session_state.session_active = False
    st.session_state.conversation_history = []
    st.session_state.provider = None
    st.session_state.level = None
    st.session_state.mode = None


def get_api_key(provider):
    if provider == "gemini":
        return os.getenv("GEMINI_API_KEY")

    return os.getenv("OPENROUTER_API_KEY")


def build_system_prompt(level, mode):
    prompt_path = APP_DIR / "prompts" / "system.md"
    base_system_prompt = prompt_path.read_text(encoding="utf-8")

    return (
        base_system_prompt
        + "\n\n"
        + format_level_policy(level)
        + "\n\nCONVERSATION MODE: "
        + mode
        + "\nFollow this mode while obeying the learner level policy above."
    )


initialize_state()

st.title("🇩🇪 German Speaking Buddy")
st.markdown(
    '<p class="session-note">Practice natural German conversation at your level.</p>',
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("Session settings")

    selected_provider = st.selectbox(
        "AI provider",
        options=["gemini", "openrouter"],
        format_func=lambda value: value.title(),
        disabled=st.session_state.session_active,
    )
    selected_level = st.selectbox(
        "German level",
        options=list(LEVEL_POLICIES),
        disabled=st.session_state.session_active,
    )
    selected_mode = st.selectbox(
        "Conversation mode",
        options=["roleplay", "free flow"],
        format_func=lambda value: value.title(),
        disabled=st.session_state.session_active,
    )

    if st.button(
        "Start Session",
        type="primary",
        use_container_width=True,
        disabled=st.session_state.session_active,
    ):
        if not get_api_key(selected_provider):
            st.error(
                f"Add {selected_provider.upper()}_API_KEY to the server-side .env file."
            )
        else:
            st.session_state.provider = selected_provider
            st.session_state.level = selected_level
            st.session_state.mode = selected_mode
            st.session_state.session_active = True
            st.rerun()

    if st.button(
        "End Session",
        use_container_width=True,
        disabled=not st.session_state.session_active,
    ):
        st.session_state.session_active = False
        st.rerun()

    if st.button("New Session / Reset", use_container_width=True):
        reset_session()
        st.rerun()

    if st.session_state.provider:
        status = "Active" if st.session_state.session_active else "Ended"
        st.divider()
        st.caption(
            f"{status} · {st.session_state.provider.title()} · "
            f"{st.session_state.level} · {st.session_state.mode.title()}"
        )


if not st.session_state.conversation_history:
    if st.session_state.session_active:
        st.info("Session started. Send a message in German to begin.")
    else:
        st.info("Choose your settings and start a session.")

for message in st.session_state.conversation_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])


user_message = st.chat_input(
    "Schreib etwas auf Deutsch …",
    disabled=not st.session_state.session_active,
)

if user_message:
    st.session_state.conversation_history.append(
        {"role": "user", "content": user_message}
    )

    with st.chat_message("user"):
        st.markdown(user_message)

    system_prompt = build_system_prompt(
        st.session_state.level,
        st.session_state.mode,
    )
    api_key = get_api_key(st.session_state.provider)

    if st.session_state.provider == "gemini":
        response_stream = stream_gemini_response(
            api_key,
            system_prompt,
            st.session_state.conversation_history,
        )
    else:
        response_stream = stream_openrouter_response(
            api_key,
            system_prompt,
            st.session_state.conversation_history,
        )

    try:
        with st.chat_message("assistant"):
            assistant_reply = st.write_stream(response_stream)
    except Exception as error:
        st.session_state.conversation_history.pop()
        st.error(f"Request failed: {error}")
    else:
        st.session_state.conversation_history.append(
            {"role": "assistant", "content": assistant_reply}
        )
