# Panasonic Washer-Dryer (スマホで洗濯) for Home Assistant

An **unofficial** Home Assistant custom integration for Panasonic **drum washer-dryers** that are connected to the Japanese
**"スマホで洗濯" (Smartphone Laundry)** app: status, finish-time reservations of courses from the washer's history, and a start
button.

> **Unofficial.** Not made, endorsed or supported by Panasonic. It talks to the same cloud API as the official Android app,
> which was worked out by reading that app. Panasonic can change or block it at any time, and using it may be against the terms
> of the service. Use it at your own risk and only with your own account and appliance. See the [disclaimer](#disclaimer).

## Why

The app is the only way to see what the washer is doing from outside the house, and there is no official API, no ECHONET Lite
on this model and no local interface. This integration brings the same information and the reservation into Home Assistant,
so that "laundry is done" notifications, dashboards and automations work.

## How this differs from other Panasonic integrations

* [specializedken/panasonic-eolia](https://github.com/specializedken/panasonic-eolia): Panasonic **Eolia air conditioners** (same
  Club Panasonic login). This project reuses its login approach, see [Acknowledgements](#acknowledgements).
* [sockless-coding/panasonic_cc](https://github.com/sockless-coding/panasonic_cc): Panasonic **Comfort Cloud** (air conditioners,
  heat pumps).
* [tsunglung/panasonic_ems2](https://github.com/tsunglung/panasonic_ems2) and [osk2/panasonic_smart_app](https://github.com/osk2/panasonic_smart_app):
  the **Panasonic Smart App / IoT** of other regions (Taiwan), including washers. The Japanese washer app is a different service with
  a different login and API, and none of the projects above supports it.

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

Tested on the real machine: a reservation with the course that was already selected on the washer (sent, read back, cancelled).
A reservation of another course (a drying-only one) was refused by the washer; washing courses with detergent settings are built
from the app's code but have not been tried.

## Requirements

* A Panasonic drum washer-dryer registered in the **スマホで洗濯** app (Club Panasonic account, Japan), with Wi-Fi on.
* Home Assistant 2025.1 or newer.
* A desktop browser (for the one-time login).

## Install

[![Open your Home Assistant instance and open this repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=1404423&repository=ha-panasonic-laundry&category=integration)

HACS: *HACS → ⋮ → Custom repositories* → add `https://github.com/1404423/ha-panasonic-laundry` as type **Integration**, install it,
restart Home Assistant. Manual: copy `custom_components/panasonic_laundry` to `<config>/custom_components/`.

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

## Limitations

* Tested on one machine only: **NA-LX127CL-W** (ななめドラム洗濯乾燥機, Japan). Other models of the same app (NA-LX129/127 series,
  NA-VG, NA-VX ...) may work; please open an issue with the model number.
* Reservations work for the course that is selected on the washer. Reserving another course through the cloud, including a
  drying-only course, was refused by the washer (see [docs/findings.md](docs/findings.md)).
* **Start now** has not been tested on a real run. There is no stop button; stop the washer on its panel.
* The washer must be switched on, waiting, with the door closed and the **遠隔 (remote)** lamp lit for any command.
* The status is polled every 60 seconds; the cloud sometimes answers "communication with the washer failed" once.
* The login needs a desktop browser once (and again when Panasonic invalidates the refresh token).

## Privacy

The integration talks only to Panasonic's servers (`auth.digital.panasonic.com`, `app.wad.apws.panasonic.com`). Your Panasonic ID
password is typed into Panasonic's own login page, never into Home Assistant. Home Assistant stores the OAuth access and refresh
tokens in the config entry (`.storage/core.config_entries`): treat backups of your Home Assistant configuration as secret.
The OAuth client id in `const.py` is the public one of the official app.

## Development

```
cd tests && python3 -m unittest discover -v
```

`custom_components/panasonic_laundry/decode.py`, `reservation.py` and `util.py` have no Home Assistant imports and carry the
unit tests. `tools/probe.py` is a small stdlib-only script that reads the status and builds or sends the same requests from a
terminal (needs a token file; read its header first). The API notes are in [docs/](docs/README.md).

`.github/workflows/` has the GitHub Actions workflows (HACS validation, hassfest, unit tests); they run on every push and daily.

## Acknowledgements

* **[specializedken/panasonic-eolia](https://github.com/specializedken/panasonic-eolia)** (MIT): the Auth0 PKCE login with the
  manual "paste the redirect URL" step, the token refresh class, the config-flow shape, the repository layout and the structure of
  this README were taken from or modelled on that project. Its copyright notice is in [LICENSE](LICENSE).
* **The official "スマホで洗濯" Android app by Panasonic**: the API (login, endpoints, status properties, reservation request) was
  worked out by reading the app. The Japanese course, stage and state names come from the app's own labels. No Panasonic code is
  included.
* **[ECHONET Lite](https://echonet.jp/english/)**: the status properties use ECHONET-Lite-style ids, which made the app's tables easier
  to read.
* The comparison projects listed above were read for orientation only; no code from them is used.
* The [Home Assistant developer documentation](https://developers.home-assistant.io/) for the integration structure.
* **AI assistance**: this integration was written with the help of Claude (Anthropic, via Claude Code) under the author's direction
  and testing on the author's own washer. [CLAUDE.md](CLAUDE.md) holds the working rules used for that.

## Disclaimer

This project is not affiliated with, endorsed by or supported by Panasonic. *Panasonic* and *スマホで洗濯* are trademarks or
product names of their owners and are used only to say which service this integration talks to. It uses the cloud with your own
account and controls your own appliance; use it at your own risk. The course and stage names are Panasonic's text, taken from the
app for convenience, and are not covered by this project's license.

## License

The code is released under the [MIT License](LICENSE) (with the notice of the project it was adapted from).

## 日本語

「スマホで洗濯」アプリに登録した、パナソニックのドラム式洗濯乾燥機の状態(状態・ドア・コース・工程・残り時間)を、
Home Assistant のセンサーとして読み取ります。**非公式**で、パナソニックとは無関係です。公式アプリと同じ通信を使うため、
仕様変更や規約に注意してください(自己責任)。運転の開始・予約には、対応していません。

ログインは、手動の手順が 1 回必要です(上の「Set up」を参照)。開発者ツールの Console に出る
`Failed to launch 'auth0://...?code=...'` の行を、丸ごと貼ってください。パスワードは、HA には保存されません。
