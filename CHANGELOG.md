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
- **Dual-output playback** for `Ctrl+Alt+5` / `Ctrl+Alt+6` — *Advanced voice settings* now has **Playback device 1** and **Playback device 2**, so the generated audio can fan out to two outputs simultaneously (e.g. speakers + VB-Audio CABLE Input → OBS captures the cable while you still hear it). Either slot can be set to `(System default)`, `(None)`, or any Windows output device. Persists per-hotkey in `clipboard_actions.json`. Legacy single-slot `playback_device` is auto-migrated to slot 1.
- **Save audio** button on Ctrl+Alt+6 (TTS) popup (Ctrl+S) — Save-As dialog copies the last generated WAV to a user-chosen path.
- Ctrl+Alt+5 (recorder) keeps its window open in respeaker mode through a new **DONE** state with **Replay** + **Save audio** buttons — mic-recorded clones can now be replayed and exported without firing the hotkey again.

### Changed
- *Advanced voice settings* info-dot `?` markers are now `QToolButton`s with both hover- and click-to-show tooltips. The previous `QLabel` implementation silently dropped tooltip events on Tool/translucent popups.
- Spinbox up/down sub-controls in *Advanced voice settings* are now explicitly styled (16×12 buttons with CSS-triangle arrows) so they render and accept clicks against the dark theme.
- Comprehensive `.gitignore` covering secrets, model weights, runtime artifacts, and vendored binaries.
- README License section spells out AGPL §13 implications for the HTTP API on port 8009.
- README "What `install_and_run.bat` does" section reflects the new CUDA + pre-warm steps.

### Removed
- `fcpe` from the F0 method picker — caused CUDA-driver segfaults on some GPU/driver combos that required a Windows reboot to recover. Legacy `clipboard_actions.json` entries with `rvc_f0_method: "fcpe"` are silently coerced to `rmvpe` at runtime and purged from JSON on next save.
- `launch.bat` (redundant with `install_and_run.bat`).
- Duplicate `python-dotenv` line in `requirements.txt`.
