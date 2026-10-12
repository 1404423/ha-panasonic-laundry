"""Config flow: log in once in a browser, paste the redirect URL, pick the washer.

The app's Auth0 client only accepts its own custom redirect URI (auth0://...), so the browser ends on a
page it cannot open. The authorization code is then copied from the browser's developer tools by hand.
The same form is used for the first setup and for re-authentication. The manual "paste the redirect URL" login follows
https://github.com/specializedken/panasonic-eolia (MIT).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import LaundryApi, LaundryApiError
from .auth import (
    LaundryAuth,
    LaundryAuthError,
    async_exchange_code,
    build_authorize_url,
    generate_pkce_pair,
    generate_state,
    token_data_to_entry_data,
)
from .const import CONF_APPLIANCE_ID, CONF_NICKNAME, DOMAIN
from .util import extract_code, extract_state

LOGIN_FIELD = "authorization_response"


class LaundryConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._verifier, challenge = generate_pkce_pair()
        self._state = generate_state()
        self._authorize_url = build_authorize_url(code_challenge=challenge, state=self._state)
        self._tokens: dict[str, Any] = {}
        self._devices: list[dict[str, Any]] = []

    # --- shared login -------------------------------------------------------------------------------------------

    async def _async_login(self, pasted: str) -> str | None:
        """Exchange the pasted code for tokens and load the device list. Returns an error key or None."""
        pasted_state = extract_state(pasted)
        if pasted_state is not None and pasted_state != self._state:
            return "state_mismatch"  # the link was not the one shown in this dialog
        session = async_get_clientsession(self.hass)
        try:
            token_data = await async_exchange_code(
                session, code=extract_code(pasted), code_verifier=self._verifier
            )
            self._tokens = token_data_to_entry_data(token_data)
            auth = LaundryAuth(
                session,
                access_token=self._tokens["access_token"],
                refresh_token=self._tokens["refresh_token"],
                expires_at=self._tokens["expires_at"],
            )
            self._devices = await LaundryApi(session, auth).async_get_devices()
        except LaundryAuthError:
            return "invalid_auth"
        except LaundryApiError:
            return "cannot_connect"
        return None

    def _login_form(self, step_id: str, errors: dict[str, str]) -> ConfigFlowResult:
        return self.async_show_form(
            step_id=step_id,
            data_schema=vol.Schema({vol.Required(LOGIN_FIELD): str}),
            description_placeholders={"authorize_url": self._authorize_url},
            errors=errors,
        )

    # --- first setup --------------------------------------------------------------------------------------------

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            error = await self._async_login(user_input[LOGIN_FIELD])
            if error is None and not self._devices:
                error = "no_devices"
            if error is None:
                return await self.async_step_device()
            errors["base"] = error
        return self._login_form("user", errors)

    async def async_step_device(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        names = {
            d["appliance_id"]: f'{d.get("nickname") or d.get("product_code")} ({d.get("product_code")})'
            for d in self._devices
        }
        if user_input is not None:
            appliance_id = user_input[CONF_APPLIANCE_ID]
            await self.async_set_unique_id(appliance_id)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=names[appliance_id],
                data={**self._tokens, CONF_APPLIANCE_ID: appliance_id, CONF_NICKNAME: names[appliance_id]},
            )
        return self.async_show_form(
            step_id="device",
            data_schema=vol.Schema({vol.Required(CONF_APPLIANCE_ID, default=next(iter(names))): vol.In(names)}),
        )

    # --- re-authentication --------------------------------------------------------------------------------------

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            error = await self._async_login(user_input[LOGIN_FIELD])
            if error is None and entry.data[CONF_APPLIANCE_ID] not in {d["appliance_id"] for d in self._devices}:
                error = "wrong_account"  # logged in with an account that does not own this washer
            if error is None:
                return self.async_update_reload_and_abort(entry, data_updates=self._tokens)
            errors["base"] = error
        return self._login_form("reauth_confirm", errors)
