# Changelog

## 0.3.1 - 2026-10-16
* Add a brand icon (`brand/icon.png`) as required for the HACS default list.

## 0.3.0 - 2026-10-12
First public release.

* Sensors: state, door, course, stage, time remaining, reservation, "starts in".
* Finish-time reservation (select a course from the washer's history, set the finish time, press *Reserve*), cancel,
  services `reserve` / `cancel_reservation`. The course defaults to the one selected on the washer.
* *Start now* button and service `start` (starts the course selected on the washer; not tested on a real run).
* Login: manual one-time step (paste the `auth0://...` console line), re-authentication dialog, `state` check.
* Japanese and English texts, unit tests for decoding, reservation commands and the login paste.
