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
- **Hardware group-blink** — chip oscillator drives the blink autonomously, zero CPU overhead (`set_group_blink`)
- **Hardware group-dim** — single register write scales a whole group's brightness (`set_group_dim`)
- Output current reference control (`set_iref`)
- Sleep / wake power management (`sleep`, `wake`)
- Raw register access (`read_register`, `write_register`) for advanced use
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

## Usage

### Hardware group-blink

The chip contains an internal oscillator that can blink any subset of outputs
autonomously.  Once `set_group_blink()` is called, no further I²C traffic or
CPU involvement is needed to sustain the blink — the chip runs it by itself.

```python
from tlc591xx import TLC59108

with TLC59108(bus=1) as drv:
    # Set individual PWM values first (1–254 range writes the PWM register).
    # These determine the on-phase brightness once blink mode is active.
    drv.set_brightness(0, 200)
    drv.set_brightness(1, 100)

    # Blink channels 0 and 1 at 2 Hz, 50 % duty cycle.
    # After this call the chip handles everything — the CPU can sleep.
    drv.set_group_blink(period=0.5, duty=0.5, channels=[0, 1])

    import time; time.sleep(30)   # chip blinks on its own for 30 s
```

The `period` is quantised to the hardware's 24 Hz base clock
(`GRPFREQ = round(period × 24 − 1)`), so the actual period is
`(GRPFREQ + 1) / 24` seconds.  The range is ≈ **42 ms – 10.67 s**.

> **Note on PWM values:** `set_brightness(ch, 255)` sets the output to fully
> on (LEDOUT = ON) without writing the PWM register.  Use values **1–254**
> before calling `set_group_blink` so the PWM register holds a meaningful
> on-phase brightness.

---

### Hardware group-dim

Group-dim mode lets you scale the brightness of a whole group of LEDs with a
**single register write**, without touching each channel's individual PWM value.
It works as a hardware multiplier: the final output current is
`(PWMn / 256) × (GRPPWM / 255) × Imax`.

```python
from tlc591xx import TLC59108

with TLC59108(bus=1) as drv:
    # Programme a fixed relative pattern across all 8 channels.
    drv.set_all_brightness([30, 60, 90, 120, 150, 180, 210, 240])

    # Now dim the whole group to 25 % with one call — the relative
    # pattern between channels stays exactly as programmed above.
    drv.set_group_dim(0.25)

    # Fade the group from full to off in a loop.
    import time
    for step in range(100, -1, -1):
        drv.set_group_dim(step / 100)
        time.sleep(0.02)
```

Channels not passed to `channels=` (or all channels when `channels=None`)
are switched to `LEDOUT_BLINK` state, which in group-dim mode means their
output is multiplied by `level`.  Channels left at `LEDOUT_DIM` or `LEDOUT_ON`
are unaffected.

---

### Sleep and wake

The chip's oscillator can be disabled to save power.  All outputs go off
immediately.  Re-enabling restores the previous configuration; allow at least
500 µs for the oscillator to stabilise before driving outputs.

```python
import time
from tlc591xx import TLC59108

with TLC59108(bus=1) as drv:
    drv.set_all_brightness([128] * 8)   # LEDs on

    drv.sleep()                          # oscillator off, outputs off
    time.sleep(5)

    drv.wake()                           # oscillator back on
    time.sleep(0.001)                    # ≥ 500 µs settling time
    drv.set_all_brightness([128] * 8)   # restore
```

---

### Current reference (IREF)

The IREF register sets the full-scale output current for all channels.
Reducing it globally limits the maximum current regardless of PWM settings —
useful when you want to cap brightness at the hardware level rather than
through software PWM values.

```python
from tlc591xx import TLC59108, REG59108_IREF

with TLC59108(bus=1) as drv:
    drv.set_all_brightness([255] * 8)

    # Bit 7 (HC) = half-current mode; bits 6:0 (CC) = 7-bit current-control word.
    # Full-scale (chip default after reset): CC = 0b1111111 = 0x7F
    drv.set_iref(0x7F)   # maximum current

    # Set HC=1 to halve the full-scale current with one bit.
    drv.set_iref(0xFF)   # HC=1, CC=0x7F → half of the above

    # Lower CC for a finer reduction — see the datasheet for the Iout formula
    # (depends on your external Rext resistor value).
    drv.set_iref(0x3F)   # HC=0, CC=0x3F → roughly half of maximum
```

