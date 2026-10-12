"""Auth0 Authorization Code + PKCE for the Panasonic washer app.

Same situation as the Eolia integration: the app's Auth0 client only accepts its own custom
redirect URI, so the browser step is done by hand once (config_flow.py) and everything after
that runs on the refresh token.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import secrets
import time
from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import urlencode

from aiohttp import ClientError, ClientSession

from .const import (
    AUTH0_AUDIENCE,
    AUTH0_AUTHORIZE_URL,
    AUTH0_CLIENT_ID,
    AUTH0_REDIRECT_URI,
    AUTH0_SCOPE,
    AUTH0_TOKEN_URL,
    CONF_ACCESS_TOKEN,
    CONF_EXPIRES_AT,
    CONF_REFRESH_TOKEN,
    TOKEN_REFRESH_MARGIN_SECONDS,
)


class LaundryAuthError(Exception):
    """Login or token refresh failed."""

    def __init__(self, message: str, *, invalid_grant: bool = False) -> None:
        super().__init__(message)
        self.invalid_grant = invalid_grant


def generate_pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)[:128]
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).decode().rstrip("=")
    return verifier, challenge


def generate_state() -> str:
    return secrets.token_hex(16)


def build_authorize_url(*, code_challenge: str, state: str) -> str:
    params = {
        "response_type": "code",
        "client_id": AUTH0_CLIENT_ID,
        "redirect_uri": AUTH0_REDIRECT_URI,
        "scope": AUTH0_SCOPE,
        "audience": AUTH0_AUDIENCE,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "state": state,
    }
    return f"{AUTH0_AUTHORIZE_URL}?{urlencode(params)}"


async def _post_token(session: ClientSession, payload: dict[str, str]) -> dict[str, Any]:
    try:
        async with session.post(AUTH0_TOKEN_URL, data=payload) as resp:
            body = await resp.json(content_type=None)
            if resp.status >= 400:
                error = body.get("error", "unknown_error")
                raise LaundryAuthError(
                    f"Auth0 token request failed: {error} ({body.get('error_description', '')})",
                    invalid_grant=error == "invalid_grant",
                )
            return body
    except ClientError as err:
        raise LaundryAuthError(f"Network error talking to Auth0: {err}") from err


async def async_exchange_code(session: ClientSession, *, code: str, code_verifier: str) -> dict[str, Any]:
    return await _post_token(
        session,
        {
            "grant_type": "authorization_code",
            "client_id": AUTH0_CLIENT_ID,
            "code": code,
            "code_verifier": code_verifier,
            "redirect_uri": AUTH0_REDIRECT_URI,
        },
    )


async def async_exchange_refresh_token(session: ClientSession, *, refresh_token: str) -> dict[str, Any]:
    return await _post_token(
        session,
        {"grant_type": "refresh_token", "client_id": AUTH0_CLIENT_ID, "refresh_token": refresh_token},
    )


def token_data_to_entry_data(token_data: dict[str, Any]) -> dict[str, Any]:
    return {
        CONF_ACCESS_TOKEN: token_data["access_token"],
        CONF_REFRESH_TOKEN: token_data.get("refresh_token"),
        CONF_EXPIRES_AT: time.time() + token_data.get("expires_in", 0),
    }


class LaundryAuth:
    """Keeps the token set fresh; a new refresh token (if rotated) is reported through the callback."""

    def __init__(
        self,
        session: ClientSession,
        *,
        access_token: str,
        refresh_token: str,
        expires_at: float,
        on_tokens_updated: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
    ) -> None:
        self._session = session
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._expires_at = expires_at
        self._on_tokens_updated = on_tokens_updated
        self._lock = asyncio.Lock()

    async def async_get_access_token(self) -> str:
        async with self._lock:
            if time.time() >= self._expires_at - TOKEN_REFRESH_MARGIN_SECONDS:
                await self._refresh()
            return self._access_token

    async def async_force_refresh(self) -> str:
        async with self._lock:
            await self._refresh()
            return self._access_token

    async def _refresh(self) -> None:
        data = token_data_to_entry_data(
            await async_exchange_refresh_token(self._session, refresh_token=self._refresh_token)
        )
        self._access_token = data[CONF_ACCESS_TOKEN]
        if data[CONF_REFRESH_TOKEN]:
            self._refresh_token = data[CONF_REFRESH_TOKEN]
        self._expires_at = data[CONF_EXPIRES_AT]
        if self._on_tokens_updated is not None:
            await self._on_tokens_updated(
                {
                    CONF_ACCESS_TOKEN: self._access_token,
                    CONF_REFRESH_TOKEN: self._refresh_token,
                    CONF_EXPIRES_AT: self._expires_at,
                }
            )
