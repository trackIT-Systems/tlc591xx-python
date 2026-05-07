# tlc591xx-python

Python library for the **TLC59108** (8-channel) and **TLC59116** (16-channel) constant-current LED sink drivers over I²C.

[![CI](https://github.com/trackIT-Systems/tlc591xx-python/actions/workflows/ci.yml/badge.svg)](https://github.com/trackIT-Systems/tlc591xx-python/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/tlc591xx)](https://pypi.org/project/tlc591xx/)
[![Python](https://img.shields.io/pypi/pyversions/tlc591xx)](https://pypi.org/project/tlc591xx/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Features

- Unified `TLC591xx` base class with chip-specific `TLC59108` and `TLC59116` subclasses
- Per-channel brightness control (`0` = off, `1`–`254` = PWM, `255` = full on)
- Bulk update of all channels in a single I²C block write (`set_all_brightness`)
- Context-manager support — bus is automatically closed on exit
- Error-flag register reading (`read_errors`) for open-load / over-temperature diagnostics
- Works with any `smbus2`-compatible bus object or a plain integer bus number

---

## Installation

```bash
pip install tlc591xx
```

Requires Python ≥ 3.12 and [`smbus2`](https://pypi.org/project/smbus2/).

On a Raspberry Pi, make sure I²C is enabled:

```bash
sudo raspi-config  # Interface Options → I2C → Enable
```

---

## Quick Start

### TLC59108 (8 channels, default address `0x40`)

```python
from tlc591xx import TLC59108

with TLC59108(bus=1) as drv:
    drv.set_brightness(0, 255)           # channel 0 fully on
    drv.set_brightness(1, 128)           # channel 1 at ~50 % PWM
    drv.set_all_brightness([255] * 8)    # all channels on
    drv.set_all_off()                    # all channels off
```

### TLC59116 (16 channels, default address `0x60`)

```python
from tlc591xx import TLC59116

with TLC59116(bus=1) as drv:
    drv.set_all_brightness(list(range(0, 256, 16)))  # brightness gradient
```

### Sharing an existing SMBus instance

```python
from smbus2 import SMBus
from tlc591xx import TLC59108

with SMBus(1) as bus:
    drv = TLC59108(bus, address=0x41)   # external bus: not closed by driver
    drv.set_brightness(3, 200)
```

---

## API Reference

### `TLC59108(bus, address=0x40)`
### `TLC59116(bus, address=0x60)`

| Parameter | Type | Description |
|-----------|------|-------------|
| `bus` | `int` or `SMBus` | I²C bus number (`/dev/i2c-<n>`) or an open `SMBus` instance |
| `address` | `int` | 7-bit I²C address — must match the A0–A3 pin strapping on the board |

#### Methods

| Method | Description |
|--------|-------------|
| `set_brightness(channel, value)` | Set one channel. `value`: `0` = off, `1`–`254` = PWM, `255` = full on |
| `set_all_brightness(values)` | Set all channels from a list; length must equal `num_leds`. Uses a single I²C block write |
| `set_all_off()` | Force all outputs off |
| `read_errors()` | Return `(eflag1, eflag2)` error-flag bytes; TLC59108 always returns `eflag2 = 0` |
| `read_register(reg)` | Read any 8-bit register by address (useful for diagnostics) |
| `close()` | Release the bus if it was opened by the driver |

#### Properties

| Property | Description |
|----------|-------------|
| `address` | The I²C address the driver was configured with |
| `num_leds` | Number of output channels (`8` for TLC59108, `16` for TLC59116) |

---

## I²C Address Selection

Both chips use four address pins (A0–A3) to set the 7-bit I²C address. The base addresses are:

| Chip | Base address | Range |
|------|-------------|-------|
| TLC59108 | `0x40` | `0x40`–`0x4F` |
| TLC59116 | `0x60` | `0x60`–`0x6F` |

Pass the matching address as the `address` parameter. Example with non-default strapping:

```python
drv = TLC59108(bus=1, address=0x43)   # A0=1, A1=1, A2=0, A3=0
```

---

## Examples

### Blink all outputs

```bash
# From the repo root (no install required):
PYTHONPATH=src python3 examples/tlc59108_blink.py
PYTHONPATH=src python3 examples/tlc59108_blink.py --bus 1 --delay 0.2
```

### Multi-channel fade / wave

```bash
PYTHONPATH=src python3 examples/tlc59108_fade.py -v
PYTHONPATH=src python3 examples/tlc59108_fade.py -c 0,1,5,6 --delay 0.05
```

---

## Development

```bash
git clone https://github.com/trackIT-Systems/tlc591xx-python.git
cd tlc591xx-python
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

### Run unit tests (no hardware required)

```bash
pytest -m "not hardware"
```

### Run hardware tests

Connect a TLC591xx chip on I²C and set the environment variables:

```bash
TLC591XX_I2C_BUS=1 TLC591XX_MODEL=TLC59108 pytest -m hardware -v
```

| Variable | Default | Description |
|----------|---------|-------------|
| `TLC591XX_I2C_BUS` | — | I²C bus number (required for hardware tests) |
| `TLC591XX_ADDRESS` | chip default | Override the I²C address |
| `TLC591XX_MODEL` | `TLC59108` | `TLC59108` or `TLC59116` |

---

## License

MIT — see [LICENSE](LICENSE).
