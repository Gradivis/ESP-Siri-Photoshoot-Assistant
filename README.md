# ESP Siri Photoshoot Assistant

Voice-controlled studio lighting for photo shoots, on a €5 ESP32.

"Hey Siri, Shoot Lights" … "noir at 40" and two Neewer RGB lights switch to a hot-pink key and a cyan rim. Or start **shoot mode** and the board cycles through 20 two-light looks, one every 30 seconds, while you shoot and call out brightness changes.

```
iPhone / Watch (Siri Shortcut)  --Wi-Fi HTTP-->  ESP32 (MicroPython)  --Bluetooth LE-->  Neewer lights
```

- No cloud, no app, no Home Assistant required. The ESP32 talks to the lights directly over Bluetooth and serves a tiny HTTP API on your Wi-Fi.
- Bring a travel router to a shoot and everything works on location.
- The look cycle runs on the board itself, so it keeps going whatever your phone or laptop is doing.

Tested with two **Neewer RGB660 PRO** panels. Other Neewer lights that use the standard (non-"Infinity") protocol should work. Support for IR-controlled lights and an IR camera trigger (Canon RC-6 codes) is on the roadmap.

## Hardware

- Any classic ESP32 dev board (tested: ESP32-D0WD-V3, 4 MB flash).
- One or more Neewer Bluetooth lights. An ESP32 holds about three BLE connections at once.

## Setup

1. Flash MicroPython (tested v1.29.0, `ESP32_GENERIC`):
   ```bash
   esptool --port /dev/cu.usbserial-XXXX erase-flash
   esptool --port /dev/cu.usbserial-XXXX write-flash 0x1000 ESP32_GENERIC-*.bin
   ```
   If the erase fails partway, run it again before writing; a half-erased filesystem makes MicroPython report corruption.
2. Copy `firmware/secrets.example.py` to `firmware/secrets.py` and fill in your Wi-Fi details.
3. Switch the lights on, then upload and reboot:
   ```bash
   cd firmware
   uvx mpremote connect /dev/cu.usbserial-XXXX fs cp secrets.py :secrets.py + fs cp neewer.py :neewer.py + fs cp main.py :main.py + reset
   ```
4. Check it: `curl http://shootbox.local/status`. Lights are numbered by Bluetooth address, so the numbering is stable across reboots. `/off?l=1` then `/on?l=1` will show you which one is light 1.
5. Import `shortcuts/Shoot Lights.shortcut` on a Mac or iPhone. Say "Hey Siri, Shoot Lights" and answer the question ("red", "noir", "shoot mode", "brighter", "off").

## HTTP API

All commands are GETs to `http://shootbox.local/<command>`. Add `l=1`, `l=2` or `l=1,2` to target specific lights (default: all).

| Command | Effect |
|---|---|
| `/status` | State of each light plus shoot-mode progress |
| `/color?h=320&s=100&b=45` | Hue 0-360, saturation 0-100, brightness 1-100 |
| `/white?k=3200&b=60` | White, 3200-5600 K |
| `/red`, `/teal?b=40`, … | Named colours: red orange amber yellow green teal cyan blue indigo purple violet magenta pink |
| `/on`, `/off` | Power (`off` also stops shoot mode) |
| `/brightness?b=70`, `/brighter`, `/dimmer` | Brightness. In shoot mode these set the master level |
| `/<look>?b=50` | Two-light look at master brightness `b` |
| `/shoot?b=50&mins=10&secs=30` | Shoot mode: cycle all looks |
| `/next`, `/stop` | Skip a look; stop cycling and hold the current look |
| `/scan` | Find lights switched on after boot |

Dictated text is accepted as-is: the first known word wins and any number becomes the brightness, so "make it teal at fifty percent" works from Siri.

**Looks** (light 1 / light 2): noir, reversenoir, sunset, bloodmoon, goldenhour, interrogation, toxic, ocean, ember, vaporwave, royal, blockbuster, redroom, ultraviolet, studio, acid, arctic, hellfire, cyberpunk, midnight. Each light's level is relative to the master brightness, so key-to-rim ratios hold when you brighten or dim. Edit `LOOKS` in `firmware/main.py` to make your own.

## Neewer protocol

Writes go to characteristic `69400002-B5A3-F393-E0A9-E50E24DCCA99` as `[0x78, tag, length, …params, checksum]`, where the checksum is the byte sum & 0xFF.

| Tag | Command | Params |
|---|---|---|
| `0x81` | Power | `1` on, `2` off |
| `0x86` | HSI | hue low byte, hue high byte, saturation, brightness |
| `0x87` | CCT | brightness, kelvin / 100, green-magenta (50 = neutral) |

Protocol details come from [NeewerLite-Python](https://github.com/taburineagle/NeewerLite-Python) by Zach Glenwright (MIT); thank you.

## Roadmap

- IR transmitter and receiver: learn and replay codes for IR-only lights, and fire a Canon camera with RC-6 codes.
- Per-look Siri phrases ("Hey Siri, noir").
- Optional Home Assistant integration (ESPHome port).

## Licence

AGPL-3.0. See [LICENSE](LICENSE).
