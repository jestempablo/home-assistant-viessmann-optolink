"""Adjustable numeric settings, bounded by the current controller coding."""

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.const import EntityCategory

from .coordinator import VitotronicEntity
from .profile import POINTS, upper_limit


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(VitotronicNumber(entry.runtime_data, p) for p in POINTS if p.platform == "number")


class VitotronicNumber(VitotronicEntity, NumberEntity):
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator, point):
        super().__init__(coordinator, point)
        self._attr_native_step = point.factor
        self._attr_native_unit_of_measurement = point.unit
        self._attr_native_min_value = point.limits[0] * point.factor
        if point.unit == "°C":
            self._attr_device_class = NumberDeviceClass.TEMPERATURE
        if point.service:
            self._attr_entity_category = EntityCategory.CONFIG

    @property
    def available(self):
        return super().available and upper_limit(self.point, self.coordinator.data) is not None

    @property
    def native_max_value(self):
        maximum = upper_limit(self.point, self.coordinator.data)
        if maximum is None:
            return self.native_min_value
        return maximum * self.point.factor

    @property
    def native_value(self):
        return None if self.raw is None else self.raw * self.point.factor

    async def async_set_native_value(self, value):
        await self.coordinator.async_set_value(self.point.key, value)
