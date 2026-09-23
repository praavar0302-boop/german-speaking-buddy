import json
import logging
import os
import sys
import time
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from decision_layer import DISPLAY, DISPLAY_AND_RECORD, decide_response
from levels import LEVEL_POLICIES, format_level_policy
from provider_retry import ProviderFailure, stream_with_provider_recovery
from providers import stream_gemini_response, stream_openrouter_response
from response_runtime import (
    TYPING_MESSAGE,
    capture_generated_chunks,
    commit_accepted_exchange,
    first_validated_chunks,
    timed_model_chunks,
    validated_response_stream,
)
from scenario_progress import (
    progress_instruction,
    split_progress_header,
    update_progress,
)
from scenarios import (
    SCENARIOS,
    SCENARIO_OPTIONS,
    choose_random_scenario,
    format_scenario_prompt,
    is_closing_reply,
    opening_line,
    scenario_is_complete,
)


APP_DIR = Path(__file__).resolve().parent
timing_logger = logging.getLogger("german_speaking_buddy.timing")
if not timing_logger.handlers:
    timing_logger.addHandler(logging.StreamHandler(sys.stderr))
timing_logger.setLevel(logging.INFO)
timing_logger.propagate = False

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
        "feedback_items": {
            "uncertain_vocabulary": [],
            "language_warnings": [],
        },
        "session_terms": set(),
        "scenario_name": None,
        "scenario_progress": [],
        "scenario_complete": False,
        "scenario_closing": False,
        "random_scenario_name": None,
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
    st.session_state.feedback_items = {
        "uncertain_vocabulary": [],
        "language_warnings": [],
    }
    st.session_state.session_terms = set()
    st.session_state.scenario_name = None
    st.session_state.scenario_progress = []
    st.session_state.scenario_complete = False
    st.session_state.scenario_closing = False
    st.session_state.random_scenario_name = None


def get_api_key(provider):
    if provider == "gemini":
        return os.getenv("GEMINI_API_KEY")

    return os.getenv("OPENROUTER_API_KEY")


def build_system_prompt(level, mode, scenario=None, scenario_progress=None):
    prompt_path = APP_DIR / "prompts" / "system.md"
    base_system_prompt = prompt_path.read_text(encoding="utf-8")

    prompt = (
        base_system_prompt
        + "\n\n"
        + format_level_policy(level)
        + "\n\nCONVERSATION MODE: "
        + mode
        + "\nFollow this mode while obeying the learner level policy above."
        + "\n\nLIVE CONVERSATION RESPONSE RULES:"
        + "\n- Stay at or below the selected level."
        + "\n- Reply with 1-3 short sentences."
        + "\n- Use common everyday vocabulary."
        + "\n- Prefer simple sentence structures."
        + "\n- Ask at most one follow-up question."
        + "\n- Prefer a simpler word or sentence whenever possible."
    )
    if mode == "roleplay" and scenario:
        prompt += "\n\n" + format_scenario_prompt(
            scenario,
            scenario_progress or [False] * len(scenario["objectives"]),
        )
    return prompt


