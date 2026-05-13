# Changelog

All notable changes to this project will be documented in this file.

The format is loosely based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- AGPL-3.0 LICENSE.
- `.github/ISSUE_TEMPLATE/bug_report.md`.
- `scripts/warm_up.py` — pre-caches `faster-whisper`, HuBERT, and RMVPE so the first offline hotkey fire is instant.
- `install_and_run.ps1` step `[5c]` — CUDA / GPU health check with optional `winget`-based NVIDIA driver install.
- `install_and_run.ps1` step `[5d]` — invokes `scripts/warm_up.py`; skipped automatically when pretrains are already present.
- `RESPEAKER_OUTPUT_DIR` env var — redirect generated WAVs to any directory (default: `audio_output/`).
- TtsWindow (Ctrl+Alt+6): **Play again** button (Ctrl+P) replays the last generation without re-synthesis; **Open folder** button opens the output directory in Explorer.
- `.ckpt` accepted alongside `.pth` for the RVC voice model (both in `models/respeaker/` and `Sound/<voice>/`).

### Changed
- Comprehensive `.gitignore` covering secrets, model weights, runtime artifacts, and vendored binaries.
- README License section spells out AGPL §13 implications for the HTTP API on port 8009.
- README "What `install_and_run.bat` does" section reflects the new CUDA + pre-warm steps.

### Removed
- `launch.bat` (redundant with `install_and_run.bat`).
- Duplicate `python-dotenv` line in `requirements.txt`.
