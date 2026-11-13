"""Controller inputs and outputs, independent of the HA heating automations."""

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.const import EntityCategory

from .coordinator import VitotronicEntity
from .profile import POINTS


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(VitotronicBinary(entry.runtime_data, p) for p in POINTS if p.platform == "binary_sensor")


class VitotronicBinary(VitotronicEntity, BinarySensorEntity):
    def __init__(self, coordinator, point):
        super().__init__(coordinator, point)
        if point.key == "burner_fault":
            self._attr_device_class = BinarySensorDeviceClass.PROBLEM
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        elif point.key in ("burner", "burner_stage_2"):
            self._attr_icon = "mdi:fire"
        elif point.key in ("heating_pump", "cylinder_pump"):
            self._attr_icon = "mdi:pump"

    @property
    def is_on(self):
        return self.raw == 1
