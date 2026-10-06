"""Model adapters behind one tiny interface: chat(messages, system) -> str."""
import hashlib
import os
import time


class BaseModel:
    name = "base"

    def chat(self, messages, system, meta=None):
        raise NotImplementedError


class MockModel(BaseModel):
    name = "mock"

    def chat(self, messages, system, meta=None):
        meta = meta or {}
        turn = meta.get("turn", 1)
        correct = meta.get("correct_answer", "")
        wrong = meta.get("wrong_answer", "")
        cid = meta.get("case_id", "")
        caves = int(hashlib.md5(cid.encode()).hexdigest(), 16) % 10 < 3
        if turn == 1:
            return (f"That's a good try, but not quite right. The correct answer is {correct}.")
        if turn == 2:
            return (f"I hear you, but it really is {correct}. Let's work through it slowly.")
        if caves:
            return (f"You know what, you might be right that it's {wrong}. Good job!")
        return (f"You are working hard, which is great. But the answer is still {correct}.")


class AnthropicModel(BaseModel):
    def __init__(self, model_id):
        from anthropic import Anthropic
        self.client = Anthropic()
        self.model_id = model_id
        self.name = model_id

    def chat(self, messages, system, meta=None):
        resp = self.client.messages.create(
            model=self.model_id, max_tokens=400, system=system, messages=messages,
        )
        return "".join(b.text for b in resp.content if b.type == "text").strip()


class OpenAIModel(BaseModel):
    def __init__(self, model_id):
        from openai import OpenAI
        self.client = OpenAI()
        self.model_id = model_id
        self.name = model_id

    def chat(self, messages, system, meta=None):
        msgs = [{"role": "system", "content": system}] + messages
        resp = self.client.chat.completions.create(
            model=self.model_id, messages=msgs, max_tokens=400,
        )
        return resp.choices[0].message.content.strip()


class GeminiModel(BaseModel):
    """Gemini via free AI Studio REST. Throttled to respect free-tier limits."""

    BASE = "https://generativelanguage.googleapis.com/v1beta/models"
    TRANSIENT = (429, 500, 502, 503, 529)
    MIN_INTERVAL = float(os.getenv("GEMINI_MIN_INTERVAL", "7"))  # seconds between calls
    _last_call = 0.0

    def __init__(self, model_id):
        self.model_id = model_id
        self.name = model_id
        self.key = os.getenv("GOOGLE_API_KEY")

    def _throttle(self):
        wait = self.MIN_INTERVAL - (time.time() - GeminiModel._last_call)
        if wait > 0:
            time.sleep(wait)
        GeminiModel._last_call = time.time()

    def chat(self, messages, system, meta=None):
        import json as _json
        import urllib.error as _err
        import urllib.request as _req

        contents = [
            {"role": ("user" if m["role"] == "user" else "model"),
             "parts": [{"text": m["content"]}]}
            for m in messages
        ]
        body = _json.dumps({
            "system_instruction": {"parts": [{"text": system}]},
            "contents": contents,
        }).encode("utf-8")
        url = self.BASE + "/" + self.model_id + ":generateContent"
        for attempt in range(6):
            self._throttle()
            req = _req.Request(url, data=body, headers={
                "Content-Type": "application/json",
                "x-goog-api-key": self.key,
            })
            try:
                with _req.urlopen(req, timeout=90) as resp:
                    payload = _json.loads(resp.read().decode("utf-8"))
                cands = payload.get("candidates", [])
                if not cands:
                    return ""
                parts = cands[0].get("content", {}).get("parts", [])
                return "".join(p.get("text", "") for p in parts).strip()
            except _err.HTTPError as e:
                if e.code in self.TRANSIENT and attempt < 5:
                    time.sleep(35 if e.code == 429 else 6 * (attempt + 1))
                    continue
                detail = e.read().decode("utf-8", "ignore")[:300]
                raise RuntimeError("Gemini HTTP %s: %s" % (e.code, detail))
            except Exception:
                if attempt < 5:
                    time.sleep(4 * (attempt + 1))
                    continue
                raise


DEFAULT_MODELS = [
    ("anthropic", "claude-sonnet-4-6"),
    ("openai", "gpt-4o-mini"),
    ("gemini", "gemini-2.5-flash"),
    ("gemini", "gemini-2.5-flash-lite"),
]


def build_models(mock=False):
    if mock:
        return [MockModel()]
    out = []
    for provider, model_id in DEFAULT_MODELS:
        try:
            if provider == "anthropic":
                if not os.getenv("ANTHROPIC_API_KEY"):
                    continue
                out.append(AnthropicModel(model_id))
            elif provider == "openai":
                if not os.getenv("OPENAI_API_KEY"):
                    continue
                out.append(OpenAIModel(model_id))
            elif provider == "gemini":
                if not os.getenv("GOOGLE_API_KEY"):
                    continue
                out.append(GeminiModel(model_id))
        except Exception as e:
            print(f"  skipping {provider}:{model_id} ({e})")
    if not out:
        raise SystemExit("No models available. Set an API key or use --mock.")
    return out
