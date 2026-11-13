"""Shared Optolink polling, verified writes and Home Assistant device identity."""

import asyncio
from datetime import timedelta
import logging

from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator, UpdateFailed

from .profile import DOMAIN, IDENTITY, TITLE, applicable, supported_value
from .protocol import InvalidSetting, Optolink, OptolinkError

_LOGGER = logging.getLogger(__name__)


class VitotronicCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry):
        super().__init__(hass, _LOGGER, name=TITLE, config_entry=entry,
                         update_interval=timedelta(seconds=30), always_update=False)
        self.client = Optolink(entry.data["port"])
        self.lock = asyncio.Lock()
        self.device = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)}, name=TITLE,
                                 manufacturer="Viessmann", model="Vitotronic 100 (V100KC2)",
                                 model_id="2091", hw_version=f"{IDENTITY[2]:02X}",
                                 sw_version=f"{IDENTITY[3]:02X}")

    async def _async_update_data(self):
        async with self.lock:
            try:
                return await self.hass.async_add_executor_job(self.client.read)
            except OptolinkError as err:
                raise UpdateFailed(str(err)) from err

    async def async_set_value(self, key, value):
        async with self.lock:
            try:
                data = await self.hass.async_add_executor_job(self.client.set_value, key, value)
            except InvalidSetting as err:
                raise ServiceValidationError(str(err)) from err
            except OptolinkError as err:
                self.async_set_update_error(UpdateFailed(str(err)))
                raise HomeAssistantError(str(err)) from err
            self.async_set_updated_data(data)


class VitotronicEntity(CoordinatorEntity[VitotronicCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator, point):
        super().__init__(coordinator)
        self.point = point
        self._attr_device_info = coordinator.device
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{point.key}"
        self._attr_translation_key = point.key
        self._attr_entity_registry_enabled_default = not (point.service and point.platform in ("number", "select"))

    @property
    def raw(self):
        return self.coordinator.data.get(self.point.key)

    @property
    def available(self):
        return (super().available and applicable(self.point, self.coordinator.data)
                and supported_value(self.point, self.raw))

    @property
    def extra_state_attributes(self):
        return {"optolink_register": f"0x{self.point.address:04X}"}
