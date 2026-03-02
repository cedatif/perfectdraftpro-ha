"""Binary sensor platform for PerfectDraft Pro."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import PerfectDraftCoordinator
from .const import DOMAIN


@dataclass(frozen=True, kw_only=True)
class PerfectDraftBinarySensorDescription(BinarySensorEntityDescription):
    """Description d'un capteur binaire PerfectDraft Pro."""


BINARY_SENSORS: tuple[PerfectDraftBinarySensorDescription, ...] = (
    PerfectDraftBinarySensorDescription(
        key="door_closed",
        name="Porte fermée",
        device_class=BinarySensorDeviceClass.DOOR,
        icon="mdi:door",
    ),
    PerfectDraftBinarySensorDescription(
        key="connected",
        name="Connectée au cloud",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        icon="mdi:cloud-check",
    ),
    PerfectDraftBinarySensorDescription(
        key="eco_mode",
        name="Mode éco",
        icon="mdi:leaf",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up PerfectDraft Pro binary sensors from a config entry."""
    coordinator: PerfectDraftCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        PerfectDraftBinarySensor(coordinator, description)
        for description in BINARY_SENSORS
    )


class PerfectDraftBinarySensor(
    CoordinatorEntity[PerfectDraftCoordinator], BinarySensorEntity
):
    """Représentation d'un capteur binaire PerfectDraft Pro."""

    entity_description: PerfectDraftBinarySensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PerfectDraftCoordinator,
        description: PerfectDraftBinarySensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{description.key}"
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
        value = self.coordinator.data.get(self.entity_description.key)
        if value is None:
            return None
        return bool(value)
