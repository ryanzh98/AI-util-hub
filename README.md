# Voice Detection — Hotkey Productivity Tray App

A Windows system-tray utility that turns global hotkeys into voice transcription, AI text actions, snippet pasting, YouTube transcription, and voice cloning. Built with PyQt6 + faster-whisper + edge-tts + RVC.

## Features

| Hotkey       | Feature                                                                 |
| ------------ | ----------------------------------------------------------------------- |
| `Ctrl+Alt+0` | Launcher popup — grid of all configured shortcuts                       |
| `Ctrl+Alt+1` | Voice → Clipboard (online Whisper API)                                  |
| `Ctrl+Alt+2` | Voice → Clipboard (offline faster-whisper, CUDA-accelerated)            |
| `Ctrl+Alt+3` | Fix grammar — re-write clipboard text via an LLM                        |
| `Ctrl+Alt+4` | YouTube transcribe — paste a URL, get the full transcript               |
| `Ctrl+Alt+5` | Voice → Cloned voice playback — record, transcribe, speak in target voice |

Every shortcut is also exposed over HTTP on port 8009 so other machines (a VM without a GPU, for example) can call them programmatically. See the `app/api_server.py` route table.

## Quick Start (Windows)

```
1. Copy this folder anywhere.
2. Double-click install_and_run.bat   (right-click → Run as administrator the first time)
3. Edit .env, fill in OPENAI_API_KEY and OPENROUTER_API_KEY.
4. Done — app is running in the tray.
```

`install_and_run.bat` is idempotent — re-running it just launches the app once everything is in place.

### What `install_and_run.bat` does on first run

1. Auto-installs **Miniconda** silently into `%USERPROFILE%\miniconda3` if neither Anaconda nor Miniconda is found.
2. Creates a Conda env named `voice-detection` (Python 3.12).
3. Installs PyTorch with CUDA 12.8 (`cu128` — works on RTX 20/30/40/50-series).
4. Installs `requirements.txt` (PyQt6, faster-whisper, tts-with-rvc, fastapi, etc.).
5. Downloads the default RVC voice model (~250 MB) to `models/respeaker/`.
6. Copies `.env.example` → `.env` if missing.
7. **Detects CUDA state.** If an NVIDIA GPU is present but the driver is missing, offers to install it via `winget`. Falls back to CPU otherwise.
8. **Pre-warms offline models** — caches `faster-whisper large-v3-turbo` (~1.5 GB), `hubert_base.pt` (~180 MB), and `rmvpe.pt` (~170 MB) so the first Ctrl+Alt+2 / Ctrl+Alt+5 / Ctrl+Alt+6 hotkey fire is instant. Skipped automatically on re-runs when already cached.
9. Launches the app in the system tray.

On subsequent runs, every check above is a fast no-op (~20 s end-to-end) — only step 9 does real work.

## Prerequisites

