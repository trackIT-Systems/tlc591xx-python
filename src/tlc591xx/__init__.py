"""
tlc591xx — Python library for the TLC59108 and TLC59116
constant-current LED sink drivers (I²C).
"""

from __future__ import annotations

from typing import Union

from smbus2 import SMBus

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "TLC591xx",
    "TLC59116",
    "TLC59108",
    # Registers / modes (for advanced use)
    "REG_MODE1",
    "REG_MODE2",
    "REG_PWM0",
    "REG_GRPPWM",
    "REG_GRPFREQ",
    "REG_IREF",
    "REG_EFLAG1",
    "REG_EFLAG2",
    "REG59108_GRPPWM",
    "REG59108_GRPFREQ",
    "REG59108_IREF",
    "REG59108_EFLAG",
    "LEDOUT_OFF",
    "LEDOUT_ON",
    "LEDOUT_DIM",
    "LEDOUT_BLINK",
    "LEDOUT_MASK",
    "MODE1_NORMAL",
    "MODE1_SPEED",
    "MODE2_DIM",
    "MODE2_BLINK",
    "MODE2_OCH_STOP",
    "MODE2_OCH_ACK",
    "AUTO_INCREMENT",
]

# --- Register addresses (MODE / PWM / LEDOUT are shared layout; see chip-specific below) ---

REG_MODE1 = 0x00
REG_MODE2 = 0x01
REG_PWM0 = 0x02
# TLC59116 only (SLDS157):
REG_GRPPWM = 0x12
REG_GRPFREQ = 0x13
REG_IREF = 0x1C
REG_EFLAG1 = 0x1D
REG_EFLAG2 = 0x1E
# TLC59108 only (SLDS156) — map is compact; do not use 59116 GRPPWM/EFLAG addresses on 59108
REG59108_GRPPWM = 0x0A
REG59108_GRPFREQ = 0x0B
REG59108_IREF = 0x12
REG59108_EFLAG = 0x13

# MODE1: bit 4 = OSC (0 = normal / oscillator on for PWM); bit 0 = ALLCALL response
MODE1_NORMAL = 0 << 4
MODE1_SPEED = 1 << 4
MODE1_ALLCALL = 0x01  # respond to All Call I2C address

# MODE2: bit 5 = DMBLNK (0 = group dim, 1 = group blink); bit 3 = OCH
MODE2_DIM = 0 << 5
MODE2_BLINK = 1 << 5
MODE2_OCH_STOP = 0 << 3
MODE2_OCH_ACK = 1 << 3

# LED driver output state (2 bits per output in LEDOUTn registers)
LEDOUT_OFF = 0x0
LEDOUT_ON = 0x1
LEDOUT_DIM = 0x2
LEDOUT_BLINK = 0x3
LEDOUT_MASK = 0x3

# I2C register auto-increment (datasheet: set bit 7 of command byte)
AUTO_INCREMENT = 0x80

_MAX_REGISTER_59116 = 0x1E
_MAX_REGISTER_59108 = REG59108_EFLAG


