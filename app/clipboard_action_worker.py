"""Generic OpenRouter worker that runs a user-defined prompt against clipboard text."""

import os

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "google/gemma-4-26b-a4b-it:free"


def run_action(prompt: str, model: str, temperature: float, text: str) -> str:
    """Run an OpenRouter chat completion synchronously and return stripped content.

    Raises RuntimeError on any failure (empty input, missing config, API error, bad response).
    """
    if not text or not text.strip():
        raise RuntimeError("Clipboard is empty")

    if not prompt or not prompt.strip():
        raise RuntimeError("Action has no prompt configured")

    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not api_key or api_key == "sk-or-replace-me":
        raise RuntimeError("OPENROUTER_API_KEY is not set in .env")

    base_url = os.environ.get("OPENROUTER_BASE_URL", "").strip() or DEFAULT_BASE_URL

    resolved_model = (model or "").strip()
    if not resolved_model:
        resolved_model = os.environ.get("OPENROUTER_ACTION_DEFAULT_MODEL", "").strip()
    if not resolved_model:
        resolved_model = DEFAULT_MODEL

    try:
        temp = float(temperature)
    except (TypeError, ValueError):
        temp = 0.2
    if temp < 0.0:
        temp = 0.0
    elif temp > 2.0:
        temp = 2.0

    try:
        from openai import OpenAI
    except ImportError as e:
        raise RuntimeError(f"openai package missing: {e}")

    try:
        client = OpenAI(api_key=api_key, base_url=base_url, timeout=30.0)
        resp = client.chat.completions.create(
            model=resolved_model,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": text},
            ],
            temperature=temp,
        )
    except Exception as e:
        raise RuntimeError(f"OpenRouter call failed: {e}")

    try:
        content = resp.choices[0].message.content or ""
    except (AttributeError, IndexError, TypeError) as e:
        raise RuntimeError(f"Bad OpenRouter response: {e}")

    result = content.strip()
    if not result:
        raise RuntimeError("Model returned an empty response")
    return result


class ClipboardActionWorker(QObject):
    done = pyqtSignal(str)
    failed = pyqtSignal(str)

    @pyqtSlot(str, str, float, str)
    def run(self, prompt: str, model: str, temperature: float, text: str) -> None:
        try:
            result = run_action(prompt, model, temperature, text)
        except RuntimeError as e:
            self.failed.emit(str(e))
            return
        except Exception as e:
            self.failed.emit(f"OpenRouter call failed: {e}")
            return
        self.done.emit(result)