def provider_stream(api_key, provider, system_prompt, history):
    if provider == "gemini":
        return stream_gemini_response(api_key, system_prompt, history)
    return stream_openrouter_response(api_key, system_prompt, history)


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
    # Free Conversation is temporarily hidden while roleplay is refined.
    selected_mode = "roleplay"
    selected_scenario_name = None
    preview_scenario = None
    if selected_mode == "roleplay":
        selected_scenario_option = st.selectbox(
            "Roleplay scenario",
            options=SCENARIO_OPTIONS,
            disabled=st.session_state.session_active,
        )
        if st.session_state.session_active and st.session_state.scenario_name:
            selected_scenario_name = st.session_state.scenario_name
        elif selected_scenario_option == "Random":
            if not st.session_state.random_scenario_name:
                st.session_state.random_scenario_name = choose_random_scenario()
            selected_scenario_name = st.session_state.random_scenario_name
        else:
            selected_scenario_name = selected_scenario_option
        preview_scenario = SCENARIOS[selected_scenario_name]

        st.subheader(preview_scenario["title"])
        st.caption(f"Learner: {preview_scenario['learner_role']}")
        st.caption(f"AI: {preview_scenario['ai_role']}")
        st.markdown("**Objectives**")
        for objective in preview_scenario["objectives"]:
            st.markdown(f"- {objective['text']}")
        st.caption(
            "Complete when: " + preview_scenario["completion_condition"]
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
            if selected_mode == "roleplay":
                st.session_state.scenario_name = selected_scenario_name
                st.session_state.scenario_progress = [
                    False
                ] * len(preview_scenario["objectives"])
                st.session_state.scenario_complete = False
                st.session_state.scenario_closing = False
                st.session_state.conversation_history = [
                    {
                        "role": "assistant",
                        "content": opening_line(preview_scenario, selected_level),
                    }
                ]
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
        status = (
            "Scenario complete" if st.session_state.scenario_complete
            else "Active" if st.session_state.session_active else "Ended"
        )
        st.divider()
        st.caption(
            f"{status} · {st.session_state.provider.title()} · "
            f"{st.session_state.level} · {st.session_state.mode.title()}"
        )

    if st.session_state.mode == "roleplay" and st.session_state.scenario_name:
        scenario = SCENARIOS[st.session_state.scenario_name]
        st.divider()
        st.markdown("**Scenario progress**")
        for index, objective in enumerate(scenario["objectives"]):
            marker = "✅" if st.session_state.scenario_progress[index] else "⬜"
            st.markdown(f"{marker} {objective['text']}")
        completed = sum(st.session_state.scenario_progress)
        st.caption(f"{completed}/{len(scenario['objectives'])} objectives recorded")
        if st.session_state.scenario_complete:
            st.success("Scenario complete")


if not st.session_state.conversation_history:
    if st.session_state.session_active:
        st.info("Session started. Send a message in German to begin.")
    else:
        st.info("Choose your settings and start a session.")

for message in st.session_state.conversation_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if st.session_state.scenario_complete:
    st.success("Scenario complete. Start a new session to practice again.")


user_message = st.chat_input(
    "Schreib etwas auf Deutsch …",
    disabled=not st.session_state.session_active or st.session_state.scenario_complete,
)

if user_message and not st.session_state.scenario_complete:
    diagnostics = {
        "started_at": time.perf_counter(),
        "model_seconds": 0.0,
        "validation_seconds": 0.0,
        "rewrites": 0,
        "first_validated_seconds": None,
        "learner_message": user_message,
        "generated_assistant_candidate": "",
        "generated_candidates": [],
        "decisions": [],
        "rewritten_candidates": [],
        "fallback_used": False,
        "scenario_progress_evidence": {},
        "scenario_completed_objectives": [],
    }
    with st.chat_message("user"):
        st.markdown(user_message)

    system_prompt = build_system_prompt(
        st.session_state.level,
        st.session_state.mode,
        SCENARIOS.get(st.session_state.scenario_name),
        st.session_state.scenario_progress,
    )
    scenario = SCENARIOS[st.session_state.scenario_name]
    response_prompt = system_prompt + progress_instruction(scenario)
    request_history = [
        *st.session_state.conversation_history,
        {"role": "user", "content": user_message},
    ]
    def rewrite_sentence(sentence, instruction, attempt):
        rewrite_prompt = (
            system_prompt
            + "\n\nREVISION TASK:\n"
            + instruction
            + "\nDo not add explanations or commentary."
        )
        rewrite_history = [{"role": "user", "content": sentence}]
        return timed_model_chunks(
            stream_with_provider_recovery(
                st.session_state.provider,
                rewrite_prompt,
                rewrite_history,
                provider_stream,
                get_api_key,
                timing_logger,
            ),
            diagnostics,
        )

    try:
        response_stream = timed_model_chunks(
            stream_with_provider_recovery(
                st.session_state.provider,
                response_prompt,
                request_history,
                provider_stream,
                get_api_key,
                timing_logger,
            ),
            diagnostics,
        )
        with st.spinner(TYPING_MESSAGE):
            progress_evidence, reply_chunks = split_progress_header(response_stream)
            diagnostics["scenario_progress_evidence"] = progress_evidence
            reply_chunks = capture_generated_chunks(reply_chunks, diagnostics)
            updated_progress = update_progress(
                scenario,
                st.session_state.scenario_progress,
                progress_evidence,
                user_message,
            )
            diagnostics["scenario_completed_objectives"] = [
                objective["id"]
                for objective, done in zip(scenario["objectives"], updated_progress)
                if done
            ]
            st.session_state.scenario_closing = scenario_is_complete(
                scenario, updated_progress
            )
            if st.session_state.scenario_closing:
                # The final turn is buffered so an unsafe or non-closing reply
                # cannot appear before the reviewed closing is chosen.
                closing_feedback = {
                    "uncertain_vocabulary": [],
                    "language_warnings": [],
                }
                try:
                    assistant_reply = "".join(
                        validated_response_stream(
                            reply_chunks,
                            st.session_state.level,
                            rewrite_sentence,
                            closing_feedback,
                            session_terms=st.session_state.session_terms,
                            diagnostics=diagnostics,
                        )
                    ).strip()
                except ProviderFailure:
                    raise
                except Exception:
                    assistant_reply = ""
                if is_closing_reply(assistant_reply):
                    for key, items in closing_feedback.items():
                        st.session_state.feedback_items[key].extend(items)
                else:
                    assistant_reply = scenario["fallback_closing"]
                    diagnostics["fallback_used"] = True
                    validation_started = time.perf_counter()
                    try:
                        fallback_decision = decide_response(
                            assistant_reply,
                            st.session_state.level,
                            session_terms=st.session_state.session_terms,
                        )
                    finally:
                        diagnostics["validation_seconds"] += (
                            time.perf_counter() - validation_started
                        )
                    diagnostics["decisions"].append(
                        {
                            "candidate": assistant_reply,
                            "action": fallback_decision["action"],
                            "reason_codes": fallback_decision["reason_codes"],
                            "unverified_vocabulary": fallback_decision["vocabulary"]["unverified_content_words"],
                            "language_warnings": fallback_decision["language"]["warnings"],
                            "language_violations": fallback_decision["language"]["violations"],
                        }
                    )
                    if fallback_decision["action"] not in {
                        DISPLAY,
                        DISPLAY_AND_RECORD,
                    }:
                        raise RuntimeError("The reviewed scenario closing failed validation")
                safe_stream = iter((assistant_reply,))
            else:
                safe_stream = validated_response_stream(
                    reply_chunks,
                    st.session_state.level,
                    rewrite_sentence,
                    st.session_state.feedback_items,
                    session_terms=st.session_state.session_terms,
                    diagnostics=diagnostics,
                )
            with st.chat_message("assistant"):
                assistant_reply = st.write_stream(
                    first_validated_chunks(safe_stream, diagnostics)
                )
    except Exception as error:
        st.session_state.scenario_closing = False
        timing_logger.warning("roleplay_request_failed error_type=%s", type(error).__name__)
        st.error("Das hat leider nicht geklappt. Bitte versuche es noch einmal.")
    else:
        accepted = commit_accepted_exchange(
            st.session_state.conversation_history,
            user_message,
            assistant_reply,
        )
        if accepted:
            if updated_progress != st.session_state.scenario_progress:
                st.session_state.scenario_progress = updated_progress
                st.session_state.scenario_complete = st.session_state.scenario_closing
                st.session_state.scenario_closing = False
                st.rerun()
    finally:
        first_ready = diagnostics["first_validated_seconds"]
        timing_logger.info(
            "roleplay_timing total=%.3fs model=%.3fs validation=%.3fs "
            "rewrites=%d first_validated=%s",
            time.perf_counter() - diagnostics["started_at"],
            diagnostics["model_seconds"],
            diagnostics["validation_seconds"],
            diagnostics["rewrites"],
            f"{first_ready:.3f}s" if first_ready is not None else "none",
        )
        timing_logger.info(
            "roleplay_audit %s",
            json.dumps(
                {
                    "learner_message": diagnostics["learner_message"],
                    "generated_assistant_candidate": diagnostics[
                        "generated_assistant_candidate"
                    ],
                    "decisions": diagnostics["decisions"],
                    "rewrite_happened": diagnostics["rewrites"] > 0,
                    "rewritten_candidates": diagnostics["rewritten_candidates"],
                    "fallback_used": diagnostics["fallback_used"],
                    "scenario_progress_evidence": diagnostics[
                        "scenario_progress_evidence"
                    ],
                    "scenario_completed_objectives": diagnostics[
                        "scenario_completed_objectives"
                    ],
                },
                ensure_ascii=False,
                default=str,
            ),
        )