- **Windows 10/11 (64-bit)**
- **NVIDIA GPU** recommended — RTX 20-series or newer for `Ctrl+Alt+2` (offline Whisper) and `Ctrl+Alt+5` (voice cloning). Older Pascal+ GPUs work too; CPU-only also works but slowly.
- **NVIDIA driver 525+** (newer is better). Update via GeForce Experience or <https://nvidia.com/drivers> if you hit CUDA errors.
- **FFmpeg** on `PATH` if you'll use YouTube transcribe (Ctrl+Alt+4). Download <https://ffmpeg.org/download.html>.
- An OpenAI API key (online Whisper) and OpenRouter API key (grammar/AI actions).
- (Conda is auto-installed by the bat file — you don't need to install it manually.)

## Configuration

All runtime config lives in `.env`. See `.env.example` for the full annotated list. Key blocks:

| Variable                  | Purpose                                                              |
| ------------------------- | -------------------------------------------------------------------- |
| `OPENAI_API_KEY`          | Online Whisper (`Ctrl+Alt+1`)                                        |
| `OPENROUTER_API_KEY`      | Grammar fix + AI Actions                                             |
| `WHISPER_INITIAL_PROMPT`  | Biasing prompt for accented English / multilingual audio             |
| `WHISPER_LOCAL_MODEL`     | Local Whisper model name (default `large-v3-turbo`)                  |
| `WHISPER_LANGUAGES`       | Comma-separated allow-list, e.g. `en,zh`                             |
| `LAUNCHER_API_*`          | HTTP API server settings (host, port, bearer token)                  |
| `RESPEAKER_MODEL_PATH`    | `.pth` file of the RVC voice model                                   |
| `RESPEAKER_INDEX_PATH`    | `.index` file (optional but strongly improves quality)               |
| `RESPEAKER_BASE_VOICE`    | edge-tts voice — affects accent. Match target's gender.              |
| `RESPEAKER_PITCH`         | Semitone shift, -12..+12 (use -12 for female base → male target)     |
| `RESPEAKER_INDEX_RATE`    | Accent-mix strength 0..1 (default 0.75)                              |
| `RESPEAKER_DEVICE`        | `cuda:0` or `cpu`                                                    |
| `RESPEAKER_OUTPUT_DIR`    | Where generated WAVs are saved. Default: `audio_output/` at project root |
| `CLIPBOARD_ACTIONS_PATH`  | Override path to `clipboard_actions.json`                            |

## Voice cloning (Ctrl+Alt+5)

1. `install_and_run.bat` downloads the default voice model and saves it as `models/respeaker/voice.pth` + `models/respeaker/voice.index`.
2. **Swap voices**: drop another RVC model into `models/respeaker/`, rename the `.pth` to `voice.pth` and the `.index` to `voice.index`. No `.env` edit needed. Both `.pth` and `.ckpt` checkpoints are accepted (standard RVC inference format — the loader uses plain `torch.load`).
3. Or point at a different filename by editing `RESPEAKER_MODEL_PATH` / `RESPEAKER_INDEX_PATH` in `.env`.
4. Sources for RVC models: <https://weights.gg>, Hugging Face (`RVC` search), AI Hub Discord.
5. **Naming gotcha when downloading raw training output**: the usable `.pth` is in the `weights/` folder. `D_*` / `G_*` files are training checkpoints — skip them. For the `.index`, pick the one starting with `added_`.

`install_and_run.bat` pre-warms the engine on first install, so the first `Ctrl+Alt+5` fire is already instant. HuBERT + RMVPE pretrains (~370 MB) land at the project root; if they ever go missing, re-run the installer to fetch them again.

## Configuring shortcuts

Right-click the tray icon → **Manage shortcuts…** opens the manager window. You can:

- Toggle any built-in shortcut on/off
- Change global hotkeys
- Add custom **AI Actions** (your own prompts + model + temperature) and bind hotkeys to them
- Add **snippets** (text or URL) to the launcher grid

The config persists to `clipboard_actions.json` in the project root.

## HTTP API

Every shortcut is reachable on `http://0.0.0.0:8009`:

```bash
# Health check (no auth)
curl http://localhost:8009/healthz

# List shortcuts
curl http://localhost:8009/items

# Fire grammar fix
curl -X POST http://localhost:8009/slot/sys-grammar \
  -H 'Content-Type: application/json' \
  -d '{"text":"helo wrld"}'

# Transcribe offline (e.g. from a VM without a GPU)
curl -X POST http://host-ip:8009/slot/sys-voice-offline \
  --data-binary @sample.wav \
  -H 'Content-Type: audio/wav'

# Speak text in the cloned voice (returns played-WAV path)
curl -X POST http://localhost:8009/slot/sys-voice-respeaker \
  -H 'Content-Type: application/json' \
  -d '{"text":"Hello from the API."}'
```

Set `LAUNCHER_API_TOKEN=<token>` to require `Authorization: Bearer <token>` on every route except `/healthz`. Set `LAUNCHER_API_ENABLED=0` to disable the server entirely.

If accessing from another machine, allow inbound TCP 8009 in Windows Firewall:

```powershell
New-NetFirewallRule -DisplayName "Voice Detection API 8009" -Direction Inbound -Protocol TCP -LocalPort 8009 -Action Allow
```

## Auto-start at login

The app auto-creates a startup-folder shortcut (and a Start Menu shortcut) the first time it runs. If you want to disable auto-start, remove `VoiceDetection.lnk` from `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup`. To re-add, right-click tray → **Re-add to startup**.

## Troubleshooting

| Symptom                                                | Fix                                                                                         |
| ------------------------------------------------------ | ------------------------------------------------------------------------------------------- |
| Hotkeys don't fire                                     | Run elevated (or once at login). Some apps consume the hotkey first.                       |
| "torch.cuda.is_available() = False"                    | Wrong CUDA variant. Edit the `$TorchIndex` line in `install_and_run.ps1` to `cu121` (older GPU) or remove for CPU, then re-run. |
| "sm_120 not compatible"                                | You're on RTX 50-series with old torch. Re-run `install_and_run.bat` (default is `cu128`). |
| "RVC model not found"                                  | `models/respeaker/*.pth` missing. Re-run `install_and_run.bat` or set `RESPEAKER_MODEL_PATH`. |
| Voice cloning sounds wrong gender                      | Set `RESPEAKER_BASE_VOICE` to a same-gender edge-tts voice, or use `RESPEAKER_PITCH=-12`.   |
| First Ctrl+Alt+5 takes 30s                             | Model lazy-load + pretrain download. Subsequent fires are fast. Pre-warm by firing once at startup. |
| `tts-with-rvc` install fails                           | Confirm you're on Python 3.12 (not 3.13/3.14). `install_and_run.bat` handles this automatically. |
| Port 8009 in use                                        | Change `LAUNCHER_API_PORT` in `.env` and restart.                                           |
| App won't start after Windows update / Conda upgrade   | Delete the env (`conda env remove -n voice-detection`) and re-run `install_and_run.bat`.   |

## File layout

```
voice_detection/
├── main.py                       # Entry point
├── install_and_run.bat           # One-shot setup (delegates to install_and_run.ps1)
├── install_and_run.ps1           # Idempotent installer + launcher
├── requirements.txt
├── .env / .env.example
├── clipboard_actions.json        # Shortcut config (user-local, gitignored)
├── app/
│   ├── tray_controller.py        # Hotkey dispatch + worker orchestration
│   ├── hotkey_manager.py         # pynput GlobalHotKeys wrapper
│   ├── launcher_window.py        # Ctrl+Alt+0 popup grid
│   ├── manager_window.py         # Shortcut config UI
│   ├── recorder_window.py        # Voice capture UI
│   ├── youtube_window.py         # YouTube URL input UI
│   ├── audio_recorder.py         # sounddevice wrapper
│   ├── whisper_client.py         # Online OpenAI Whisper
│   ├── local_whisper_client.py   # Offline faster-whisper
│   ├── grammar_online_client.py  # OpenRouter grammar fix
│   ├── clipboard_action_worker.py # OpenRouter generic AI Action
│   ├── youtube_audio_worker.py   # yt-dlp download
│   ├── respeaker_client.py       # TTS + RVC voice cloning  ← Ctrl+Alt+5
│   ├── api_server.py             # FastAPI HTTP server
│   ├── actions_config.py         # JSON config schema
│   ├── hotkey_recorder.py        # Hotkey capture widget
│   ├── speaker_mute.py           # Pycaw speaker mute
│   ├── startup_manager.py        # Windows shortcut creation
│   └── state.py
├── design/                       # QSS stylesheets + design tokens
├── models/respeaker/             # RVC voice models (.pth + .index)
├── audio_temp/                   # edge-tts intermediates (auto-created, gitignored)
└── audio_output/                 # RVC-converted WAVs (auto-created, gitignored)
```

Runtime-generated files that are **not** committed: `audio_temp/`, `audio_output/`,
`crash.log`, `models/respeaker/voice.pth` + `voice.index` (auto-downloaded),
`clipboard_actions.json` (user config), and `.env` (your API keys). See `.gitignore`.

## License

Code in this repository is licensed under the **GNU AGPL-3.0** — see [LICENSE](LICENSE).

If you run a modified version of this software as a network service (the FastAPI
server on port 8009 counts), AGPL §13 requires you to offer those users the
corresponding source code of your modified version.

Third-party assets keep their own licenses:

- Microphone tray icon adapted from Lucide (ISC) — see `assets/LICENSE-icons.txt`.
- RVC voice models are user-supplied and carry their own licenses — check each model card.
- `tts-with-rvc`, `faster-whisper`, `PyQt6`, etc. are upstream packages — see `requirements.txt`.
