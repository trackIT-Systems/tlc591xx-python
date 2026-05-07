"""
Unit tests for the ``tlc591xx`` driver using a fake I²C backend (no hardware).

Covers initialisation, ``read_register``, ``read_errors``, ``set_brightness``,
``set_all_off``, ``set_all_brightness``, validation errors, and block writes.
"""

from __future__ import annotations

import pytest

from tlc591xx import (
    AUTO_INCREMENT,
    LEDOUT_DIM,
    LEDOUT_OFF,
    LEDOUT_ON,
    REG59108_EFLAG,
    REG59108_GRPPWM,
    REG_EFLAG1,
    REG_EFLAG2,
    REG_MODE1,
    REG_MODE2,
    REG_PWM0,
    TLC59108,
    TLC59116,
)


class FakeSMBus:
    """Minimal SMBus2-like fake: register file + recorded block writes."""

    def __init__(self) -> None:
        self.mem: dict[int, int] = {}
        self.block_writes: list[tuple[int, int, list[int]]] = []

    def write_byte_data(self, addr: int, reg: int, val: int) -> None:
        self.mem[reg] = val & 0xFF

    def read_byte_data(self, addr: int, reg: int) -> int:
        return int(self.mem.get(reg, 0)) & 0xFF

    def write_i2c_block_data(self, addr: int, cmd: int, data: list[int]) -> None:
        self.block_writes.append((addr, cmd, list(data)))
        base = cmd & 0x7F
        for i, b in enumerate(data):
            self.mem[base + i] = b & 0xFF


