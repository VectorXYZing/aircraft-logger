# Changelog

All notable changes to this project are documented in this file.

## Unreleased

- Refactor: Extracted metadata lookup into `airlogger/metadata.py` (OpenSky-only) with retries, backoff and caching.
- Tests: Added unit tests for metadata and message parsing; added CI workflow (`.github/workflows/ci.yml`).
- Docs: Updated README to remove references to legacy helper scripts and document OpenSky-only policy.
- Scripts: Added new OpenSky helper scripts and **removed** legacy ADSB.lol-based scripts (legacy files deleted from repository).
- Cleanup: Improved project structure and documentation.
- Fix: Dashboard now uses configurable `AIRLOGGER_LOG_DIR` and respects `AIRLOGGER_TZ` (if set). Improved performance by only loading files for the selected date.
- Fix: Email sender validates SMTP configuration, supports SSL and retries, and attaches compressed logs to reduce email size.
- Fix: `setup.sh` no longer hardcodes service user/paths and avoids installing unnecessary packages.
- Feature: Added heartbeat file writer and dashboard health checks (`/status` includes heartbeat info; `/health` endpoint returns 200 if recent). 
