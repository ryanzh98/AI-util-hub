import os

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "google/gemma-4-26b-a4b-it:free"

SYSTEM_PROMPT = (
    "Fix grammar and spelling errors in the user's text. "
    "Preserve meaning, tone, line breaks, code blocks, and formatting exactly. "
    "Output only the corrected text — no preamble, no explanation, no surrounding quotes."
)


def fix_grammar(text: str) -> str:
    if not text or not text.strip():
        raise RuntimeError("Clipboard is empty")

    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not api_key or api_key == "sk-or-replace-me":
        raise RuntimeError("OPENROUTER_API_KEY is not set in .env")

    base_url = os.environ.get("OPENROUTER_BASE_URL", "").strip() or DEFAULT_BASE_URL
    model = os.environ.get("OPENROUTER_GRAMMAR_MODEL", "").strip() or DEFAULT_MODEL

    try:
        from openai import OpenAI
    except ImportError as e:
        raise RuntimeError(f"openai package missing: {e}")

    try:
        client = OpenAI(api_key=api_key, base_url=base_url, timeout=30.0)
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            temperature=0.2,
        )
    except Exception as e:
        raise RuntimeError(f"OpenRouter call failed: {e}")

    try:
        content = resp.choices[0].message.content or ""
    except (AttributeError, IndexError, TypeError) as e:
        raise RuntimeError(f"Bad OpenRouter response: {e}")

    fixed = content.strip()
    if not fixed:
        raise RuntimeError("Gemma returned empty response")
    return fixed


class OnlineGrammarFixWorker(QObject):
    done = pyqtSignal(str)
    failed = pyqtSignal(str)

    @pyqtSlot(str)
    def fix(self, text: str) -> None:
        try:
            result = fix_grammar(text)
        except RuntimeError as e:
            self.failed.emit(str(e))
            return
        except Exception as e:
            self.failed.emit(f"OpenRouter call failed: {e}")
            return
        self.done.emit(result)
