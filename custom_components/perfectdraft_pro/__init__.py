"""PerfectDraft Pro integration for Home Assistant."""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    STORE_ACCESS_TOKEN,
    STORE_DEVICE_UUID,
    STORE_MACHINE_ID,
    STORE_REFRESH_TOKEN,
    STORE_TOKEN_EXPIRY,
    UPDATE_INTERVAL,
)
from .perfectdraft_api import PerfectDraftApiError, PerfectDraftAuthError, PerfectDraftClient

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up PerfectDraft Pro from a config entry."""
    client = PerfectDraftClient(async_get_clientsession(hass))

    stored_expiry = entry.data.get(STORE_TOKEN_EXPIRY, 0.0)
    if stored_expiry <= 0:
        stored_expiry = time.time() + 3540

    client.restore_session(
        access_token=entry.data[STORE_ACCESS_TOKEN],
        refresh_token=entry.data[STORE_REFRESH_TOKEN],
        token_expiry=stored_expiry,
        machine_id=entry.data.get(STORE_MACHINE_ID),
    )

    machine_id = entry.data[STORE_MACHINE_ID]
    device_uuid = entry.data[STORE_DEVICE_UUID]

    coordinator = PerfectDraftCoordinator(hass, entry, client, machine_id, device_uuid)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


# ------------------------------------------------------------------ #
# Coordinator                                                          #
# ------------------------------------------------------------------ #

class PerfectDraftCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator de données — interroge l'API PerfectDraft toutes les 60 s."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: PerfectDraftClient,
        machine_id: int,
        device_uuid: str,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )
        self.entry = entry
        self.client = client
        self.machine_id = machine_id
        self.device_uuid = device_uuid

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            # Requêtes parallèles pour minimiser la latence
            machine, keg_data, rewards = await asyncio.gather(
                self.client.get_machine(self.machine_id),
                self.client.get_machine_keg(self.machine_id),
                self.client.get_rewards(),
            )

            # Persister les tokens potentiellement renouvelés
            _persist_tokens(self.hass, self.entry, self.client)

            return await _build_state(self.client, machine, keg_data, rewards)

        except PerfectDraftAuthError as err:
            raise UpdateFailed(f"Erreur d'authentification : {err}") from err
        except PerfectDraftApiError as err:
            raise UpdateFailed(f"Erreur API : {err}") from err
        except Exception as err:
            raise UpdateFailed(f"Erreur inattendue : {err}") from err


# ------------------------------------------------------------------ #
# Helpers                                                              #
# ------------------------------------------------------------------ #

async def _build_state(
    client: PerfectDraftClient,
    machine: dict,
    keg_data: dict,
    rewards: dict,
) -> dict[str, Any]:
    """Assembler l'état complet depuis les réponses API."""
    details = machine.get("details") or {}
    setting = machine.get("setting") or {}
    keg_active = keg_data.get("kegActive")
    rewards_data = rewards.get("rewards") or {}
    tier_data = rewards.get("tier") or {}

    # Résoudre le nom de la bière
    beer_name = None
    keg_inserted_at = None
    if keg_active:
        keg_inserted_at = keg_active.get("insertedAt")
        product_id = _extract_id(keg_active.get("keg", ""))
        if product_id:
            try:
                product = await client.get_product(product_id)
                beer_name = product.get("name") or product.get("title")
            except PerfectDraftApiError:
                pass

    detail_settings = details.get("settings") or {}
    time_to_temp_ms = details.get("timeToReachTargetTemperature")

    return {
        # Température
        "temperature": details.get("displayedBeerTemperatureInCelsius"),
        "target_temperature": setting.get("temperature"),
        "temp_min": setting.get("temperatureMin", 0),
        "temp_max": setting.get("temperatureMax", 12),
        # Fût
        "keg_volume": details.get("kegVolume"),
        "keg_pressure": details.get("kegPressure"),
        "keg_type": details.get("kegType"),
        # Verres
        "last_pour_volume": details.get("volumeOfLastPour"),
        "last_pour_duration": details.get("durationOfLastPour"),
        "pours_since_startup": details.get("numberOfPoursSinceStartup"),
        # Divers
        "time_to_temp": round(time_to_temp_ms / 1000) if time_to_temp_ms else None,
        "error_codes": details.get("errorCodes"),
        "firmware_version": details.get("firmwareVersion"),
        "serial_number": details.get("serialNumber"),
        # États binaires
        "door_closed": details.get("doorClosed"),
        "connected": details.get("connectedState"),
        "boost": setting.get("boost"),
        "eco_mode": detail_settings.get("ecoModeEnabled"),
        # Bière
        "beer_name": beer_name,
        "keg_inserted_at": keg_inserted_at,
        # Réglages
        "mode": setting.get("mode"),
        "settings_id": setting.get("id"),
        # Fidélité
        "loyalty_points": rewards_data.get("availablePoints"),
        "tier": tier_data.get("band"),
    }


def _persist_tokens(
    hass: HomeAssistant, entry: ConfigEntry, client: PerfectDraftClient
) -> None:
    """Mettre à jour uniquement les tokens (après refresh)."""
    hass.config_entries.async_update_entry(
        entry,
        data={
            **entry.data,
            STORE_ACCESS_TOKEN: client.access_token,
            STORE_REFRESH_TOKEN: client.refresh_token,
            STORE_TOKEN_EXPIRY: client.token_expiry,
        },
    )


def _extract_id(iri: str) -> int | None:
    """Extraire l'ID numérique depuis une IRI : '/api/products/29775' → 29775."""
    try:
        return int(iri.rstrip("/").rsplit("/", 1)[-1])
    except (ValueError, AttributeError):
        return None
