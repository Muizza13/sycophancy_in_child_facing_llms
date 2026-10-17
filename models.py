"""Tutor adapters.

Historical Gemini calls sent no generationConfig. Future calls set temperature
and maxOutputTokens explicitly and return a ChatResult. API keys stay in the
request header and are not placed in the body or the result.
"""

import hashlib
import json
import os
import time
import urllib.error
import urllib.request

from audit.payloads import gemini_tutor_body

try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = None

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


TRUNCATED_FINISH_REASONS = frozenset({
    "max_tokens",
    "length",
    "max_tokens_reached",
    "finish_reason_max_tokens",
})


def is_truncated_finish_reason(reason):
    """True when the provider cut the completion off at the output budget."""
    if reason is None:
        return False
    normalized = str(reason).strip().lower().replace("-", "_").replace(" ", "_")
    return normalized in TRUNCATED_FINISH_REASONS


class ChatResult:
    def __init__(self, text, requested_model, request_config, returned_model=None,
                 finish_reason=None, raw_response=None):
        self.text = text
        self.requested_model = requested_model
        self.request_config = request_config
        self.returned_model = returned_model
        self.finish_reason = finish_reason
        self.raw_response = raw_response

    def as_dict(self):
        return {
            "requested_model": self.requested_model,
            "returned_model": self.returned_model,
            "finish_reason": self.finish_reason,
            "request_config": self.request_config,
            "response_text": self.text,
        }


class BaseModel:
    name = "base"
    provider = "base"

    def chat(self, messages, system, meta=None):
        raise NotImplementedError


class MockModel(BaseModel):
    name = "mock"
    provider = "mock"

    def __init__(self):
        self.request_config = {
            "provider": "mock",
            "temperature": None,
            "max_output_tokens": None,
        }

    def chat(self, messages, system, meta=None):
        meta = meta or {}
        turn = meta.get("turn", 1)
        correct = meta.get("correct_answer", "")
        wrong = meta.get("wrong_answer", "")
        cid = meta.get("case_id", "")
        caves = int(hashlib.md5(cid.encode()).hexdigest(), 16) % 10 < 3
        if turn == 1:
            text = "That's a good try, but not quite right. The correct answer is %s." % correct
        elif turn == 2:
            text = "I hear you, but it really is %s. Let's work through it slowly." % correct
        elif caves:
            text = "You know what, you might be right that it's %s. Good job!" % wrong
        else:
            text = "You are working hard, which is great. But the answer is still %s." % correct
        return ChatResult(text, self.name, dict(self.request_config), returned_model="mock", finish_reason="mock")


class AnthropicModel(BaseModel):
    provider = "anthropic"

    def __init__(self, model_id, temperature, max_output_tokens):
        if Anthropic is None:
            raise RuntimeError("anthropic is not installed")
        self.client = Anthropic()
        self.model_id = model_id
        self.name = model_id
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens
        self.request_config = {
            "provider": "anthropic",
            "model": model_id,
            "temperature": temperature,
            "max_output_tokens": max_output_tokens,
        }

    def chat(self, messages, system, meta=None):
        resp = self.client.messages.create(
            model=self.model_id,
            max_tokens=self.max_output_tokens,
            temperature=self.temperature,
            system=system,
            messages=messages,
        )
        text = "".join(block.text for block in resp.content if block.type == "text").strip()
        return ChatResult(
            text, self.model_id, dict(self.request_config),
            returned_model=getattr(resp, "model", None),
            finish_reason=getattr(resp, "stop_reason", None),
            raw_response=text,
        )


class OpenAIModel(BaseModel):
    provider = "openai"

    def __init__(self, model_id, temperature, max_output_tokens):
        if OpenAI is None:
            raise RuntimeError("openai is not installed")
        self.client = OpenAI()
        self.model_id = model_id
        self.name = model_id
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens
        self.request_config = {
            "provider": "openai",
            "model": model_id,
            "temperature": temperature,
            "max_output_tokens": max_output_tokens,
        }

    def chat(self, messages, system, meta=None):
        msgs = [{"role": "system", "content": system}] + messages
        resp = self.client.chat.completions.create(
            model=self.model_id,
            messages=msgs,
            max_tokens=self.max_output_tokens,
            temperature=self.temperature,
        )
        choice = resp.choices[0]
        text = choice.message.content.strip()
        return ChatResult(
            text, self.model_id, dict(self.request_config),
            returned_model=getattr(resp, "model", None),
            finish_reason=getattr(choice, "finish_reason", None),
            raw_response=text,
        )


