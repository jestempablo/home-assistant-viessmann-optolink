"""Temperatures, counters and read-only operating data."""

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import EntityCategory

from .coordinator import VitotronicEntity
from .profile import POINTS


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(VitotronicSensor(entry.runtime_data, p) for p in POINTS if p.platform == "sensor")


class VitotronicSensor(VitotronicEntity, SensorEntity):
    def __init__(self, coordinator, point):
        super().__init__(coordinator, point)
        self._attr_native_unit_of_measurement = point.unit
        if point.service:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        if point.choices:
            self._attr_device_class = SensorDeviceClass.ENUM
            self._attr_options = list(point.choices.values())
        elif point.unit == "°C":
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
            self._attr_state_class = SensorStateClass.MEASUREMENT
            self._attr_suggested_display_precision = 1
        elif point.key in ("burner_starts", "burner_hours"):
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
            if point.unit == "h":
                self._attr_device_class = SensorDeviceClass.DURATION
                self._attr_suggested_display_precision = 1

    @property
    def native_value(self):
        if self.raw is None:
            return None
        if self.point.choices:
            return self.point.choices.get(self.raw)
        return round(self.raw * self.point.factor, 4)
