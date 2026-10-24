# Release checklist

Run everything below before tagging a release. (The same rules, with the reasoning, live in the `ha-integration-review` skill that the
maintainer's AI assistant uses.)

1. `python3 tools/ha_audit.py .` - static audit: blocking calls in the event loop, name collisions in `__init__.py`, `PARALLEL_UPDATES`,
   translation/strings consistency, services, manifest/HACS files, README sections, private data. Must end with `FAIL=0`; read the WARN/INFO lines.
2. `cd tests && python3 -m unittest discover` - pure-module unit tests (no Home Assistant needed).
3. Tests inside a real Home Assistant:
   `python3.13 -m venv v && v/bin/pip install pytest-homeassistant-custom-component && v/bin/python -m pytest tests/ha`
   (config flow incl. every error and re-authentication, setup/unload, setup failure paths, a service error path, diagnostics redaction).
4. `v/bin/python tools/min_ha_version.py .` - the oldest Home Assistant version in which every import exists; `hacs.json` and the README must say the same.
   Methods and keyword arguments are not covered: grep them in the old wheel.
5. Optional but useful: run once on a Home Assistant with `debug: true` under `homeassistant:` and watch the log for "Detected blocking call".
6. Bump `version` in `manifest.json`, add a `CHANGELOG.md` entry, commit, push, create the GitHub **release** (a tag alone is not enough),
   and check that the HACS and hassfest workflows are green.