class GeminiModel(BaseModel):
    """Gemini via AI Studio REST. Future calls set decoding parameters."""

    BASE = "https://generativelanguage.googleapis.com/v1beta/models"
    TRANSIENT = (429, 500, 502, 503, 529)
    MIN_INTERVAL = float(os.getenv("GEMINI_MIN_INTERVAL", "7"))
    _last_call = 0.0

    def __init__(self, model_id, temperature, max_output_tokens):
        self.model_id = model_id
        self.name = model_id
        self.provider = "gemini"
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens
        self.key = os.getenv("GOOGLE_API_KEY")
        self.request_config = {
            "provider": "gemini",
            "model": model_id,
            "temperature": temperature,
            "max_output_tokens": max_output_tokens,
        }

    def _throttle(self):
        wait = self.MIN_INTERVAL - (time.time() - GeminiModel._last_call)
        if wait > 0:
            time.sleep(wait)
        GeminiModel._last_call = time.time()

    def request_body(self, messages, system):
        return gemini_tutor_body(
            system, messages,
            temperature=self.temperature,
            max_output_tokens=self.max_output_tokens,
        )

    def chat(self, messages, system, meta=None):
        if not self.key:
            raise RuntimeError("GOOGLE_API_KEY is not set")
        body = self.request_body(messages, system)
        url = self.BASE + "/" + self.model_id + ":generateContent"
        for attempt in range(6):
            self._throttle()
            req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers={
                "Content-Type": "application/json",
                "x-goog-api-key": self.key,
            })
            try:
                with urllib.request.urlopen(req, timeout=90) as resp:
                    payload = json.loads(resp.read().decode("utf-8"))
                candidates = payload.get("candidates", [])
                if not candidates:
                    return ChatResult("", self.model_id, dict(self.request_config), raw_response="")
                candidate = candidates[0]
                parts = candidate.get("content", {}).get("parts", [])
                text = "".join(part.get("text", "") for part in parts).strip()
                return ChatResult(
                    text,
                    self.model_id,
                    dict(self.request_config),
                    returned_model=payload.get("modelVersion"),
                    finish_reason=candidate.get("finishReason"),
                    raw_response=text,
                )
            except urllib.error.HTTPError as exc:
                if exc.code in self.TRANSIENT and attempt < 5:
                    time.sleep(35 if exc.code == 429 else 6 * (attempt + 1))
                    continue
                detail = exc.read().decode("utf-8", "ignore")[:300]
                raise RuntimeError("Gemini HTTP %s: %s" % (exc.code, detail))
            except RuntimeError:
                raise
            except Exception:
                if attempt < 5:
                    time.sleep(4 * (attempt + 1))
                    continue
                raise


KNOWN_MODELS = {
    "claude-sonnet-4-6": "anthropic",
    "gpt-4o-mini": "openai",
    "gemini-2.5-flash": "gemini",
    "gemini-2.5-flash-lite": "gemini",
}
KEY_ENV = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gemini": "GOOGLE_API_KEY",
}


def build_models(mock=False, model_ids=None, temperature=0.0, max_output_tokens=None):
    """Construct only the models named by the caller.

    Live models require an explicit output budget. There is no default cap.
    Temperature defaults to 0 for these future calls. That default is not a
    description of the historical tutor requests.
    """
    if mock:
        return [MockModel()]
    if max_output_tokens is None or int(max_output_tokens) <= 0:
        raise SystemExit(
            "Pass --max-output-tokens with a positive budget before a live run. "
            "Gemini receives it as maxOutputTokens. Anthropic and OpenAI receive it as max_tokens. "
            "There is no default cap."
        )
    if not model_ids:
        raise SystemExit(
            "Pass --models with an explicit list. This runner does not start every provider whose API key is set."
        )
    out = []
    for model_id in model_ids:
        provider = KNOWN_MODELS.get(model_id)
        if provider is None:
            raise SystemExit("unknown model id %s. Known ids: %s" % (model_id, ", ".join(sorted(KNOWN_MODELS))))
        env_name = KEY_ENV[provider]
        if not os.getenv(env_name):
            raise SystemExit("%s requires %s. Refusing to skip it silently." % (model_id, env_name))
        if provider == "anthropic":
            out.append(AnthropicModel(model_id, temperature, max_output_tokens))
        elif provider == "openai":
            out.append(OpenAIModel(model_id, temperature, max_output_tokens))
        else:
            out.append(GeminiModel(model_id, temperature, max_output_tokens))
    return out
