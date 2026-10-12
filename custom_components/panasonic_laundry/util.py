"""Helpers for the login step (no Home Assistant imports, unit-testable)."""

from __future__ import annotations

import re

_CODE_RE = re.compile(r"[?&]code=([A-Za-z0-9._~\-]+)")
_STATE_RE = re.compile(r"[?&]state=([A-Za-z0-9._~\-]+)")
_CALLBACK_RE = re.compile(r"auth0://[^\s'\"]+")


def _callback_part(text: str) -> str:
    """The `auth0://...` URL inside what was pasted (a console line also carries the consent page URL, which has its
    own `state=`); the whole text when there is no such URL."""
    match = _CALLBACK_RE.search(text)
    return match.group(0) if match else text


def extract_code(text: str) -> str:
    """Pull the authorization code out of whatever the user pasted.

    Accepts the bare code, the redirect URL, or the whole browser console line
    ("Failed to launch 'auth0://...?code=...&state=...' because ...").
    """
    text = text.strip()
    match = _CODE_RE.search(_callback_part(text))
    if match:
        return match.group(1)
    return re.sub(r"[\s'\"]", "", text)


def extract_state(text: str) -> str | None:
    """Return the `state` value of a pasted redirect URL, if there is one."""
    match = _STATE_RE.search(_callback_part(text))
    return match.group(1) if match else None
