# Working rules for AI-assisted changes

This repository is developed with AI assistance (Claude Code). These are the rules that assistance follows:

* **No secrets or personal data** in any file or test: no tokens, authorization codes, `appliance_id`, serial numbers, purchase
  data, addresses. Test data must be obviously fake (`tests/test_util.py` shows how).
* **Commands to a real washer** (start, reservation, cancel) are sent only after the owner has said so for that action, with the
  drum empty for anything that could run; reservations are cancelled again right after a test.
* **Credit**: code adapted from other projects keeps their licence notice (see `LICENSE` and the README's Acknowledgements). Do not
  copy Panasonic code; the API notes in `docs/findings.md` are descriptions, not copies.
* **Tests**: `cd tests && python3 -m unittest discover` must pass. `decode.py`, `reservation.py` and `util.py` stay free of Home
  Assistant imports so they can be tested alone.
* **What is verified** is stated in `docs/findings.md` and the README; keep those honest when behaviour changes.
* Commits use the GitHub noreply address; do not publish a private e-mail address.
* **Before every release** run the steps in `docs/RELEASE-CHECKLIST.md` (audit, unit tests, tests inside a real Home Assistant, minimum
  Home Assistant version). Green CI (hassfest, HACS validation) does not prove the integration behaves: it found neither the per-request
  `ZoneInfo(...)` on the event loop nor the `time` name that a platform module `time.py` silently replaced in `__init__.py`.
* **Outward-facing steps** (push, release, a comment on a pull request) only after the owner said yes for that action.
