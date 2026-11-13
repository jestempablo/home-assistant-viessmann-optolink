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
- **No KW response.** Verify the selected port and seat the head over the optical window. Stop any other service using the same adapter, such as `vcontrold`. A disconnected link makes the entities unavailable until polling succeeds again.
- **Unsupported controller.** The identity read at `0x00F8` must match the supported profile. For a compatibility request, include the controller model, its four-byte identity if known, and a reference for its register map.
- **Only some entities are unavailable.** Check the system layout, burner stages and controller coding. Download the integration's diagnostics from the entry menu to see which registers are inapplicable or returned unsupported values at the last successful poll.

This independent community integration has no affiliation with Viessmann. The protocol and register references used for the V100KC2 profile are the [openv KW protocol](https://github.com/openv/openv/wiki/Protokoll-KW), the [openv device list](https://github.com/openv/openv/wiki/Ger%C3%A4te), the [ViessData data-point tables](https://github.com/philippoo66/ViessData21/blob/master/DP_Listen_2.zip) and the [V100KC2 data-point catalog](https://github.com/SoulSolistice/esphome_vitohome/blob/9592b32ddb17947d06dad5d5686090dab9316c7e/example/catalogs/en/v100kc2.yaml).
