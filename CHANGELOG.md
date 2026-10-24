# Changelog

## 0.3.3 - 2026-10-24
* Review fix: the API time zone is resolved once during setup (`dt_util.async_get_time_zone`) and kept on the API object, instead of building
  `ZoneInfo(...)` (a disk read on the event loop) for every request. The config flow does the same; a missing tz database now gives an
  "Unexpected error" instead of a crash.
* Fix: the name `time` imported in `__init__.py` collided with the platform module `time.py`; once Home Assistant imported the platform before
  the coordinator was created, setup failed with `'module' object is not callable`. It only worked by import order. Now imported as `dt_time`.
* Minimum Home Assistant is **2025.3** (was documented as 2025.1): `AddConfigEntryEntitiesCallback` does not exist before 2025.3.
* New: diagnostics (tokens, ids and the nickname are redacted), `icons.json`, `PARALLEL_UPDATES` on every platform, missing "Unexpected error" text.
* New: tests inside a real Home Assistant (`tests/ha`: config flow, re-authentication, setup/unload, failure paths, services, diagnostics),
  `tools/ha_audit.py`, `tools/min_ha_version.py` and `docs/RELEASE-CHECKLIST.md`.
* README: removal instructions, the Japanese text no longer says reservations/start are unsupported.

## 0.3.2 - 2026-10-16
* Add a brand icon (`brand/icon.png`) as required for the HACS default list.

## 0.3.0 - 2026-10-12
First public release.

* Sensors: state, door, course, stage, time remaining, reservation, "starts in".
* Finish-time reservation (select a course from the washer's history, set the finish time, press *Reserve*), cancel,
  services `reserve` / `cancel_reservation`. The course defaults to the one selected on the washer.
* *Start now* button and service `start` (starts the course selected on the washer; not tested on a real run).
* Login: manual one-time step (paste the `auth0://...` console line), re-authentication dialog, `state` check.
* Japanese and English texts, unit tests for decoding, reservation commands and the login paste.
