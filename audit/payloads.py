"""Request bodies with no credentials.

Historical Gemini calls omitted generationConfig. Future calls set temperature
and a max token cap explicitly. The historical shape is kept so tests can show
the difference. Building a body does not perform a request.
"""

import hashlib
import json


def _canonical(payload):
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_payload(payload):
    return sha256_text(_canonical(payload))


def gemini_contents_from_messages(messages):
    contents = []
    for message in messages:
        role = "user" if message["role"] == "user" else "model"
        contents.append({"role": role, "parts": [{"text": message["content"]}]})
    return contents


def gemini_tutor_body(system, messages, temperature=None, max_output_tokens=None):
    """Tutor request. temperature=None reproduces the historical body."""
    body = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": gemini_contents_from_messages(messages),
    }
    generation = {}
    if temperature is not None:
        generation["temperature"] = temperature
    if max_output_tokens is not None:
        generation["maxOutputTokens"] = max_output_tokens
    if generation:
        body["generationConfig"] = generation
    return body


def gemini_judge_body(system, prompt, temperature=None, max_output_tokens=None):
    """Judge request. temperature=None reproduces the historical body."""
    body = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
    }
    generation = {}
    if temperature is not None:
        generation["temperature"] = temperature
    if max_output_tokens is not None:
        generation["maxOutputTokens"] = max_output_tokens
    if generation:
        body["generationConfig"] = generation
    return body


def groq_judge_body(system, prompt, model_id, temperature, max_tokens, reasoning_effort=None):
    body = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if reasoning_effort is not None:
        body["reasoning_effort"] = reasoning_effort
    return body


def assert_no_secret(payload, secret):
    if secret and secret in _canonical(payload):
        raise RuntimeError("request payload contains a credential")
    return payload
