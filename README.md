# Panasonic Washer-Dryer (スマホで洗濯) for Home Assistant

Status, finish-time reservations and a start button for a Panasonic drum washer-dryer that is connected to the Japanese
**"スマホで洗濯" (Smartphone Laundry)** app:
state, door, course, stage and time remaining as Home Assistant sensors, the washer's recent history, and **finish-time
reservations** of courses from that history. You can use them for "laundry is done" notifications, dashboards or automations.

> **Unofficial.** This integration is not made, endorsed or supported by Panasonic. It talks to the same cloud API as the official
> Android app, which was worked out by reading that app. Panasonic can change or block it at any time, and using it may be
> against the terms of the service. Use it at your own risk and only with your own account and appliance.

## What you get

| Entity | Values |
|---|---|
| `sensor` State | off / waiting / running / paused / finished / error |
| `sensor` Door | open / closed |
| `sensor` Course | the selected course (e.g. "洗濯・乾燥 おまかせ") |
| `sensor` Stage | what the machine is doing now (washing, rinsing, spinning, drying, unwinding, ...) |
| `sensor` Time remaining | minutes (unknown while no run is active) |
| `sensor` Reservation | none / reserved |
| `sensor` Starts in | minutes until a reserved run starts (computed by the washer, it keeps recalculating) |
| `select` Reservation course | **only courses from the washer's history** (its last 10 courses) |
| `time` Reservation finish time | time of day the run should be finished (next time the clock shows it) |
| `button` Reserve / Cancel reservation | send the reservation with the two values above / turn it off |
| `button` Start now | start the course that is selected on the washer right now |

Services (for automations): `panasonic_laundry.reserve` (`course`, `finish_time`), `panasonic_laundry.cancel_reservation` and `panasonic_laundry.start`.

The status is polled every 60 seconds.

### Reservations

A reservation is the washer's own *finish-time* timer: you say when the run should be **finished**, the washer works out when
to start. It is sent as the official app does it (finish time + timer on + course). Rules:

* Only courses that are in the washer's recent history can be chosen (the history is read from the washer, 10 entries).
* It is only sent when the washer is switched on, waiting before a run, the door is closed, there is no fault and the
  **遠隔 (remote) button on the washer has been pressed** so its lamp is lit. Otherwise you get an error that says which.
* The finish time must be between 10 minutes and 24 hours from now (10-minute steps).
* After sending, the integration reads the status back and reports an error if the reservation did not show up.
  Cancelling is retried (the cloud sometimes answers "communication with the washer failed" once).
* **Start now** starts the course that is selected on the washer (the official app's start without a new course). It uses the
  same checks (switched on, waiting, door closed, no fault, 遠隔 lamp lit) and is refused while a reservation is set. A person has
  to load the drum and close the door; the 遠隔 lamp is the physical safety gate. There is no stop button (stop it on the washer).
  The start command was built from the app's code (`00B2` = `41`) and **has not been tested on a real run**.
* Changing a course through the cloud on its own is refused by the washer; the course is only sent together with a reservation.

Tested on the real machine: a reservation with the already selected course (sent, read back, cancelled). Reservations of
*other* courses and washing courses with detergent settings are implemented following the app's code but not all tested yet.

## Tested with

* NA-LX127CL-W (ななめドラム洗濯乾燥機), Japan, Club Panasonic account: status, reservation of the course that is selected on the
  washer, cancelling. Not tested on a real run: **Start now**. Refused by this model: reserving or switching to another course
  through the cloud (tried a drying-only course).

Other models of the same app (NA-LX129/127 series, NA-VG, NA-VX ...) may work; please open an issue with the model number.

## Install

[![Open your Home Assistant instance and open this repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=1404423&repository=ha-panasonic-laundry&category=integration)

HACS: *HACS → ⋮ → Custom repositories* → add `https://github.com/1404423/ha-panasonic-laundry` as type **Integration**, install it, restart Home Assistant.
Manual: copy `custom_components/panasonic_laundry` to `<config>/custom_components/`.

Requires Home Assistant 2025.1 or newer.

## Set up (login)

The app's login only accepts its own redirect address (`auth0://...`), so one step is manual and needs a desktop browser:

1. *Settings → Devices & services → Add integration → Panasonic Washer-Dryer*.
2. Open the shown link in a browser **with the developer tools' Console tab open** (Chrome: F12, Mac: Cmd+Option+I).
3. Log in with your Panasonic ID. The page then stays blank and the console shows a line like
   `Failed to launch 'auth0://...?code=...&state=...' because the scheme does not have a registered handler.`
4. Paste that whole line (or only the `auth0://...` address, or only the code) into the dialog and pick your washer.

The code is single-use and expires within a minute or so. Your password is never seen by Home Assistant; only the tokens
(access token and refresh token) are stored in the config entry. When the login expires Home Assistant asks you to log in again
(the same steps).

## Troubleshooting

* *"This address comes from a different login link"*: use the link shown in the open dialog, not an older one.
* *"Login failed"*: the code expired or was already used; log in again and paste right away.
* *No washer listed*: register it in the official app first (the app's "My家電" list).

## Privacy

The integration talks only to Panasonic's servers (`auth.digital.panasonic.com`, `app.wad.apws.panasonic.com`). Your Panasonic ID
password is typed into Panasonic's own login page, never into Home Assistant. Home Assistant stores the OAuth access and refresh
tokens in the config entry (`.storage/core.config_entries`): treat backups of your Home Assistant configuration as secret.
The OAuth client id in `const.py` is the public one of the official app.

## Development

`ci/validate.yml` is the GitHub Actions workflow (hassfest, HACS validation, unit tests). Copy it to `.github/workflows/validate.yml`
(pushing workflow files needs a token with the `workflow` permission).

`custom_components/panasonic_laundry/decode.py` and `util.py` have no Home Assistant imports; run the tests with

```
cd tests && python3 -m unittest discover -v
```

## 日本語

「スマホで洗濯」アプリに登録した、パナソニックのドラム式洗濯乾燥機の状態(状態・ドア・コース・工程・残り時間)を、
Home Assistant のセンサーとして読み取ります。**非公式**で、パナソニックとは無関係です。公式アプリと同じ通信を使うため、
仕様変更や規約に注意してください(自己責任)。運転の開始・予約には、対応していません。

ログインは、手動の手順が 1 回必要です(上の「Set up」を参照)。開発者ツールの Console に出る
`Failed to launch 'auth0://...?code=...'` の行を、丸ごと貼ってください。パスワードは、HA には保存されません。

## License

MIT, see `LICENSE`.