def _ledout_bits(mem: dict[int, int], ledout_base: int, channel: int) -> int:
    reg = ledout_base + (channel // 4)
    shift = (channel % 4) * 2
    return (mem[reg] >> shift) & 0x3


@pytest.fixture
def bus() -> FakeSMBus:
    return FakeSMBus()


def test_init_writes_mode_registers_59108(bus: FakeSMBus) -> None:
    TLC59108(bus, address=0x40)
    assert bus.mem[REG_MODE1] == 0x01
    assert bus.mem[REG_MODE2] == 0x00


def test_init_writes_mode_registers_59116(bus: FakeSMBus) -> None:
    TLC59116(bus, address=0x60)
    assert bus.mem[REG_MODE1] == 0x01
    assert bus.mem[REG_MODE2] == 0x00


def test_set_brightness_off_dim_on_59108(bus: FakeSMBus) -> None:
    d = TLC59108(bus, address=0x40)
    d.set_brightness(3, 0)
    assert _ledout_bits(bus.mem, 0x0C, 3) == LEDOUT_OFF
    d.set_brightness(3, 200)
    assert _ledout_bits(bus.mem, 0x0C, 3) == LEDOUT_DIM
    assert bus.mem[REG_PWM0 + 3] == 200
    d.set_brightness(3, 255)
    assert _ledout_bits(bus.mem, 0x0C, 3) == LEDOUT_ON


def test_set_brightness_pwm_not_written_for_full_on(bus: FakeSMBus) -> None:
    d = TLC59108(bus, address=0x40)
    bus.mem[REG_PWM0 + 1] = 77
    d.set_brightness(1, 255)
    assert bus.mem[REG_PWM0 + 1] == 77


def test_set_all_off_clears_ledout_59108(bus: FakeSMBus) -> None:
    d = TLC59108(bus, address=0x40)
    d.set_brightness(0, 255)
    d.set_brightness(7, 128)
    d.set_all_off()
    assert bus.mem[0x0C] == 0
    assert bus.mem[0x0D] == 0


def test_set_all_brightness_block_and_pwm_59108(bus: FakeSMBus) -> None:
    d = TLC59108(bus, address=0x40)
    vals = [10, 20, 30, 40, 50, 60, 70, 80]
    d.set_all_brightness(vals)
    assert len(bus.block_writes) == 1
    addr, cmd, block = bus.block_writes[0]
    assert addr == 0x40
    assert cmd == (AUTO_INCREMENT | REG_PWM0)
    assert block == vals
    for i, v in enumerate(vals):
        assert bus.mem[REG_PWM0 + i] == v
        assert _ledout_bits(bus.mem, 0x0C, i) == LEDOUT_DIM


def test_set_all_brightness_all_on_all_off_59108(bus: FakeSMBus) -> None:
    d = TLC59108(bus, address=0x40)
    d.set_all_brightness([255] * 8)
    for ch in range(8):
        assert _ledout_bits(bus.mem, 0x0C, ch) == LEDOUT_ON
    d.set_all_brightness([0] * 8)
    for ch in range(8):
        assert _ledout_bits(bus.mem, 0x0C, ch) == LEDOUT_OFF


def test_read_errors_59108(bus: FakeSMBus) -> None:
    bus.mem[REG59108_EFLAG] = 0xAB
    d = TLC59108(bus, address=0x40)
    e1, e2 = d.read_errors()
    assert e1 == 0xAB
    assert e2 == 0


def test_read_errors_59116_two_registers(bus: FakeSMBus) -> None:
    bus.mem[REG_EFLAG1] = 0x12
    bus.mem[REG_EFLAG2] = 0x34
    d = TLC59116(bus, address=0x60)
    assert d.read_errors() == (0x12, 0x34)


def test_read_register_out_of_range_59108(bus: FakeSMBus) -> None:
    d = TLC59108(bus, address=0x40)
    with pytest.raises(ValueError, match="out of range"):
        d.read_register(REG59108_EFLAG + 1)


def test_read_register_out_of_range_59116(bus: FakeSMBus) -> None:
    d = TLC59116(bus, address=0x60)
    with pytest.raises(ValueError, match="out of range"):
        d.read_register(REG_EFLAG2 + 1)


def test_set_brightness_invalid_channel(bus: FakeSMBus) -> None:
    d = TLC59108(bus, address=0x40)
    with pytest.raises(ValueError, match="channel"):
        d.set_brightness(8, 10)
    with pytest.raises(ValueError, match="channel"):
        d.set_brightness(-1, 10)


def test_set_brightness_invalid_value(bus: FakeSMBus) -> None:
    d = TLC59108(bus, address=0x40)
    with pytest.raises(ValueError, match="brightness"):
        d.set_brightness(0, -1)
    with pytest.raises(ValueError, match="brightness"):
        d.set_brightness(0, 256)


def test_set_all_brightness_wrong_length(bus: FakeSMBus) -> None:
    d = TLC59108(bus, address=0x40)
    with pytest.raises(ValueError, match="expected 8"):
        d.set_all_brightness([0] * 7)


def test_set_all_brightness_invalid_element(bus: FakeSMBus) -> None:
    d = TLC59108(bus, address=0x40)
    with pytest.raises(ValueError, match="brightness"):
        d.set_all_brightness([0, 0, 0, 0, 0, 0, 0, 300])


def test_properties_59108(bus: FakeSMBus) -> None:
    d = TLC59108(bus, address=0x4A)
    assert d.address == 0x4A
    assert d.num_leds == 8


def test_properties_59116(bus: FakeSMBus) -> None:
    d = TLC59116(bus, address=0x62)
    assert d.address == 0x62
    assert d.num_leds == 16


def test_external_bus_not_closed_on_close(bus: FakeSMBus) -> None:
    d = TLC59108(bus, address=0x40)
    d.close()
    d.close()


def test_set_all_brightness_59116_writes_sixteen_bytes(bus: FakeSMBus) -> None:
    d = TLC59116(bus, address=0x60)
    vals = list(range(1, 17))
    d.set_all_brightness(vals)
    assert len(bus.block_writes) == 1
    _, cmd, block = bus.block_writes[0]
    assert cmd == (AUTO_INCREMENT | REG_PWM0)
    assert len(block) == 16
    assert block == vals


def test_read_valid_aux_register_59108(bus: FakeSMBus) -> None:
    """TLC59108 group PWM lives at 0x0A — must be within max register."""
    bus.mem[REG59108_GRPPWM] = 0x55
    d = TLC59108(bus, address=0x40)
    assert d.read_register(REG59108_GRPPWM) == 0x55
