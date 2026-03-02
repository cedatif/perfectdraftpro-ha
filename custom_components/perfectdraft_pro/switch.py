"""Switch platform for PerfectDraft Pro — mode boost."""
from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import PerfectDraftCoordinator
from .const import DOMAIN
from .perfectdraft_api import PerfectDraftApiError

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up PerfectDraft Pro switch entities from a config entry."""
    coordinator: PerfectDraftCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([PerfectDraftBoostSwitch(coordinator)])


class PerfectDraftBoostSwitch(CoordinatorEntity[PerfectDraftCoordinator], SwitchEntity):
    """Interrupteur pour le mode boost de la tireuse."""

    _attr_has_entity_name = True
    _attr_name = "Mode boost"
    _attr_icon = "mdi:rocket-launch"

    def __init__(self, coordinator: PerfectDraftCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_boost"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.entry_id)},
            name="PerfectDraft Pro",
            manufacturer="AB InBev",
            model="PerfectDraft Pro",
        )

    @property
    def is_on(self) -> bool | None:
        if self.coordinator.data is None:
            return None
        v = self.coordinator.data.get("boost")
        return bool(v) if v is not None else None

    async def async_turn_on(self, **kwargs) -> None:
        await self._set_boost(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._set_boost(False)

    async def _set_boost(self, value: bool) -> None:
        if not self.coordinator.data:
            return
        settings_id = self.coordinator.data.get("settings_id")
        if not settings_id:
            _LOGGER.error("settings_id non disponible, impossible de changer le mode boost")
            return
        try:
            await self.coordinator.client.set_machine_settings(
                settings_id, boost=value
            )
            await self.coordinator.async_request_refresh()
        except PerfectDraftApiError as err:
            _LOGGER.error("Erreur lors du changement du mode boost : %s", err)
