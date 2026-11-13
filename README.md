# Viessmann Optolink for Home Assistant

Read a Viessmann Vitotronic 100 boiler controller over a local USB optical adapter. Home Assistant shows boiler and cylinder temperatures, burner activity and pump outputs. You can change the operating mode and temperature setpoints from the device page. The integration works offline.

[![Open Viessmann Optolink in HACS or Marketplace](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=jestempablo&repository=home-assistant-viessmann-optolink&category=integration)

## Compatibility

| Requirement | Supported configuration |
| --- | --- |
| Controller | Vitotronic 100, profile **V100KC2**, with the four-byte identity **`20 91 00 01`**. Observed on a Vitogas 100 with a Vitotronic 100 panel marked KK2. |
| Connection | A local USB Optolink head aligned with the controller's optical window. The adapter must be visible inside Home Assistant under `/dev/serial/by-id/` or `/dev/serial/by-path/`. For a VM or container, pass the USB device and its stable path through to the guest. |
| Protocol | KW (VS1), 4800 baud, 8 data bits, even parity, 2 stop bits. Each connection verifies the controller identity. Other signatures are rejected before a setting can be written. |
| Home Assistant | 2026.10.0 or newer. One controller per Home Assistant instance. English and Polish user interfaces. |

The profile covers the controller outputs. For example, the heating pump entity reports the boiler's output terminal. A pump connected to an independent relay has its own state.

## Cable and optical port

Use a **USB-to-Optolink data cable with an infrared head**. The replacement cable for Vitoconnect OPTO is **Viessmann part 7856059**. Viessmann specifies a length of **3 m**. Plug the USB end into the machine running Home Assistant, or into the host that passes USB through to its VM. Seat the optical head over the window marked **V** on the Vitotronic front panel. The cable connects directly to Home Assistant and works without a Vitoconnect gateway or a ViCare account. [Viessmann cable specifications](https://www.viessmann.co.uk/en/products/control-system-and-connectivity/vitoconnect.html) · [Spare part 7856059](https://viessmanndirect.co.uk/Catalogue/Spares/Miscellaneous-Spares/Connecting-cable-USB-Optolink-7856059)

## Installation

1. Open the badge above. In Home Assistant 2026.11 or later, you can also open **Settings → Marketplace → Add from link** and paste `https://github.com/jestempablo/home-assistant-viessmann-optolink`. Connect GitHub if prompted. In HACS on Home Assistant 2026.10, use **Custom repositories**, paste the same URL and choose **Integration**.
2. Download **Viessmann Optolink**. Follow any restart prompt. On HACS, restart Home Assistant after installation.
3. Open **Settings → Devices & services → Add integration**, select **Viessmann Optolink**, and choose the adapter or enter its stable path. You can find the port under **Settings → System → Hardware → All hardware**. Setup reads the controller identity through the optical head.
4. Open the **Vitotronic 100** device to see the first readings. To replace the adapter, choose **Reconfigure** on the integration entry and select its new path.

For a manual installation, copy `custom_components/viessmann_optolink` from a release into your configuration's `custom_components` directory, restart Home Assistant and continue at step 3. [Releases](https://github.com/jestempablo/home-assistant-viessmann-optolink/releases)

**Upgrading from a manually installed version.** Install the release over the same `custom_components/viessmann_optolink` directory, follow the restart prompt and keep your existing integration entry. The entry, device and entity identities carry over, including renamed entities and the previous enabled state of service settings.

## Device and controls

A shared poll reads the 43 register-backed entities every 30 seconds. Second-stage data requires a two-stage burner. Cylinder data requires a system layout with a cylinder. An unsupported value makes its entity unavailable.

| On the device page | What it provides |
| --- | --- |
| Daily controls | Operating mode (heating and hot water, hot water only, standby), boiler setpoint and domestic hot water (DHW) setpoint. |
| Temperatures and demand | Measured boiler and cylinder temperatures, effective targets, room thermostat input and cylinder charging phase. |
| Outputs and counters | Burner stages, burner fault, heating and cylinder pump outputs, burner starts and operating hours. |
| Service diagnostics | Fuel type (03), cutoff differential (13) and safety module (92) are read-only. |
| Service settings | System layout, burner and cylinder coding, pump overrun and summer/standby programs. Writable service entities start disabled on new installations. Enable an individual setting on the device's **Entities** page when you need it. |

Changes to service coding affect boiler operation. Use the commissioning instructions for your exact controller before enabling a service setting. The integration reads the current coding and allowed limits before a write. It sends one KW write, checks the acknowledgement and reads the result back. If an acknowledgement is lost, check the next reading before issuing another command. The boiler temperature limit (code 06) and DHW range (code 56) bound their respective setpoints. The controller retains control of its own safety interlocks.

## Troubleshooting

- **The adapter is missing.** Check that the USB device and its stable path are visible inside the Home Assistant OS guest or container. You can enter a path manually if the selector is empty.
- **The serial port is present, but there is no KW response.** Check that the optical head sits flush over the **V** window and that the selected path belongs to this adapter. Stop any other service using the same adapter, such as `vcontrold`.
- **Unsupported controller.** The identity read at `0x00F8` must match the supported profile. For a compatibility request, include the controller model, its four-byte identity if known, and a reference for its register map.
- **Only some entities are unavailable.** Check the system layout, burner stages and controller coding. Download the integration's diagnostics from the entry menu to see which registers are inapplicable or returned unsupported values at the last successful poll.

### USB disconnects on Synology Virtual Machine Manager

In the tested installation, the Optolink adapter occasionally disconnected even when plugged directly into the NAS. The same symptom occurred with a 5 m active USB extension, when the NAS logged `port disabled by hub`. The adapter may have behaved the same way in both setups. The cause of the disconnects is still unknown.

When DSM detects the adapter again, it can assign it a new USB device number. Virtual Machine Manager (VMM) can retain the old bus/device address, occupying a virtual USB slot while the serial port disappears from Home Assistant. The adapter's vendor/product ID and the Home Assistant entity IDs stay the same.

1. **Check the host.** Look for the adapter on the NAS and compare its USB bus/device address before and after a drop. If you use an extension or hub, a direct connection helps compare the two setups. The USB side can be checked with the optical head off the boiler.
2. **Check the VM.** If the NAS sees the adapter and its serial path is missing inside Home Assistant, open **Virtual Machine Manager → Virtual Machine**, select the HA VM and choose **Action → Edit → Others → USB device**. Remove the stale entry for the Optolink adapter, save, then add the currently detected adapter to the same VM. Identify the adapter before changing an assignment so that other devices, such as a Zigbee radio, stay connected. [Synology VMM USB settings](https://kb.synology.com/en-global/DSM/help/Virtualization/virtual_machine?version=7)
3. **Confirm a boiler reading.** Check that the original `/dev/serial/by-id/` or `/dev/serial/by-path/` path is visible in Home Assistant again. With the head on the boiler, wait for polling to resume (the normal interval is 30 seconds) and check for a fresh boiler or cylinder temperature. If the stable path changed, select the new one with **Reconfigure** on the existing entry.

#### Automatic recovery on the NAS

In this installation, a Synology DSM Task Scheduler job checks the passthrough every minute. Its host-side script matches the adapter by physical USB port and vendor/product ID (`1a86:7523` on the tested adapter), checks the running HA VM, and removes stale assignments it can identify. It attaches the newly detected bus/device address and verifies that the VM has claimed the USB interface. A healthy assignment needs no action. The script waits while the adapter is absent and stops if the match is ambiguous or another VM owns it. The task is configured separately in DSM. Once the serial port returns, a fresh temperature report in Home Assistant confirms that the optical link to the boiler works again.

This independent community integration has no affiliation with Viessmann. The protocol and register references used for the V100KC2 profile are the [openv KW protocol](https://github.com/openv/openv/wiki/Protokoll-KW), the [openv device list](https://github.com/openv/openv/wiki/Ger%C3%A4te), the [ViessData data-point tables](https://github.com/philippoo66/ViessData21/blob/master/DP_Listen_2.zip) and the [V100KC2 data-point catalog](https://github.com/SoulSolistice/esphome_vitohome/blob/9592b32ddb17947d06dad5d5686090dab9316c7e/example/catalogs/en/v100kc2.yaml).
