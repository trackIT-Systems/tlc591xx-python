# Changelog

All notable changes to this project will be documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

---

## [0.2.0] — 2026-05-07

### Added

- `set_group_blink(period, duty, channels)` — enable the chip's hardware blink
  oscillator on selected channels. The chip drives the blink autonomously after
  this call; no periodic I²C writes or CPU polling are needed.
  - `period` in seconds, clamped to the hardware range ≈ 0.042–10.67 s
    (GRPFREQ register, 24 Hz base clock).
  - `duty` as an on-time fraction 0.0–1.0.
  - Optional `channels` list; defaults to all channels.
- `set_group_dim(level, channels)` — apply a hardware master-brightness
  multiplier to selected channels via a single GRPPWM register write.
  - `level` 0.0 (off) – 1.0 (no additional dimming).
  - Opted-in channels have their individual PWM output scaled by `level`.
- `set_iref(value)` — write the IREF register (raw 8-bit) to configure the
  full-scale output current. Bit 7 = HC (half-current); bits 6:0 = CC
  current-control word (see datasheet for the Iout formula).
- `sleep()` — put the chip into low-power mode (oscillator off, all outputs
  off) by setting MODE1 bit 4 (OSC).
- `wake()` — resume normal operation (oscillator on). The datasheet recommends
  allowing ≥ 500 µs before driving outputs.
- `write_register(reg, value)` — public counterpart to the existing
  `read_register`; writes any 8-bit register by address (escape hatch for
  advanced use such as sub-address configuration).
- `set_output_change_on_ack(enable)` — toggle the OCH bit in MODE2.
  `True` = outputs latch on each I²C ACK; `False` = on STOP (default).
- `MODE1_SLEEP` constant (replaces the misleadingly named `MODE1_SPEED`).
- `examples/tlc59108_hw_blink.py` — hardware group-blink demo with
  `--period`, `--duty`, and `--channels` arguments.
- `examples/tlc59108_hw_dim.py` — sine-wave group-dim sweep demo showing that
  a single GRPPWM write dims the entire group simultaneously.
- 28 new unit tests covering all new methods, validation paths, and
  chip-specific register routing (TLC59108 vs TLC59116).

### Changed

- `TLC591xx.__init__` now accepts `grppwm_reg`, `grpfreq_reg`, and `iref_reg`
  keyword arguments; both subclasses pass the correct chip-specific addresses.
- Version bumped to `0.2.0` in both `pyproject.toml` and `__version__`.

### Fixed

- `MODE1_SPEED` was a misnomer — bit 4 of MODE1 is the oscillator-off (sleep)
  bit, not a speed control. The constant is renamed to `MODE1_SLEEP`.

---

## [0.1.0] — 2026-05-07

### Added

- `TLC591xx` base class with unified I²C interface for the TLC59108 (8-channel)
  and TLC59116 (16-channel) constant-current LED sink drivers.
- `TLC59108` subclass — default address `0x40`, LEDOUT at `0x0C`–`0x0D`.
- `TLC59116` subclass — default address `0x60`, LEDOUT at `0x14`–`0x17`.
- Per-channel brightness control via `set_brightness(channel, value)`:
  `0` = off, `1`–`254` = individual PWM, `255` = full on (no PWM).
- Bulk channel update `set_all_brightness(values)` using a single I²C block
  write with auto-increment.
- `set_all_off()` — force all LEDOUT pairs to OFF state.
- `read_errors()` — return `(EFLAG1, EFLAG2)`; TLC59108 returns `eflag2 = 0`.
- `read_register(reg)` — read any 8-bit register by address.
- Context-manager support (`with` statement); bus is closed on exit when
  opened by the driver (integer bus argument).
- Accepts an existing `SMBus` instance as `bus` — driver does not close it.
- `address` and `num_leds` properties.
- Register and mode constants exported in `__all__` for advanced use.
- Unit test suite (no hardware required): `pytest -m "not hardware"`.
- Hardware integration tests: `TLC591XX_I2C_BUS=1 pytest -m hardware -v`.
- CI workflow (GitHub Actions) running unit tests on Python 3.12 and 3.13.
- Publish workflow (GitHub Actions) releasing to PyPI on version tags.
- `examples/tlc59108_blink.py` — software blink demo.
- `examples/tlc59108_fade.py` — multi-channel wave / fade demo.

[Unreleased]: https://github.com/trackIT-Systems/tlc591xx-python/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/trackIT-Systems/tlc591xx-python/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/trackIT-Systems/tlc591xx-python/releases/tag/v0.1.0
