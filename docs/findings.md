# What is known about the washer's cloud API

Everything here comes from reading the official Android app "スマホで洗濯" (Smartphone Laundry, package
`com.panasonic.SmartLaundry`, version 2.14.00, Japan) and from calls made with the author's own account to the author's own
washer (NA-LX127CL-W). Items marked *verified* were seen working on that machine; *not verified* is read from the app only.

## Login (Auth0, Authorization Code + PKCE)

* Authorize: `https://auth.digital.panasonic.com/authorize`, token: `https://auth.digital.panasonic.com/oauth/token`.
* The client id is the app's public one (see `const.py`). Scope `openid offline_access smartlaundry.control`,
  audience `https://club.panasonic.jp/<client id>/api/v1/`.
* The client only accepts its own redirect URI `auth0://auth.digital.panasonic.com/android/com.panasonic.SmartLaundry/callback`.
  A browser cannot open it, so the code is copied from the developer tools console (`Failed to launch '...?code=...&state=...'`).
  The `state` of the callback URL must be compared with the one sent; a console line also carries the consent page's own
  `state=`, so only the `auth0://` URL may be read.
* Access token lifetime: 24 h (`expires_in 86400`); a refresh token is issued (`offline_access`).

## API (`https://app.wad.apws.panasonic.com/laundry/v5`)

Headers on every call: `Authorization: Bearer <token>`, `Cookie: atkn=<token>`, `X-Timestamp: yyyyMMddHHmmss+0900` (JST),
`Content-Type: application/json;charset=UTF-8`.

| Call | Use |
|---|---|
| `GET user/devices` | Registered appliances (*verified*). `hashed_guid` can be empty; then `user/devices/status?hashed_guid=` fails with 400 - use `device/status`. |
| `GET device/status` + header `X-ApplianceId` | All properties as `{id, params:[{value}]}`, hex strings (*verified*). `X-Cached: true` returns the cloud's copy. |
| `GET device/info?com_id=<model>` | Model info; `supported_cmds` was empty for NA-LX127C (*verified*). |
| `POST device/control` | Property writes: `{"requests":[{"appliance_id","cmd_type":"02","cmds":[{"id","params":[{"value"}]}],"protocol":"echonetlite","seq_no":1}]}`; success = HTTP 200, `status_code "200"`, `cmd_result true` (*verified* for reservation and cancel). |
| `POST laundry/command` | Not a control call: returns course information (*not verified*). |

Errors seen: HTTP 400 `L3E11-018-1302` ("communication with the washer may have failed") once on a cancel - the retry a few
seconds later worked; `cmd_result false` with HTTP 200 when the washer refuses a command.

## Status properties (ECHONET-Lite-style ids, hex strings)

| id | Meaning | Values |
|---|---|---|
| `0080` | operating state | `30` on, `31` off |
| `0088` | fault | `41` fault, `42` none |
| `00B0` | door | `41` open, `42` closed |
| `00B2` | start/stop (write) | `41` start, `42` pause, `43` stop (*not verified*) |
| `00D0` | course | code, e.g. `21` 洗濯・乾燥 おまかせ, `61` 洗濯 おまかせ, `A1` 乾燥 おまかせ, `BF` 乾燥 槽乾燥 (table in `const.py`) |
| `00E2` | stage / transition state | `41` washing, `42` rinsing, `43` spinning, `52` drying, `61` waiting before a run, `45/51/53/54/EF` finished kinds |
| `0121` | driving situation (finer than `00E2`) | `00` waiting, `01` washing, `03` rinsing, `05` spinning, `06` drying, ... |
| `00ED` `00DB` `00DC` | time remaining (all / washing / drying) | two hex bytes HH MM, `FFFF` unknown |
| `0090` | reservation timer | `41` on, `42` off |
| `0092` | time until the run should be **finished** | HH MM as hex bytes (2 h 30 min = `021E`), 10-minute steps |
| `00F2` | time until the run starts (computed by the washer, keeps changing) | HH MM |
| `0100` | remote operation | `01` permitted (遠隔 lamp lit), `02` not permitted |
| `012B` | recent courses | 10 x 4 bytes, newest first, first byte = course code |

## Reservation (*verified*)

One `device/control` request with `0092` (finish in), `0090 = 41` and `00D0` (course). On NA-LX127CL-W it was accepted only for
the course that was already selected on the washer; `A1` (乾燥 おまかせ) and, as a single write, `BF` were refused
(`cmd_result false`, nothing changed) - whether that is because of the course type or because the cloud refuses course
changes is not known. Cancel: `0090 = 42` (retry on `L3E11-018-1302`). Needs `0100 = 01`, door closed, washer waiting.

## Start now (*not verified on a real run*)

`00B2 = 41` for the course selected on the washer, with the same preconditions. The official app sends the new course together with
the start; a course change on its own is refused.
