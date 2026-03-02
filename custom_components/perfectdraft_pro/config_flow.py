"""Config flow for PerfectDraft Pro integration."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_EMAIL,
    CONF_PASSWORD,
    DOMAIN,
    STORE_ACCESS_TOKEN,
    STORE_DEVICE_UUID,
    STORE_MACHINE_ID,
    STORE_REFRESH_TOKEN,
    STORE_TOKEN_EXPIRY,
)
from .perfectdraft_api import PerfectDraftAuthError, PerfectDraftClient

_LOGGER = logging.getLogger(__name__)

STEP_CREDENTIALS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

STEP_TOKENS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(STORE_ACCESS_TOKEN): str,
        vol.Required(STORE_REFRESH_TOKEN): str,
        vol.Required(STORE_MACHINE_ID): vol.Coerce(int),
        vol.Required(STORE_DEVICE_UUID): str,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow pour PerfectDraft Pro.

    Deux modes :
    - credentials : email + mot de passe (nécessite reCAPTCHA → utiliser get_tokens.py)
    - tokens      : coller les tokens obtenus via get_tokens.py
    """

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Étape initiale : choix du mode de configuration."""
        return self.async_show_menu(
            step_id="user",
            menu_options=["credentials", "tokens"],
        )

    # ------------------------------------------------------------------ #
    # Mode 1 : email + mot de passe                                        #
    # ------------------------------------------------------------------ #

    async def async_step_credentials(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Authentification via email + mot de passe."""
        errors: dict[str, str] = {}

        if user_input is not None:
            email = user_input[CONF_EMAIL].strip().lower()
            password = user_input[CONF_PASSWORD]

            await self.async_set_unique_id(email)
            self._abort_if_unique_id_configured()

            client = PerfectDraftClient(async_get_clientsession(self.hass))

            try:
                await client.authenticate(email, password)
                me = await client.get_me()
                machines = me.get("perfectdraftMachines", [])
                if not machines:
                    errors["base"] = "no_machine"
                else:
                    machine = machines[0]
                    return self.async_create_entry(
                        title=f"PerfectDraft Pro ({email})",
                        data={
                            CONF_EMAIL: email,
                            CONF_PASSWORD: password,
                            STORE_ACCESS_TOKEN: client.access_token,
                            STORE_REFRESH_TOKEN: client.refresh_token,
                            STORE_TOKEN_EXPIRY: client.token_expiry,
                            STORE_MACHINE_ID: machine["id"],
                            STORE_DEVICE_UUID: machine["deviceId"],
                        },
                    )

            except PerfectDraftAuthError:
                errors["base"] = "invalid_auth"
            except aiohttp.ClientConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Erreur inattendue lors de la configuration")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="credentials",
            data_schema=STEP_CREDENTIALS_SCHEMA,
            errors=errors,
        )

    # ------------------------------------------------------------------ #
    # Mode 2 : tokens obtenus via get_tokens.py                           #
    # ------------------------------------------------------------------ #

    async def async_step_tokens(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Saisie manuelle des tokens obtenus via le script get_tokens.py."""
        errors: dict[str, str] = {}

        if user_input is not None:
            email = user_input[CONF_EMAIL].strip().lower()

            await self.async_set_unique_id(email)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=f"PerfectDraft Pro ({email})",
                data={
                    CONF_EMAIL: email,
                    CONF_PASSWORD: "",
                    STORE_ACCESS_TOKEN: user_input[STORE_ACCESS_TOKEN].strip(),
                    STORE_REFRESH_TOKEN: user_input[STORE_REFRESH_TOKEN].strip(),
                    STORE_TOKEN_EXPIRY: 0.0,
                    STORE_MACHINE_ID: user_input[STORE_MACHINE_ID],
                    STORE_DEVICE_UUID: user_input[STORE_DEVICE_UUID].strip(),
                },
            )

        return self.async_show_form(
            step_id="tokens",
            data_schema=STEP_TOKENS_SCHEMA,
            errors=errors,
        )