---

### Output-change timing (OCH)

By default outputs latch when the I²C master sends a **STOP** condition
(`OCH = 0`).  Switching to **ACK** mode (`OCH = 1`) makes each output register
take effect as soon as it is acknowledged, which can reduce visible tearing
when updating many channels in rapid succession.

```python
with TLC59108(bus=1) as drv:
    drv.set_output_change_on_ack(True)   # outputs update on ACK
    drv.set_all_brightness([200] * 8)
    drv.set_output_change_on_ack(False)  # back to STOP (default)
```

---

### Raw register access

`read_register` and `write_register` give direct access to any chip register
by address — useful for features not yet covered by a dedicated method, such
as configuring I²C sub-addresses so multiple chips can be addressed
simultaneously with a single broadcast write.

```python
from tlc591xx import TLC59108

# TLC59108 sub-address registers: SUBADR1=0x0E, SUBADR2=0x0F, SUBADR3=0x10
with TLC59108(bus=1) as drv:
    # Configure a shared broadcast address on two chips
    drv.write_register(0x0E, 0x92)   # SUBADR1 = 0x49 (left-shifted in register)

    # Inspect the current value of any register for diagnostics
    mode2 = drv.read_register(0x01)
    print(f"MODE2 = 0x{mode2:02x}")
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

**Brightness**

| Method | Description |
|--------|-------------|
| `set_brightness(channel, value)` | Set one channel: `0` = off, `1`–`254` = PWM duty, `255` = full on |
| `set_all_brightness(values)` | Set all channels from a list (length = `num_leds`) in one I²C block write |
| `set_all_off()` | Force all outputs off |

**Hardware group generator**

| Method | Description |
|--------|-------------|
| `set_group_blink(period, duty=0.5, channels=None)` | Hardware blink via the chip oscillator. `period` in seconds (≈ 0.042–10.67 s); `duty` = on-time fraction 0.0–1.0; `channels` = indices to blink (`None` = all) |
| `set_group_dim(level, channels=None)` | Master-brightness multiplier. `level` 0.0–1.0 scales all opted-in channels via a single GRPPWM write; `channels` = indices to include (`None` = all) |

**Current reference**

| Method | Description |
|--------|-------------|
| `set_iref(value)` | Write the IREF register (raw 8-bit). Bit 7 = HC (half-current); bits 6:0 = CC current-control word — see datasheet for the Iout formula |

**Power management**

| Method | Description |
|--------|-------------|
| `sleep()` | Oscillator off — low-power sleep, outputs off |
| `wake()` | Oscillator on — resume normal operation (allow ≥ 500 µs before driving outputs) |

**Output-change timing**

| Method | Description |
|--------|-------------|
| `set_output_change_on_ack(enable)` | `True` = outputs latch on each I²C ACK; `False` = on STOP (default) |

**Register access and diagnostics**

| Method | Description |
|--------|-------------|
| `read_errors()` | Return `(eflag1, eflag2)` error-flag bytes; TLC59108 always returns `eflag2 = 0` |
| `read_register(reg)` | Read any 8-bit register by address |
| `write_register(reg, value)` | Write any 8-bit register by address (escape hatch for advanced use) |
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

### Software blink (CPU-driven)

```bash
# From the repo root (no install required):
PYTHONPATH=src python3 examples/tlc59108_blink.py
PYTHONPATH=src python3 examples/tlc59108_blink.py --bus 1 --delay 0.2
```

### Hardware group-blink (chip oscillator, zero CPU overhead)

```bash
PYTHONPATH=src python3 examples/tlc59108_hw_blink.py
PYTHONPATH=src python3 examples/tlc59108_hw_blink.py --period 0.5 --duty 0.25
PYTHONPATH=src python3 examples/tlc59108_hw_blink.py --channels 0,2,4 --period 2.0
```

### Hardware group-dim (master brightness knob)

```bash
PYTHONPATH=src python3 examples/tlc59108_hw_dim.py
PYTHONPATH=src python3 examples/tlc59108_hw_dim.py --delay 0.02
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
