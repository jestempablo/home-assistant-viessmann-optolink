"""Operating mode and enumerated settings from the device's register map."""

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory

from .coordinator import VitotronicEntity
from .profile import POINTS


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(VitotronicSelect(entry.runtime_data, p) for p in POINTS if p.platform == "select")


class VitotronicSelect(VitotronicEntity, SelectEntity):
    def __init__(self, coordinator, point):
        super().__init__(coordinator, point)
        self._attr_options = list(point.choices.values())
        if point.service:
            self._attr_entity_category = EntityCategory.CONFIG

    @property
    def current_option(self):
        return self.point.choices.get(self.raw)

    async def async_select_option(self, option):
        await self.coordinator.async_set_value(self.point.key, option)
