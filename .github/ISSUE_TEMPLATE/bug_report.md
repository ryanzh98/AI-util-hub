---
name: Bug report
about: Something's broken or behaving unexpectedly
title: ''
labels: bug
assignees: ''
---

**What happened?**
A short description of the bug.

**Which feature / hotkey?**
e.g. `Ctrl+Alt+1` (online Whisper), `Ctrl+Alt+5` (voice clone), tray menu, HTTP API.

**Steps to reproduce**
1.
2.
3.

**Expected vs. actual**
- Expected:
- Actual:

**Environment**
- Windows version (`winver`):
- Python / conda env: output of `conda env list | findstr voice-detection`
- GPU + NVIDIA driver:
- `torch.version.cuda` (run `python -c "import torch; print(torch.version.cuda)"` inside the env):

**Logs**
Attach `crash.log` if it has content. Paste any stderr from the console window (run `install_and_run.bat` from a terminal to see it).
