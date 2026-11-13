"""Exercise the production KW frames and the full HA config entry against a fake Vitotronic."""

import asyncio
import json
import os
from pathlib import Path
import select
import shutil
import tempfile
import threading
import time
import tty
import unittest
from unittest.mock import patch

import serialx

from custom_components.viessmann_optolink.profile import BY_KEY, IDENTITY, POINTS
from custom_components.viessmann_optolink.protocol import InvalidSetting, Optolink, OptolinkError, UnsupportedController


TEST_PORT = "/dev/serial/by-id/test-optolink"


class BoilerPort:
    def __init__(self):
        self.frames = []
        self.values = {p.address: (p.limits[0] if p.limits else next(iter(p.choices)) if p.choices else 0)
                       for p in POINTS}
        self.values.update({0x7700: 2, 0x5706: 85, 0x5300: 60, 0x6300: 60,
                            0x0802: 395, 0x0804: 640, 0x2301: 4, 0x778A: 175})
        self.identity = IDENTITY
        self.pending = b""
        self.drop_ack = False
        self.ignore_write = False
        self.opens = 0

    def open(self, *args, **kwargs):
        assert (kwargs["baudrate"], kwargs["byte_size"], kwargs["parity"], kwargs["stopbits"]) == (
            4800, 8, serialx.Parity.EVEN, serialx.StopBits.TWO
        )
        assert kwargs["read_timeout"] == kwargs["write_timeout"] == 0.55
        assert kwargs["exclusive"]
        self.opens += 1
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def reset_read_buffer(self):
        self.pending = b"\x05"
        self.first = True

    def read(self, size):
        reply = self.pending[:size]
        self.pending = self.pending[size:]
        return reply

    def readexactly(self, size):
        reply = self.read(size)
        if len(reply) != size:
            raise asyncio.IncompleteReadError(reply, size)
        return reply

    def write(self, frame):
        self.frames.append(frame)
        if self.first:
            assert frame.startswith(b"\x01")
            frame = frame[1:]
            self.first = False
        op, hi, lo, length = frame[:4]
        addr = (hi << 8) + lo
        if op == 0xF7:
            assert len(frame) == 4
            self.pending = self.identity if addr == 0x00F8 else self.values[addr].to_bytes(length, "little")
        else:
            assert op == 0xF4 and len(frame) == 5 and length == 1
            if not self.ignore_write:
                self.values[addr] = frame[4]
            self.pending = b"" if self.drop_ack else b"\x00"
        return len(self.frames[-1])

    def writes(self):
        return [frame for frame in self.frames if frame.lstrip(b"\x01").startswith(b"\xf4")]