class TLC591xx:
    """
    I²C interface to a TLC59108/TLC59116 constant-current LED sink driver.

    Brightness per channel: ``0`` = off, ``255`` = full on (no PWM), ``1``–``254`` = PWM dimming.

    ``bus`` may be an SMBus instance or an integer bus number (e.g. ``1`` for ``/dev/i2c-1``).
    If an integer is passed, the bus is opened here and closed when exiting the context manager.
    """

    def __init__(
        self,
        bus: Union[int, SMBus],
        address: int,
        *,
        num_leds: int,
        ledout_offset: int,
        max_register: int,
        eflag_registers: tuple[int, ...],
    ) -> None:
        if not (0 <= address <= 0x7F):
            raise ValueError(f"invalid I2C address: {address!r}")
        if num_leds < 1 or num_leds > 16:
            raise ValueError(f"num_leds must be 1..16, got {num_leds}")
        if max_register < 0 or max_register > 0x7F:
            raise ValueError(f"invalid max_register: {max_register!r}")
        if not eflag_registers:
            raise ValueError("eflag_registers must name at least one register")
        if any(r < 0 or r > max_register for r in eflag_registers):
            raise ValueError("eflag_registers out of range for this chip")
        if not (0 <= ledout_offset <= max_register):
            raise ValueError(f"invalid ledout_offset: {ledout_offset!r}")

        self._address = address
        self._num_leds = num_leds
        self._ledout_offset = ledout_offset
        self._ledout_count = (num_leds + 3) // 4
        self._max_register = max_register
        self._eflag_registers = eflag_registers

        if self._ledout_offset + self._ledout_count - 1 > max_register:
            raise ValueError("LEDOUT registers would exceed max register address")

        if isinstance(bus, int):
            self._bus = SMBus(bus)
            self._own_bus = True
        else:
            self._bus = bus
            self._own_bus = False

        # Same intent as Linux leds-tlc591xx: normal mode, group dim, outputs latch on STOP.
        # MODE1: oscillator on (OSC=0), respond to All Call (plan / typical bring-up).
        self._write(REG_MODE1, MODE1_NORMAL | MODE1_ALLCALL)
        self._write(REG_MODE2, MODE2_OCH_STOP | MODE2_DIM)

    @property
    def address(self) -> int:
        return self._address

    @property
    def num_leds(self) -> int:
        return self._num_leds

    def close(self) -> None:
        if self._own_bus:
            self._bus.close()
            self._own_bus = False

    def __enter__(self) -> TLC591xx:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _write(self, reg: int, value: int) -> None:
        if not (0 <= reg <= self._max_register):
            raise ValueError(f"register out of range: {reg}")
        self._bus.write_byte_data(self._address, reg, value & 0xFF)

    def _read(self, reg: int) -> int:
        if not (0 <= reg <= self._max_register):
            raise ValueError(f"register out of range: {reg}")
        return int(self._bus.read_byte_data(self._address, reg)) & 0xFF

    def read_register(self, reg: int) -> int:
        """Read an 8-bit register (e.g. for diagnostics or hardware tests)."""
        return self._read(reg)

    def _check_channel(self, channel: int) -> None:
        if not (0 <= channel < self._num_leds):
            raise ValueError(f"channel must be 0..{self._num_leds - 1}, got {channel}")

    def _set_ledout(self, channel: int, state: int) -> None:
        self._check_channel(channel)
        if state & ~LEDOUT_MASK:
            raise ValueError(f"invalid LEDOUT state: {state!r}")
        shift = (channel % 4) * 2
        mask = LEDOUT_MASK << shift
        reg = self._ledout_offset + (channel >> 2)
        cur = self._read(reg)
        cur = (cur & ~mask) | ((state & LEDOUT_MASK) << shift)
        self._write(reg, cur)

    def set_brightness(self, channel: int, value: int) -> None:
        """Set one channel: 0 off, 255 on (full), 1–254 PWM duty."""
        self._check_channel(channel)
        if value < 0 or value > 255:
            raise ValueError("brightness must be 0..255")

        if value == 0:
            self._set_ledout(channel, LEDOUT_OFF)
        elif value == 255:
            self._set_ledout(channel, LEDOUT_ON)
        else:
            self._set_ledout(channel, LEDOUT_DIM)
            self._write(REG_PWM0 + channel, value)

    def set_all_off(self) -> None:
        """Force all outputs off (all LEDOUT pairs = OFF)."""
        for i in range(self._ledout_count):
            self._write(self._ledout_offset + i, 0x00)

    def set_all_brightness(self, values: list[int]) -> None:
        """
        Set every channel from ``values`` (length must equal :py:attr:`num_leds`).

        Updates LEDOUT for each channel, then writes all PWM bytes in one block using
        auto-increment (faster than per-channel PWM writes).
        """
        if len(values) != self._num_leds:
            raise ValueError(
                f"expected {self._num_leds} brightness values, got {len(values)}"
            )
        pwm_bytes: list[int] = []
        for ch, v in enumerate(values):
            if v < 0 or v > 255:
                raise ValueError(f"brightness must be 0..255, got {v!r} at channel {ch}")
            if v == 0:
                self._set_ledout(ch, LEDOUT_OFF)
                pwm_bytes.append(0)
            elif v == 255:
                self._set_ledout(ch, LEDOUT_ON)
                pwm_bytes.append(0xFF)
            else:
                self._set_ledout(ch, LEDOUT_DIM)
                pwm_bytes.append(v)

        cmd = AUTO_INCREMENT | REG_PWM0
        self._bus.write_i2c_block_data(self._address, cmd, pwm_bytes)

    def read_errors(self) -> tuple[int, int]:
        """
        Return error-flag bytes as ``(first, second)``.

        * **TLC59116:** ``(EFLAG1, EFLAG2)`` at 0x1D and 0x1E.
        * **TLC59108:** one EFLAG at 0x13; ``second`` is always ``0`` (no second register).
        """
        regs = self._eflag_registers
        first = self.read_register(regs[0])
        if len(regs) >= 2:
            second = self.read_register(regs[1])
        else:
            second = 0
        return (first, second)


class TLC59116(TLC591xx):
    """16-channel TLC59116 (LEDOUT0–3 at 0x14–0x17). Default address ``0x60`` (verify A0–A3 wiring)."""

    def __init__(self, bus: Union[int, SMBus], address: int = 0x60) -> None:
        super().__init__(
            bus,
            address,
            num_leds=16,
            ledout_offset=0x14,
            max_register=_MAX_REGISTER_59116,
            eflag_registers=(REG_EFLAG1, REG_EFLAG2),
        )


class TLC59108(TLC591xx):
    """8-channel TLC59108 (LEDOUT0–1 at 0x0C–0x0D). Default address ``0x40`` (verify A0–A3 wiring)."""

    def __init__(self, bus: Union[int, SMBus], address: int = 0x40) -> None:
        super().__init__(
            bus,
            address,
            num_leds=8,
            ledout_offset=0x0C,
            max_register=_MAX_REGISTER_59108,
            eflag_registers=(REG59108_EFLAG,),
        )
