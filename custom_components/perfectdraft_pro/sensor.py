"""Sensor platform for PerfectDraft Pro."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfPressure, UnitOfTemperature, UnitOfTime, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import PerfectDraftCoordinator
from .const import DOMAIN


@dataclass(frozen=True, kw_only=True)
class PerfectDraftSensorDescription(SensorEntityDescription):
    """Description d'un capteur PerfectDraft Pro."""


SENSORS: tuple[PerfectDraftSensorDescription, ...] = (
    PerfectDraftSensorDescription(
        key="temperature",
        name="Température bière",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:thermometer",
    ),
    PerfectDraftSensorDescription(
        key="time_to_temp",
        name="Temps de refroidissement",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:timer-sand",
    ),
    PerfectDraftSensorDescription(
        key="keg_volume",
        name="Volume fût restant",
        native_unit_of_measurement=UnitOfVolume.LITERS,
        device_class=SensorDeviceClass.VOLUME,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:beer",
    ),
    PerfectDraftSensorDescription(
        key="keg_pressure",
        name="Pression fût",
        native_unit_of_measurement=UnitOfPressure.KPA,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:gauge",
    ),
    PerfectDraftSensorDescription(
        key="last_pour_volume",
        name="Volume dernier verre",
        native_unit_of_measurement=UnitOfVolume.LITERS,
        device_class=SensorDeviceClass.VOLUME,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:cup",
    ),
    PerfectDraftSensorDescription(
        key="last_pour_duration",
        name="Durée dernier verre",
        native_unit_of_measurement="ms",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:timer-outline",
    ),
    PerfectDraftSensorDescription(
        key="pours_since_startup",
        name="Verres servis",
        native_unit_of_measurement="verres",
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:counter",
    ),
    PerfectDraftSensorDescription(
        key="error_codes",
        name="Codes d'erreur",
        icon="mdi:alert-circle-outline",
    ),
    PerfectDraftSensorDescription(
        key="firmware_version",
        name="Version firmware",
        icon="mdi:chip",
    ),
    PerfectDraftSensorDescription(
        key="beer_name",
        name="Bière en cours",
        icon="mdi:beer-outline",
    ),
    PerfectDraftSensorDescription(
        key="keg_inserted_at",
        name="Fût inséré le",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:calendar-clock",
    ),
    PerfectDraftSensorDescription(
        key="keg_type",
        name="Type de fût",
        icon="mdi:barrel",
    ),
    PerfectDraftSensorDescription(
        key="mode",
        name="Mode de fonctionnement",
        icon="mdi:cog-outline",
    ),
    PerfectDraftSensorDescription(
        key="loyalty_points",
        name="Points fidélité",
        native_unit_of_measurement="points",
        state_class=SensorStateClass.TOTAL,
        icon="mdi:star-circle",
    ),
    PerfectDraftSensorDescription(
        key="tier",
        name="Niveau fidélité",
        icon="mdi:trophy-outline",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up PerfectDraft Pro sensors from a config entry."""
    coordinator: PerfectDraftCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        PerfectDraftSensor(coordinator, description) for description in SENSORS
    )


class PerfectDraftSensor(CoordinatorEntity[PerfectDraftCoordinator], SensorEntity):
    """Représentation d'un capteur PerfectDraft Pro."""

    entity_description: PerfectDraftSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PerfectDraftCoordinator,
        description: PerfectDraftSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{description.key}"
        data = coordinator.data or {}
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.entry_id)},
            name="PerfectDraft Pro",
            manufacturer="AB InBev",
            model="PerfectDraft Pro",
            sw_version=data.get("firmware_version"),
            serial_number=data.get("serial_number"),
        )

    @property
    def native_value(self) -> Any:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self.entity_description.key)
