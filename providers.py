import json

import httpx


GEMINI_MODEL = "gemini-3.6-flash"

GEMINI_API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/"
    f"models/{GEMINI_MODEL}:streamGenerateContent?alt=sse"
)

OPENROUTER_API_URL = (
    "https://openrouter.ai/api/v1/chat/completions"
)

OPENROUTER_MODEL = "openrouter/free"


def convert_history_for_gemini(conversation_history):
    gemini_history = []

    for message in conversation_history:
        role = message["role"]

        if role == "assistant":
            role = "model"

        gemini_message = {
            "role": role,
            "parts": [
                {
                    "text": message["content"]
                }
            ]
        }

        gemini_history.append(gemini_message)

    return gemini_history


def stream_gemini_response(
    api_key,
    system_prompt,
    conversation_history
):
    gemini_history = convert_history_for_gemini(
        conversation_history
    )

    headers = {
        "x-goog-api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "text/event-stream"
    }

    request_payload = {
        "systemInstruction": {
            "parts": [
                {
                    "text": system_prompt
                }
            ]
        },
        "contents": gemini_history,
        "generationConfig": {
            "thinkingConfig": {
                "thinkingLevel": "low"
            }
        }
    }

    assistant_reply = ""

    print("Assistant: ", end="", flush=True)

    with httpx.stream(
        "POST",
        url=GEMINI_API_URL,
        headers=headers,
        json=request_payload,
        timeout=60
    ) as response:

        if response.status_code != 200:
            error_message = response.read().decode()

            raise RuntimeError(
                "Gemini API error: " + error_message
            )

        for line in response.iter_lines():

            if not line.startswith("data: "):
                continue

            json_text = line.replace("data: ", "", 1)

            if not json_text:
                continue

            response_data = json.loads(json_text)

            if "candidates" not in response_data:
                continue

            candidate = response_data["candidates"][0]

            if "content" not in candidate:
                continue

            parts = candidate["content"]["parts"]

            for part in parts:

                if "text" not in part:
                    continue

                text_chunk = part["text"]

                assistant_reply += text_chunk

                print(
                    text_chunk,
                    end="",
                    flush=True
                )

    print()

    return assistant_reply


def stream_openrouter_response(
    api_key,
    system_prompt,
    conversation_history
):
    headers = {
        "Authorization": "Bearer " + api_key,
        "Content-Type": "application/json",
        "Accept": "text/event-stream"
    }

    messages = [
        {
            "role": "system",
            "content": system_prompt
        }
    ]

    messages.extend(conversation_history)

    request_payload = {
        "model": OPENROUTER_MODEL,
        "messages": messages,
        "stream": True
    }

    assistant_reply = ""

    print("Assistant: ", end="", flush=True)

    with httpx.stream(
        "POST",
        url=OPENROUTER_API_URL,
        headers=headers,
        json=request_payload,
        timeout=60
    ) as response:

        if response.status_code != 200:
            error_message = response.read().decode()

            raise RuntimeError(
                "OpenRouter API error: " + error_message
            )

        for line in response.iter_lines():

            if not line.startswith("data: "):
                continue

            json_text = line.replace("data: ", "", 1)

            if json_text == "[DONE]":
                break

            if not json_text:
                continue

            response_data = json.loads(json_text)

            if "choices" not in response_data:
                continue

            delta = response_data["choices"][0]["delta"]

            if "content" not in delta:
                continue

            text_chunk = delta["content"]

            assistant_reply += text_chunk

            print(
                text_chunk,
                end="",
                flush=True
            )

    print()

    return assistant_reply