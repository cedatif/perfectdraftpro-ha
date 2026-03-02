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

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow pour PerfectDraft Pro.

    Flux :
    1. L'utilisateur saisit son email + mot de passe PerfectDraft
    2. On s'authentifie directement via AWS Cognito (pas de captcha)
    3. On récupère l'ID de la tireuse via /api/me
    4. Les tokens + machine_id sont stockés dans HA (chiffrés)
    5. L'intégration gère les renouvellements de token de façon autonome
    """

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Étape initiale : saisie des identifiants."""
        errors: dict[str, str] = {}

        if user_input is not None:
            email = user_input[CONF_EMAIL].strip().lower()
            password = user_input[CONF_PASSWORD]

            # Empêcher la double configuration du même compte
            await self.async_set_unique_id(email)
            self._abort_if_unique_id_configured()

            client = PerfectDraftClient(async_get_clientsession(self.hass))

            try:
                # Auth directe Cognito → pas de captcha
                await client.authenticate(email, password)

                # Récupérer la première tireuse associée au compte
                me = await client.get_me()
                machines = me.get("perfectdraftMachines", [])
                if not machines:
                    errors["base"] = "no_machine"
                else:
                    machine = machines[0]
                    return self.async_create_entry(
                        title=f"PerfectDraft Pro ({email})",
                        data={
                            # Credentials — stockés chiffrés par HA
                            CONF_EMAIL: email,
                            CONF_PASSWORD: password,
                            # Tokens — gérés automatiquement par l'intégration
                            STORE_ACCESS_TOKEN: client.access_token,
                            STORE_REFRESH_TOKEN: client.refresh_token,
                            STORE_TOKEN_EXPIRY: client.token_expiry,
                            # Tireuse identifiée au premier login
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
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
