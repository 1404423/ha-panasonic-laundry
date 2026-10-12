#!/usr/bin/env python3
"""Developer probe for the Panasonic washer API (stdlib only). NOT part of the integration.

  probe.py status                      read the washer status and show the reservation-relevant values
  probe.py plan   --finish-in 10:00    show the request that `reserve` would send (sends nothing)
  probe.py reserve --finish-in 10:00 --yes   SEND the finish-time reservation, then read the status back
  probe.py cancel --yes                SEND "timer off", then read the status back
  probe.py start  --drum-empty --yes   START the tank-drying course right now (the only course allowed in this tool)
  probe.py stop   --yes                SEND "stop" (00B2=43), then read the status back

Needs a token file (default $LAUNDRY_TOKEN_FILE or ./laundry-token.json) with the Auth0 token response
(access_token / refresh_token); it is refreshed automatically. Never commit that file.

What the official web UI does (see docs/CHANGELOG.md, 2026-10-12): POST /laundry/v5/device/control
  {"requests":[{"appliance_id":..., "cmd_type":"02", "cmds":[{"id":"0092","params":[{"value":"0A00"}]},
   {"id":"0090","params":[{"value":"41"}]}, {"id":"00D0","params":[{"value":<course>}]}],
   "protocol":"echonetlite", "seq_no":1}]}
0092 = time until the washer should be finished (two hex bytes HH MM, 10-minute steps), 0090 = 41 timer on / 42 off.
"""

from __future__ import annotations

import argparse
import datetime
import importlib.util
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("c", os.path.join(HERE, "..", "custom_components", "panasonic_laundry", "const.py"))
const = importlib.util.module_from_spec(spec)
spec.loader.exec_module(const)

JST = datetime.timezone(datetime.timedelta(hours=9))
TOKEN_FILE = os.environ.get("LAUNDRY_TOKEN_FILE", "laundry-token.json")


def _post_form(url: str, data: dict) -> dict:
    req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode(), headers={"Content-Type": "application/x-www-form-urlencoded"})
    return json.load(urllib.request.urlopen(req, timeout=30))


def token() -> str:
    t = json.load(open(TOKEN_FILE))
    if time.time() < t.get("_expires_at", 0) - 300:
        return t["access_token"]
    new = _post_form(const.AUTH0_TOKEN_URL, {"grant_type": "refresh_token", "client_id": const.AUTH0_CLIENT_ID, "refresh_token": t["refresh_token"]})
    t.update(new)
    t["_expires_at"] = time.time() + new.get("expires_in", 0)
    os.umask(0o077)
    json.dump(t, open(TOKEN_FILE, "w"))
    return t["access_token"]


def api(method: str, path: str, headers: dict | None = None, body: dict | None = None):
    tok = token()
    h = {
        "Authorization": f"Bearer {tok}",
        "Cookie": f"atkn={tok}",
        "X-Timestamp": datetime.datetime.now(JST).strftime(const.API_TIMESTAMP_FORMAT),
        "Content-Type": "application/json;charset=UTF-8",
        "Accept": "application/json",
        **(headers or {}),
    }
    req = urllib.request.Request(f"{const.API_BASE_URL}/{path}", data=json.dumps(body).encode() if body is not None else None, headers=h, method=method)
    try:
        return json.load(urllib.request.urlopen(req, timeout=60))
    except urllib.error.HTTPError as e:
        raise SystemExit(f"HTTP {e.code} on {path}: {e.read().decode()[:500]}")


def appliance() -> dict:
    return api("GET", "user/devices")["devices"][0]


def status(appliance_id: str, cached: bool = False) -> dict[str, str]:
    data = api("GET", "device/status", {"X-ApplianceId": appliance_id, **({"X-Cached": "true"} if cached else {})})
    return {x["id"]: x["params"][0]["value"] for x in data["status"] if x.get("params")}


def hex_hhmm(minutes: int) -> str:
    return f"{minutes // 60:02X}{minutes % 60:02X}"


def parse_hhmm(text: str) -> int:
    h, _, m = text.partition(":")
    minutes = int(h) * 60 + int(m or 0)
    if minutes <= 0 or minutes % 10:
        raise SystemExit("--finish-in must be a positive multiple of 10 minutes (e.g. 10:00)")
    return minutes


def show(st: dict[str, str]) -> None:
    stage = const.STAGES.get(st.get("00E2", "").upper(), ("?", "?"))
    print(f"power 0080={st.get('0080')} (30 on / 31 off)   fault 0088={st.get('0088')} (42 none)")
    print(f"door 00B0={st.get('00B0')} (42 closed / 41 open)   remote 0100={st.get('0100')} (01 permitted / 02 NOT permitted)")
    print(f"stage 00E2={st.get('00E2')} {stage}   course 00D0={st.get('00D0')} {const.COURSES.get((st.get('00D0') or '').upper())}")
    print(f"reservation: 0090={st.get('0090')} (41 on / 42 off)  0092={st.get('0092')}  00F2={st.get('00F2')}")