class TestOptolink(unittest.TestCase):
    def setUp(self):
        self.boiler = BoilerPort()
        self.client = Optolink(TEST_PORT)
        self.addCleanup(patch.stopall)
        patch("serialx.serial_for_url", side_effect=self.boiler.open).start()

    def test_snapshot_heating_mode_and_identity(self):
        data = self.client.read()
        self.assertEqual((data["boiler_temperature"], data["operating_mode"]), (395, 4))
        self.assertEqual(self.boiler.frames[0], bytes.fromhex("01 f7 00 f8 04"))
        self.assertEqual(self.boiler.writes(), [])

    def test_incomplete_read_reacquires_sync(self):
        with patch.object(self.boiler, "readexactly", side_effect=[
            asyncio.IncompleteReadError(b"\x20", 4), IDENTITY,
        ]):
            self.client.probe()
        self.assertEqual(self.boiler.frames, [bytes.fromhex("01 f7 00 f8 04")] * 2)

    def test_invalid_paths_do_not_open_a_device(self):
        for path in ("", "/dev/ttyUSB0", "socket://example.org:80", "/dev/serial/by-id/..",
                     "/dev/serial/by-id/../../tty0", "/dev/serial/by-id/bad\x00name"):
            with self.subTest(path=path), self.assertRaises(OptolinkError):
                Optolink(path).probe()
        self.assertEqual(self.boiler.opens, 0)

    def test_wrong_controller_cannot_receive_writes(self):
        self.boiler.identity = bytes.fromhex("20 98 00 01")
        with self.assertRaises(UnsupportedController):
            self.client.set_value("dhw_setpoint", 55)
        self.assertEqual(len(self.boiler.frames), 1)
        self.assertFalse(self.boiler.writes())

    def test_fresh_limits_and_stage(self):
        for key, value in (("dhw_setpoint", 61), ("boiler_setpoint", 86), ("heating_integral", 128),
                           ("fault_delay", 6), ("fault_delay", float("nan")), ("fuel", "oil"),
                           ("dhw_priority", "unsupported")):
            with self.subTest(key=key), self.assertRaises(InvalidSetting):
                self.client.set_value(key, value)
        self.assertFalse(self.boiler.writes())
        self.boiler.values[0x6756] = 1
        self.assertEqual(self.client.set_value("dhw_setpoint", 61)["dhw_setpoint"], 61)
        self.assertEqual(self.boiler.writes(), [bytes.fromhex("f4 63 00 01 3d")])

    def test_readback_noop_and_no_write_replay(self):
        self.client.set_value("boiler_setpoint", 60)
        self.assertFalse(self.boiler.writes())
        self.boiler.ignore_write = True
        with self.assertRaisesRegex(OptolinkError, "read-back"):
            self.client.set_value("coding_display", "all_codes")
        self.boiler.ignore_write = False
        self.boiler.drop_ack = True
        with self.assertRaisesRegex(OptolinkError, "acknowledgement"):
            self.client.set_value("coding_display", "all_codes")
        self.assertEqual(len(self.boiler.writes()), 2)
        self.assertEqual(self.client.read()["coding_display"], 176)

    def test_translations_cover_every_entity_and_option(self):
        root = Path(__file__).resolve().parents[1] / "custom_components/viessmann_optolink"
        for name in ("en", "pl"):
            catalog = json.loads((root / "translations" / f"{name}.json").read_text())["entity"]
            for point in POINTS:
                item = catalog[point.platform][point.key]
                self.assertTrue(item["name"])
                self.assertEqual(set(item.get("state", {})), set((point.choices or {}).values()))
        self.assertEqual(len(BY_KEY), len({p.address for p in POINTS}))


@unittest.skipUnless(os.name == "posix", "requires a pseudo-terminal")
class SerialTransportTest(unittest.TestCase):
    def test_real_serial_driver_receives_fragmented_identity(self):
        # Map only the path to a PTY. The driver, serial options and KW session are real.
        master, slave = os.openpty()
        self.addCleanup(os.close, slave)
        self.addCleanup(os.close, master)
        controller_path = os.ttyname(slave)
        open_port = serialx.serial_for_url
        stop = threading.Event()
        requests = []

        def controller():
            received = b""
            while not stop.is_set():
                if not received:
                    os.write(master, b"\x05")
                if not select.select([master], [], [], 0.05)[0]:
                    continue
                received += os.read(master, 5 - len(received))
                if len(received) == 5:
                    requests.append(received)
                    for byte in IDENTITY:
                        os.write(master, bytes([byte]))
                        time.sleep(0.015)
                    return

        def open_test_port(path, **kwargs):
            self.assertEqual(path, TEST_PORT)
            return open_port(controller_path, **kwargs)

        # Opening once sets the PTY to raw mode before the controller sends its beacon.
        tty.setraw(slave)
        worker = threading.Thread(target=controller, daemon=True)
        worker.start()
        try:
            with patch("serialx.serial_for_url", side_effect=open_test_port):
                Optolink(TEST_PORT).probe()
        finally:
            stop.set()
            worker.join(timeout=2)
        self.assertEqual(requests, [bytes.fromhex("01 f7 00 f8 04")])


