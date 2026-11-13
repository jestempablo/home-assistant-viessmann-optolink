"""Configure a local Optolink adapter chosen by the user."""

from pathlib import Path

import probatio
from homeassistant import config_entries
from homeassistant.const import CONF_PORT
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig, SelectSelectorMode

from .profile import DOMAIN, TITLE
from .protocol import SERIAL_DIRECTORIES, Optolink, OptolinkError, UnsupportedController, valid_port


def _port_choices():
    """List stable device paths without opening a port."""
    return sorted(str(path) for directory in SERIAL_DIRECTORIES for path in Path(directory).glob("*"))


class OptolinkConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        return await self._async_port("user", user_input)

    async def async_step_reconfigure(self, user_input=None):
        return await self._async_port("reconfigure", user_input, self._get_reconfigure_entry())

    async def _async_port(self, step, user_input, entry=None):
        errors = {}
        path = entry.data[CONF_PORT] if entry else None
        if user_input is not None:
            path = user_input[CONF_PORT].strip()
            if not valid_port(path):
                errors[CONF_PORT] = "invalid_port"
            else:
                if entry is None:
                    self._async_abort_entries_match({CONF_PORT: path})
                try:
                    probe = Optolink(path).probe
                    if entry is not None and hasattr(entry, "runtime_data"):
                        async with entry.runtime_data.lock:
                            await self.hass.async_add_executor_job(probe)
                    else:
                        await self.hass.async_add_executor_job(probe)
                except UnsupportedController:
                    errors["base"] = "unsupported_controller"
                except OptolinkError:
                    errors["base"] = "cannot_connect"
                else:
                    data = {CONF_PORT: path}
                    if entry is not None:
                        return self.async_update_reload_and_abort(entry, unique_id=path, data_updates=data)
                    await self.async_set_unique_id(path)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(title=TITLE, data=data)

        ports = await self.hass.async_add_executor_job(_port_choices)
        if path and path not in ports:
            ports.append(path)
        port_field = probatio.Required(CONF_PORT, default=path) if path else probatio.Required(CONF_PORT)
        return self.async_show_form(
            step_id=step,
            data_schema=probatio.Schema({port_field: SelectSelector(SelectSelectorConfig(
                options=ports, custom_value=True, mode=SelectSelectorMode.DROPDOWN,
            ))}),
            errors=errors,
        )