def precheck(st: dict[str, str]) -> list[str]:
    problems = []
    if st.get("0080") != "30":
        problems.append("power is not on")
    if st.get("0088") == "41":
        problems.append("the washer reports a fault")
    if const.STAGES.get(st.get("00E2", "").upper(), ("", "wait"))[1] != "wait":
        problems.append(f"the washer is not waiting before a run (00E2={st.get('00E2')})")
    if st.get("00B0") != "42":
        problems.append(f"the door is not closed (00B0={st.get('00B0')})")
    if st.get("0100") != "01":
        problems.append(f"remote operation is not permitted (0100={st.get('0100')}); press the 遠隔 button on the washer")
    return problems


def reserve_request(appliance_id: str, st: dict[str, str], minutes: int, course: str | None = None) -> dict:
    cmds = [
        {"id": "0092", "params": [{"value": hex_hhmm(minutes)}]},
        {"id": "0090", "params": [{"value": "41"}]},
        {"id": "00D0", "params": [{"value": course or st["00D0"]}]},  # default: the course that is selected on the washer
    ]
    return {"requests": [{"appliance_id": appliance_id, "cmd_type": "02", "cmds": cmds, "protocol": "echonetlite", "seq_no": 1}]}


def cancel_request(appliance_id: str) -> dict:
    return {"requests": [{"appliance_id": appliance_id, "cmd_type": "02", "cmds": [{"id": "0090", "params": [{"value": "42"}]}], "protocol": "echonetlite", "seq_no": 1}]}


TANK_DRY = "BF"  # 乾燥 槽乾燥: dries the empty drum, no water, no laundry. The only course this tool will start.
DRY_ONLY_TEST = {"BF", "A1"}  # reservation tests may use these drying-only courses (empty drum)


def control_request(appliance_id: str, cmds: list[tuple[str, str]]) -> dict:
    return {"requests": [{"appliance_id": appliance_id, "cmd_type": "02", "cmds": [{"id": i, "params": [{"value": v}]} for i, v in cmds],
                          "protocol": "echonetlite", "seq_no": 1}]}


def send(body: dict) -> None:
    res = api("POST", "device/control", body=body)
    print("response:", json.dumps(res, ensure_ascii=False)[:800])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["status", "plan", "reserve", "cancel", "start", "stop"])
    ap.add_argument("--course", help="reserve this course code instead of the selected one (tests: only BF, tank drying, is allowed)")
    ap.add_argument("--drum-empty", action="store_true", help="I confirm the drum is empty (needed for start)")
    ap.add_argument("--finish-in", default="10:00")
    ap.add_argument("--yes", action="store_true", help="really send to the washer")
    ap.add_argument("--force", action="store_true", help="ignore the pre-checks")
    a = ap.parse_args()
    dev = appliance()
    aid = dev["appliance_id"]
    st = status(aid)
    print(f"washer {dev.get('product_code')} ({dev.get('nickname')})")
    show(st)
    if a.cmd == "status":
        return
    if a.cmd == "stop":
        body = control_request(aid, [("00B2", "43")])
    elif a.cmd == "start":
        problems = precheck(st)
        if st.get("0090") == "41":
            problems.append("a reservation is on (0090=41); cancel it first")
        if not a.drum_empty:
            problems.append("--drum-empty not given: tank drying must run with an EMPTY drum")
        for p in problems:
            print("PRECHECK:", p)
        if problems and not a.force:
            raise SystemExit("not sending: fix the above first")
        steps = []
        if st.get("00D0") != TANK_DRY:
            steps.append(control_request(aid, [("00D0", TANK_DRY)]))
        steps.append(control_request(aid, [("00B2", "41")]))
        for n, body in enumerate(steps, 1):
            print(f"step {n}/{len(steps)} request body:", json.dumps(body, ensure_ascii=False))
        if not a.yes:
            print("(nothing sent; add --yes to send)")
            return
        for n, body in enumerate(steps, 1):
            send(body)
            time.sleep(6)
            now = status(aid)
            print(f"--- status after step {n}:")
            show(now)
            if n < len(steps) and now.get("00D0") != TANK_DRY:
                raise SystemExit("the course did not switch to tank drying; stopping before the start command")
        return
    elif a.cmd == "cancel":
        body = cancel_request(aid)
    else:
        problems = precheck(st)
        for p in problems:
            print("PRECHECK:", p)
        if problems and not a.force:
            raise SystemExit("not sending: fix the above first (or --force)")
        if a.course and a.course.upper() not in DRY_ONLY_TEST and a.course.upper() != st.get("00D0"):
            raise SystemExit(f"--course: tests are limited to drying-only courses {sorted(DRY_ONLY_TEST)} (empty drum) or the course already selected")
        body = reserve_request(aid, st, parse_hhmm(a.finish_in), a.course.upper() if a.course else None)
    print("request body:", json.dumps(body, ensure_ascii=False))
    if a.cmd == "plan" or not a.yes:
        print("(nothing sent; add --yes with reserve/cancel to send)")
        return
    send(body)
    time.sleep(5)
    print("--- status after:")
    show(status(aid))


if __name__ == "__main__":
    main()
