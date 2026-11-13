"""Bounded KW (VS1) transactions over a local Optolink serial adapter."""

from asyncio import IncompleteReadError
from contextlib import contextmanager
import math
import os
import time

import serialx

from .profile import BY_KEY, IDENTITY, POINTS, applicable, supported_value, upper_limit

SERIAL_DIRECTORIES = ("/dev/serial/by-id", "/dev/serial/by-path")


def valid_port(path):
    """Accept a single device name under a stable Linux serial directory."""
    directory, name = os.path.split(path)
    return directory in SERIAL_DIRECTORIES and name not in ("", ".", "..") and "\x00" not in name


class OptolinkError(Exception):
    """An Optolink exchange could not be completed."""


class UnsupportedController(OptolinkError):
    """This controller does not match the installed register profile."""


class InvalidSetting(OptolinkError):
    """The current controller configuration does not allow this value."""


class Session:
    def __init__(self, port):
        self.port = port
        self.synchronized = False

    def synchronize(self):
        self.port.reset_read_buffer()
        until = time.monotonic() + 6
        while time.monotonic() < until:
            if self.port.read(1) == b"\x05":
                return
        raise OptolinkError("No KW synchronization byte on the serial port")

    def exchange(self, request, size):
        prefix = b""
        if not self.synchronized:
            self.synchronize()
            prefix = b"\x01"
        self.synchronized = False
        frame = prefix + request
        if self.port.write(frame) != len(frame):
            raise OptolinkError("Incomplete serial transmission")
        try:
            reply = self.port.readexactly(size)
        except IncompleteReadError as err:
            raise OptolinkError(f"Incomplete KW reply ({len(err.partial)}/{size} bytes)") from err
        self.synchronized = True
        return reply

    def read(self, address, size):
        frame = bytes((0xF7, address >> 8, address & 255, size))
        try:
            return self.exchange(frame, size)
        except OptolinkError:
            # Read requests have no side effects. Reacquire a fresh 05 window.
            self.synchronized = False
            return self.exchange(frame, size)

    def identify(self):
        identity = self.read(0x00F8, 4)
        if identity != IDENTITY:
            raise UnsupportedController(f"Unsupported controller ID {identity.hex(' ')}")
        return identity

    def snapshot(self):
        values = {}
        for point in POINTS:
            payload = self.read(point.address, point.length)
            values[point.key] = int.from_bytes(payload, "little", signed=point.signed)
        return values

    def write_setting(self, key, requested):
        point = BY_KEY[key]
        if point.platform not in ("number", "select"):
            raise InvalidSetting(f"{key} is read-only")
        # Read the dependencies from the controller in this same exclusive session.
        values = self.snapshot()
        if not applicable(point, values) or not supported_value(point, values[key]):
            raise InvalidSetting(f"{key} is unavailable in this configuration")
        if point.choices:
            options = {name: code for code, name in point.choices.items()}
            if requested not in options:
                raise InvalidSetting(f"Unknown {key} option")
            raw = options[requested]
        else:
            high = upper_limit(point, values)
            if high is None or not isinstance(requested, (int, float)) or not math.isfinite(requested):
                raise InvalidSetting(f"No valid range or value for {key}")
            scaled = requested / point.factor
            if not scaled.is_integer() or not point.limits[0] <= scaled <= high:
                raise InvalidSetting(f"{key} is outside its current range or step")
            raw = int(scaled)

        if values[key] == raw:
            return values
        address = point.address
        # Each supported writable setting occupies one byte. Never replay F4,
        # even if the controller accepted a write but its ACK was lost.
        try:
            ack = self.exchange(bytes((0xF4, address >> 8, address & 255, 1, raw)), 1)
        except (OSError, serialx.SerialException, OptolinkError) as err:
            raise OptolinkError(f"No write acknowledgement for {key}, check the next reading") from err
        if ack != b"\x00":
            raise OptolinkError(f"{key}: controller rejected the write (0x{ack.hex()})")
        values = self.snapshot()
        if values[key] != raw:
            raise OptolinkError(f"{key}: read-back differs from the requested value")
        return values


class Optolink:
    def __init__(self, path):
        self.path = path

    @contextmanager
    def session(self):
        if not valid_port(self.path):
            raise OptolinkError("Choose a stable /dev/serial/by-id or by-path device")
        try:
            with serialx.serial_for_url(
                self.path, baudrate=4800, byte_size=8, parity=serialx.Parity.EVEN,
                stopbits=serialx.StopBits.TWO, read_timeout=0.55, write_timeout=0.55,
                exclusive=True,
            ) as port:
                session = Session(port)
                session.identify()
                yield session
        except (OSError, serialx.SerialException) as err:
            raise OptolinkError(f"Could not communicate with {self.path}: {err}") from err

    def probe(self):
        with self.session():
            pass

    def read(self):
        with self.session() as session:
            return session.snapshot()

    def set_value(self, key, value):
        with self.session() as session:
            return session.write_setting(key, value)