class HomeAssistantEntryTest(unittest.TestCase):
    def test_flow_device_services_and_reload(self):
        from homeassistant import bootstrap, loader
        from homeassistant.core import HomeAssistant
        from homeassistant.helpers import device_registry as dr, entity_registry as er

        async def scenario(directory, boiler):
            hass = HomeAssistant(directory)
            loader.async_setup(hass)
            hass.config.skip_pip = True
            try:
                await bootstrap.async_from_config_dict({"homeassistant": {"name": "Optolink test",
                    "latitude": 50.0, "longitude": 19.0, "elevation": 100, "unit_system": "metric",
                    "time_zone": "Europe/Warsaw", "country": "PL"}}, hass)
                form = await hass.config_entries.flow.async_init("viessmann_optolink", context={"source": "user"})
                self.assertEqual(form["type"], "form")
                self.assertEqual(boiler.opens, 0)
                invalid = await hass.config_entries.flow.async_configure(form["flow_id"], {"port": "/dev/ttyUSB0"})
                self.assertEqual(invalid["errors"], {"port": "invalid_port"})
                self.assertEqual(boiler.opens, 0)
                boiler.identity = bytes.fromhex("20 98 00 01")
                wrong = await hass.config_entries.flow.async_configure(form["flow_id"], {"port": TEST_PORT})
                self.assertEqual(wrong["errors"], {"base": "unsupported_controller"})
                self.assertFalse(boiler.writes())
                boiler.identity = IDENTITY
                done = await hass.config_entries.flow.async_configure(form["flow_id"], {"port": TEST_PORT})
                self.assertEqual(done["type"], "create_entry")
                await hass.async_block_till_done()
                entry = done["result"]
                self.assertEqual(entry.state.value, "loaded")
                devices = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
                self.assertEqual(len(devices), 1)
                entities = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
                self.assertEqual(len(entities), len(POINTS))
                self.assertEqual({e.device_id for e in entities}, {devices[0].id})
                by_key = {e.unique_id.removeprefix(entry.entry_id + "_"): e.entity_id for e in entities}
                self.assertEqual(hass.states.get(by_key["operating_mode"]).state, "heating_and_dhw")
                self.assertEqual(float(hass.states.get(by_key["boiler_temperature"]).state), 39.5)
                await hass.services.async_call("number", "set_value", {
                    "entity_id": by_key["dhw_setpoint"], "value": 55}, blocking=True)
                self.assertEqual(boiler.values[0x6300], 55)
                await hass.services.async_call("select", "select_option", {
                    "entity_id": by_key["operating_mode"], "option": "dhw_only"}, blocking=True)
                self.assertEqual(boiler.values[0x2301], 0)
                registry = er.async_get(hass)
                self.assertEqual(registry.async_get(by_key["coding_display"]).disabled_by,
                                 er.RegistryEntryDisabler.INTEGRATION)
                self.assertIsNone(registry.async_get(by_key["fuel"]).disabled_by)
                # Mimic an existing installation with an enabled service-code entity.
                registry.async_update_entity(by_key["coding_display"], disabled_by=None)
                from custom_components.viessmann_optolink.diagnostics import async_get_config_entry_diagnostics
                info = await async_get_config_entry_diagnostics(hass, entry)
                self.assertIn("burner_stage_2", info["inapplicable_points"])
                self.assertNotIn(TEST_PORT, json.dumps(info))
                original = {e.entity_id for e in entities}
                old_device_id = devices[0].id
                other_path = "/dev/serial/by-path/test-optolink"
                reconfigure = await hass.config_entries.flow.async_init("viessmann_optolink", context={
                    "source": "reconfigure", "entry_id": entry.entry_id,
                })
                result = await hass.config_entries.flow.async_configure(reconfigure["flow_id"], {"port": other_path})
                self.assertEqual(result["reason"], "reconfigure_successful")
                await hass.async_block_till_done()
                self.assertEqual({e.entity_id for e in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)}, original)
                self.assertEqual([device.id for device in dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)], [old_device_id])
                self.assertEqual((entry.state.value, entry.unique_id, entry.data["port"]), ("loaded", other_path, other_path))
                self.assertIsNone(registry.async_get(by_key["coding_display"]).disabled_by)
                self.assertEqual(hass.states.get(by_key["coding_display"]).state, "applicable")
                old_port = await hass.config_entries.flow.async_init("viessmann_optolink", context={"source": "user"})
                self.assertEqual(old_port["reason"], "single_instance_allowed")
            finally:
                await hass.async_stop()

        with tempfile.TemporaryDirectory() as directory:
            root = Path(__file__).resolve().parents[1]
            shutil.copytree(root / "custom_components" / "viessmann_optolink",
                            Path(directory) / "custom_components" / "viessmann_optolink")
            boiler = BoilerPort()
            with patch("serialx.serial_for_url", side_effect=boiler.open):
                asyncio.run(scenario(directory, boiler))
