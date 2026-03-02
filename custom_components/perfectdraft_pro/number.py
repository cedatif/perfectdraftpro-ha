"""Number platform for PerfectDraft Pro — température cible."""
from __future__ import annotations

import logging

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
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
    """Set up PerfectDraft Pro number entities from a config entry."""
    coordinator: PerfectDraftCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([PerfectDraftTemperatureNumber(coordinator)])


class PerfectDraftTemperatureNumber(
    CoordinatorEntity[PerfectDraftCoordinator], NumberEntity
):
    """Contrôle de la température cible de la tireuse."""

    _attr_has_entity_name = True
    _attr_name = "Température cible"
    _attr_icon = "mdi:thermometer-chevron-up"
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_mode = NumberMode.BOX
    _attr_native_step = 1.0

    def __init__(self, coordinator: PerfectDraftCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_target_temperature"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.entry_id)},
            name="PerfectDraft Pro",
            manufacturer="AB InBev",
            model="PerfectDraft Pro",
        )

    @property
    def native_value(self) -> float | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("target_temperature")

    @property
    def native_min_value(self) -> float:
        if self.coordinator.data:
            v = self.coordinator.data.get("temp_min")
            if v is not None:
                return float(v)
        return 0.0

    @property
    def native_max_value(self) -> float:
        if self.coordinator.data:
            v = self.coordinator.data.get("temp_max")
            if v is not None:
                return float(v)
        return 12.0

    async def async_set_native_value(self, value: float) -> None:
        if not self.coordinator.data:
            return
        settings_id = self.coordinator.data.get("settings_id")
        if not settings_id:
            _LOGGER.error("settings_id non disponible, impossible de régler la température")
            return
        try:
            await self.coordinator.client.set_machine_settings(
                settings_id, temperature=int(value)
            )
            await self.coordinator.async_request_refresh()
        except PerfectDraftApiError as err:
            _LOGGER.error("Erreur lors du réglage de la température : %s", err)
