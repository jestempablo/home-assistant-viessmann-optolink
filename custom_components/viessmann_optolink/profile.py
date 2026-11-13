"""Optolink KW registers for the V100KC2 profile of the Vitotronic 100."""

from dataclasses import dataclass

DOMAIN = "viessmann_optolink"
TITLE = "Vitotronic 100"
IDENTITY = bytes.fromhex("20 91 00 01")


@dataclass(frozen=True)
class Point:
    key: str
    address: int
    platform: str
    length: int = 1
    factor: float = 1
    unit: str | None = None
    limits: tuple[int, int] | None = None  # Raw, whole register units
    choices: dict[int, str] | None = None
    service: bool = False
    two_stage: bool = False
    dhw: bool = False
    signed: bool = False


def number(key, address, low, high, unit=None, *, factor=1, service=True, **features):
    return Point(key, address, "number", unit=unit, limits=(low, high), factor=factor,
                 service=service, **features)


def select(key, address, choices, *, service=True, **features):
    return Point(key, address, "select", choices=choices, service=service, **features)


# Operation, commissioning and coding tables. A read-only point never has a
# write opcode. Codes 03, 13 and 92 have explicit restrictions in the manual.
POINTS = (
    select("operating_mode", 0x2301, {0: "dhw_only", 4: "heating_and_dhw", 5: "standby"}, service=False),
    number("boiler_setpoint", 0x5300, 0, 127, "°C", service=False),
    number("dhw_setpoint", 0x6300, 10, 95, "°C", service=False, dhw=True),
    select("system_layout", 0x7700, {1: "heating", 2: "heating_and_cylinder"}),
    select("burner_control", 0x7701, {0: "thermostat_burner", 1: "thermostat_burner_and_pump", 2: "external_burner"}),
    select("burner_type", 0x5702, {0: "single_stage", 1: "two_stage"}),
    Point("fuel", 0x5703, "sensor", choices={0: "gas", 1: "oil", 2: "undefined"}, service=True),
    select("hysteresis", 0x5704, {0: "standard", 1: "erb50", 2: "erb80"}),
    number("boiler_limit", 0x5706, 20, 127, "°C"),
    number("heating_integral", 0x5710, 0, 199, "K·s", factor=128, two_stage=True),
    number("cylinder_integral", 0x5711, 0, 199, "K·s", factor=128, two_stage=True, dhw=True),
    number("off_integral", 0x5712, 0, 199, "K·s", factor=128, two_stage=True),
    Point("cutoff_differential", 0x5713, "sensor", unit="K", service=True),
    number("burner_motor_time", 0x5715, 7, 180, "s", two_stage=True),
    select("interval_ignition", 0x5728, {0: "disabled", 1: "every_five_hours"}),
    select("dhw_algorithm", 0x6755, {0: "standard", 1: "adaptive"}, dhw=True),
    select("dhw_range", 0x6756, {0: "standard_60", 1: "extended_95"}, dhw=True),
    number("dhw_setpoint_2", 0x6758, 0, 95, "°C", dhw=True),
    number("dhw_offset", 0x6760, 10, 50, "K", dhw=True),
    select("cylinder_pump_start", 0x6761, {0: "temperature_dependent", 1: "immediate"}, dhw=True),
    number("cylinder_pump_overrun", 0x6762, 0, 15, "min", dhw=True),
    select("extra_dhw_frequency", 0x6763,
           {0: "never", 1: "daily", **{n: f"every_{n}_days" for n in range(2, 15)}, 15: "twice_daily"}, dhw=True),
    number("fault_delay", 0x7780, 0, 199, "s", factor=5),
    select("temperature_display", 0x7788, {0: "celsius", 1: "fahrenheit"}),
    select("coding_display", 0x778A, {175: "applicable", 176: "all_codes"}),
    Point("safety_module", 0x7792, "sensor", choices={0: "absent", 1: "installed"}, service=True),
    select("dhw_priority", 0x27A2, {0: "no_priority", 2: "cylinder_priority"}, dhw=True),
    number("heating_pump_overrun", 0x57F5, 0, 20, "min"),
    select("summer_pump", 0x57F6, {0: "off", **{n: f"cycles_{n}" for n in range(1, 25)}, 25: "continuous"}),
    select("standby_pump", 0x57F7, {0: "off", **{n: f"cycles_{n}" for n in range(1, 25)}, 25: "continuous"}),
    Point("boiler_temperature", 0x0802, "sensor", 2, 0.1, "°C", signed=True),
    Point("cylinder_temperature", 0x0804, "sensor", 2, 0.1, "°C", dhw=True, signed=True),
    Point("boiler_target", 0x5502, "sensor", 2, 0.1, "°C"),
    Point("cylinder_target", 0x6500, "sensor", 2, 0.1, "°C", dhw=True),
    Point("burner", 0x0842, "binary_sensor"),
    Point("burner_stage_2", 0x0849, "binary_sensor", two_stage=True),
    Point("cylinder_pump", 0x0845, "binary_sensor", dhw=True),
    Point("heating_pump", 0x0843, "binary_sensor"),
    Point("thermostat_input", 0x0884, "binary_sensor"),
    Point("burner_fault", 0x0883, "binary_sensor"),
    Point("dhw_phase", 0x650A, "sensor", choices={0: "idle", 1: "heating", 2: "overrun"}, dhw=True),
    Point("burner_starts", 0x088A, "sensor", 4),
    Point("burner_hours", 0x08A7, "sensor", 4, 1 / 3600, "h"),
)
BY_KEY = {point.key: point for point in POINTS}


def supported_value(point, value):
    if value is None:
        return False
    if point.choices is not None:
        return value in point.choices
    if point.limits:
        return point.limits[0] <= value <= point.limits[1]
    if point.platform == "binary_sensor":
        return value in (0, 1)
    if point.unit == "°C":
        return 0 <= value <= 1500
    return value != (1 << (8 * point.length)) - 1


def applicable(point, values):
    return ((not point.two_stage or values.get("burner_type") == 1)
            and (not point.dhw or values.get("system_layout") == 2))


def upper_limit(point, values):
    high = point.limits[1]
    if point.key == "boiler_setpoint":
        limit = values.get("boiler_limit")
        return min(high, limit) if supported_value(BY_KEY["boiler_limit"], limit) else None
    if point.key in ("dhw_setpoint", "dhw_setpoint_2"):
        return {0: 60, 1: 95}.get(values.get("dhw_range"))
    return high
