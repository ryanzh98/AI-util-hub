import json
import os
import urllib.error
import urllib.request

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

DEFAULT_HOST = "http://localhost:11434"
DEFAULT_MODEL = "gemma4:e4b"

SYSTEM_PROMPT = (
    "Fix grammar and spelling errors in the user's text. "
    "Preserve meaning, tone, line breaks, code blocks, and formatting exactly. "
    "Output only the corrected text — no preamble, no explanation, no surrounding quotes."
)


class GrammarFixWorker(QObject):
    done = pyqtSignal(str)
    failed = pyqtSignal(str)

    @pyqtSlot(str)
    def fix(self, text: str) -> None:
        if not text or not text.strip():
            self.failed.emit("Clipboard is empty")
            return

        host = os.environ.get("OLLAMA_HOST", "").strip() or DEFAULT_HOST
        model = os.environ.get("GRAMMAR_MODEL", "").strip() or DEFAULT_MODEL
        url = host.rstrip("/") + "/api/chat"

        payload = json.dumps({
            "model": model,
            "stream": False,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            "options": {"temperature": 0.2},
        }).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                body = resp.read()
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                detail = e.read().decode("utf-8", "replace")
            except Exception:
                pass
            if e.code == 404 and "model" in detail.lower():
                self.failed.emit(
                    f"Model '{model}' not found. Run: ollama pull {model}"
                )
            else:
                self.failed.emit(f"Ollama HTTP {e.code}: {detail[:200] or e.reason}")
            return
        except urllib.error.URLError as e:
            self.failed.emit(
                f"Ollama not reachable at {host} — is `ollama serve` running? ({e.reason})"
            )
            return
        except TimeoutError:
            self.failed.emit("Ollama timed out after 180 s")
            return
        except Exception as e:
            self.failed.emit(f"Grammar fix failed: {e}")
            return

        try:
            data = json.loads(body)
            content = (data.get("message") or {}).get("content", "")
        except Exception as e:
            self.failed.emit(f"Bad Ollama response: {e}")
            return

        fixed = (content or "").strip()
        if not fixed:
            self.failed.emit("Gemma returned empty response")
            return
        self.done.emit(fixed)
