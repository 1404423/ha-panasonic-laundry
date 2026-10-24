"""Thin client for the washer app's cloud API (https://app.wad.apws.panasonic.com/laundry/v5)."""

from __future__ import annotations

from datetime import datetime, tzinfo
from typing import Any

from aiohttp import ClientError, ClientSession

from .auth import LaundryAuth, LaundryAuthError
from .const import API_BASE_URL, API_TIMESTAMP_FORMAT

CMD_TYPE_SET = "02"
PROTOCOL = "echonetlite"
TRANSIENT_CODE = "L3E11-018-1302"  # "communication with the washer may have failed" - seen once, the retry worked


class LaundryApiError(Exception):
    """Request failed (network or HTTP error, or the washer refused the command)."""

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.code = code

    @property
    def transient(self) -> bool:
        return self.code == TRANSIENT_CODE


class LaundryApi:
    def __init__(self, session: ClientSession, auth: LaundryAuth, time_zone: tzinfo) -> None:
        """time_zone is the API's zone (const.API_TIMEZONE), resolved once by the caller with `await dt_util.async_get_time_zone(...)`: building a ZoneInfo reads the tz database from disk, which must not happen on the event loop for every request."""
        self._session = session
        self._auth = auth
        self._time_zone = time_zone

    async def _request(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        body: dict[str, Any] | None = None,
        retried: bool = False,
    ) -> Any:
        token = await self._auth.async_get_access_token()
        all_headers = {
            "Authorization": f"Bearer {token}",
            "Cookie": f"atkn={token}",
            "X-Timestamp": datetime.now(self._time_zone).strftime(API_TIMESTAMP_FORMAT),
            "Content-Type": "application/json;charset=UTF-8",
            "Accept": "application/json",
            **(headers or {}),
        }
        try:
            async with self._session.request(method, f"{API_BASE_URL}/{path}", headers=all_headers, json=body) as resp:
                if resp.status in (401, 403) and not retried:
                    await self._auth.async_force_refresh()
                    return await self._request(method, path, headers=headers, body=body, retried=True)
                if resp.status >= 400:
                    text = await resp.text()
                    code = None
                    try:
                        code = (await resp.json(content_type=None)).get("code")
                    except Exception:  # noqa: BLE001 - the error body is only used to pick out the code
                        pass
                    raise LaundryApiError(f"HTTP {resp.status} on {path}: {text[:200]}", code=code)
                return await resp.json(content_type=None)
        except ClientError as err:
            raise LaundryApiError(f"Network error on {path}: {err}") from err
        except LaundryAuthError:
            raise

    async def async_get_devices(self) -> list[dict[str, Any]]:
        return (await self._request("GET", "user/devices")).get("devices", [])

    async def async_get_status(self, appliance_id: str) -> dict[str, str]:
        """Return {property id: hex string} for one appliance."""
        data = await self._request("GET", "device/status", headers={"X-ApplianceId": appliance_id})
        return {item["id"]: item["params"][0]["value"] for item in data.get("status", []) if item.get("params")}

    async def async_control(self, appliance_id: str, cmds: list[tuple[str, str]]) -> None:
        """Send property writes (as the official app does). Raises LaundryApiError if the washer refuses."""
        body = {
            "requests": [
                {
                    "appliance_id": appliance_id,
                    "cmd_type": CMD_TYPE_SET,
                    "cmds": [{"id": prop, "params": [{"value": value}]} for prop, value in cmds],
                    "protocol": PROTOCOL,
                    "seq_no": 1,
                }
            ]
        }
        data = await self._request("POST", "device/control", body=body)
        result = (data.get("results") or [{}])[0]
        if result.get("status_code") != "200" or result.get("cmd_result") is not True:
            raise LaundryApiError(
                f"The washer did not accept the command (status {result.get('status_code')}, cmd_result {result.get('cmd_result')})"
            )
