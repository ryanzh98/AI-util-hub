# Changelog

All notable changes to this project will be documented in this file.

The format is loosely based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- AGPL-3.0 LICENSE.
- `.github/ISSUE_TEMPLATE/bug_report.md`.

### Changed
- Comprehensive `.gitignore` covering secrets, model weights, runtime artifacts, and vendored binaries.
- README License section spells out AGPL §13 implications for the HTTP API on port 8009.

### Removed
- `launch.bat` (redundant with `install_and_run.bat`).
- Duplicate `python-dotenv` line in `requirements.txt`.
