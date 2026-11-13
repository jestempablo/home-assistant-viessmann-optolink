"""Report model compatibility and unreadable registers without installation data."""

from .profile import IDENTITY, POINTS, applicable, supported_value


async def async_get_config_entry_diagnostics(hass, entry):
    coordinator = entry.runtime_data
    data = coordinator.data or {}
    return {
        "profile": "V100KC2",
        "supported_signature": IDENTITY.hex(" "),
        "last_poll_successful": coordinator.last_update_success,
        "poll_interval_seconds": coordinator.update_interval.total_seconds(),
        "unsupported_values": [
            point.key for point in POINTS
            if applicable(point, data) and not supported_value(point, data.get(point.key))
        ],
        "inapplicable_points": [point.key for point in POINTS if not applicable(point, data)],
    }
