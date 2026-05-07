"""
Unit tests for the ``tlc591xx`` driver using a fake I²C backend (no hardware).

Covers initialisation, ``read_register``, ``write_register``, ``read_errors``,
``set_brightness``, ``set_all_off``, ``set_all_brightness``, ``set_group_blink``,
``set_group_dim``, ``set_iref``, ``sleep``/``wake``, ``set_output_change_on_ack``,
validation errors, and block writes.
"""

from __future__ import annotations

import pytest

from tlc591xx import (
    AUTO_INCREMENT,
    LEDOUT_BLINK,
    LEDOUT_DIM,
    LEDOUT_OFF,
    LEDOUT_ON,
    MODE1_SLEEP,
    MODE2_BLINK,
    MODE2_OCH_ACK,
    REG59108_EFLAG,
    REG59108_GRPFREQ,
    REG59108_GRPPWM,
    REG59108_IREF,
    REG_EFLAG1,
    REG_EFLAG2,
    REG_GRPFREQ,
    REG_GRPPWM,
    REG_IREF,
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


# ---------------------------------------------------------------------------
# write_register
# ---------------------------------------------------------------------------


def test_write_register_59108(bus: FakeSMBus) -> None:
    d = TLC59108(bus, address=0x40)
    d.write_register(REG59108_GRPPWM, 0xAB)
    assert bus.mem[REG59108_GRPPWM] == 0xAB


def test_write_register_masks_to_8_bits(bus: FakeSMBus) -> None:
    d = TLC59108(bus, address=0x40)
    d.write_register(REG59108_GRPPWM, 0x1FF)
    assert bus.mem[REG59108_GRPPWM] == 0xFF


def test_write_register_out_of_range_raises(bus: FakeSMBus) -> None:
    d = TLC59108(bus, address=0x40)
    with pytest.raises(ValueError, match="out of range"):
        d.write_register(REG59108_EFLAG + 1, 0x00)


# ---------------------------------------------------------------------------
# sleep / wake
# ---------------------------------------------------------------------------


def test_sleep_sets_osc_bit_59108(bus: FakeSMBus) -> None:
    d = TLC59108(bus, address=0x40)
    d.sleep()
    assert bus.mem[REG_MODE1] & MODE1_SLEEP


def test_wake_clears_osc_bit_59108(bus: FakeSMBus) -> None:
    d = TLC59108(bus, address=0x40)
    d.sleep()
    d.wake()
    assert not (bus.mem[REG_MODE1] & MODE1_SLEEP)


def test_sleep_preserves_other_mode1_bits(bus: FakeSMBus) -> None:
    d = TLC59108(bus, address=0x40)
    d.write_register(REG_MODE1, 0x01)  # ALLCALL bit set
    d.sleep()
    assert bus.mem[REG_MODE1] & 0x01   # ALLCALL still set
    assert bus.mem[REG_MODE1] & MODE1_SLEEP


# ---------------------------------------------------------------------------
# set_output_change_on_ack
# ---------------------------------------------------------------------------


def test_set_output_change_on_ack_enables(bus: FakeSMBus) -> None:
    d = TLC59108(bus, address=0x40)
    d.set_output_change_on_ack(True)
    assert bus.mem[REG_MODE2] & MODE2_OCH_ACK


def test_set_output_change_on_ack_disables(bus: FakeSMBus) -> None:
    d = TLC59108(bus, address=0x40)
    d.set_output_change_on_ack(True)
    d.set_output_change_on_ack(False)
    assert not (bus.mem[REG_MODE2] & MODE2_OCH_ACK)


def test_set_output_change_preserves_other_mode2_bits(bus: FakeSMBus) -> None:
    d = TLC59108(bus, address=0x40)
    # Pre-set DMBLNK bit
    bus.mem[REG_MODE2] = MODE2_BLINK
    d.set_output_change_on_ack(True)
    assert bus.mem[REG_MODE2] & MODE2_BLINK   # still set
    assert bus.mem[REG_MODE2] & MODE2_OCH_ACK  # newly set


# ---------------------------------------------------------------------------
# set_iref
# ---------------------------------------------------------------------------


def test_set_iref_59108_writes_correct_register(bus: FakeSMBus) -> None:
    d = TLC59108(bus, address=0x40)
    d.set_iref(0xC0)
    assert bus.mem[REG59108_IREF] == 0xC0


def test_set_iref_59116_writes_correct_register(bus: FakeSMBus) -> None:
    d = TLC59116(bus, address=0x60)
    d.set_iref(0x7F)
    assert bus.mem[REG_IREF] == 0x7F


def test_set_iref_invalid_raises(bus: FakeSMBus) -> None:
    d = TLC59108(bus, address=0x40)
    with pytest.raises(ValueError):
        d.set_iref(256)
    with pytest.raises(ValueError):
        d.set_iref(-1)


# ---------------------------------------------------------------------------
# set_group_blink
# ---------------------------------------------------------------------------


def test_set_group_blink_sets_mode2_blink(bus: FakeSMBus) -> None:
    d = TLC59108(bus, address=0x40)
    d.set_group_blink(1.0)
    assert bus.mem[REG_MODE2] & MODE2_BLINK


def test_set_group_blink_writes_grpfreq_59108(bus: FakeSMBus) -> None:
    d = TLC59108(bus, address=0x40)
    # period=1.0 s → GRPFREQ = round(1.0 * 24 - 1) = 23
    d.set_group_blink(1.0)
    assert bus.mem[REG59108_GRPFREQ] == 23


def test_set_group_blink_writes_grpfreq_59116(bus: FakeSMBus) -> None:
    d = TLC59116(bus, address=0x60)
    d.set_group_blink(1.0)
    assert bus.mem[REG_GRPFREQ] == 23


def test_set_group_blink_writes_grppwm_duty(bus: FakeSMBus) -> None:
    d = TLC59108(bus, address=0x40)
    # duty=0.5 → GRPPWM = round(0.5 * 256) = 128
    d.set_group_blink(1.0, duty=0.5)
    assert bus.mem[REG59108_GRPPWM] == 128


def test_set_group_blink_sets_ledout_blink_all(bus: FakeSMBus) -> None:
    d = TLC59108(bus, address=0x40)
    d.set_group_blink(1.0)
    for ch in range(d.num_leds):
        assert _ledout_bits(bus.mem, 0x0C, ch) == LEDOUT_BLINK


def test_set_group_blink_sets_ledout_blink_subset(bus: FakeSMBus) -> None:
    d = TLC59108(bus, address=0x40)
    d.set_group_blink(1.0, channels=[0, 3])
    assert _ledout_bits(bus.mem, 0x0C, 0) == LEDOUT_BLINK
    assert _ledout_bits(bus.mem, 0x0C, 3) == LEDOUT_BLINK
    # Channel 1 untouched (was OFF from init)
    assert _ledout_bits(bus.mem, 0x0C, 1) == LEDOUT_OFF


def test_set_group_blink_period_clamped_to_hardware_min(bus: FakeSMBus) -> None:
    d = TLC59108(bus, address=0x40)
    d.set_group_blink(0.001)  # much shorter than hardware minimum
    assert bus.mem[REG59108_GRPFREQ] == 0


def test_set_group_blink_period_clamped_to_hardware_max(bus: FakeSMBus) -> None:
    d = TLC59108(bus, address=0x40)
    d.set_group_blink(9999.0)
    assert bus.mem[REG59108_GRPFREQ] == 255


def test_set_group_blink_invalid_period_raises(bus: FakeSMBus) -> None:
    d = TLC59108(bus, address=0x40)
    with pytest.raises(ValueError, match="period"):
        d.set_group_blink(0.0)
    with pytest.raises(ValueError, match="period"):
        d.set_group_blink(-1.0)


def test_set_group_blink_invalid_duty_raises(bus: FakeSMBus) -> None:
    d = TLC59108(bus, address=0x40)
    with pytest.raises(ValueError, match="duty"):
        d.set_group_blink(1.0, duty=-0.1)
    with pytest.raises(ValueError, match="duty"):
        d.set_group_blink(1.0, duty=1.1)


# ---------------------------------------------------------------------------
# set_group_dim
# ---------------------------------------------------------------------------


def test_set_group_dim_clears_mode2_blink(bus: FakeSMBus) -> None:
    d = TLC59108(bus, address=0x40)
    # First engage blink, then switch to dim
    d.set_group_blink(1.0)
    d.set_group_dim(0.5)
    assert not (bus.mem[REG_MODE2] & MODE2_BLINK)


def test_set_group_dim_writes_grppwm_59108(bus: FakeSMBus) -> None:
    d = TLC59108(bus, address=0x40)
    # level=1.0 → GRPPWM = 255 (full brightness, no extra dim)
    d.set_group_dim(1.0)
    assert bus.mem[REG59108_GRPPWM] == 255


def test_set_group_dim_writes_grppwm_59116(bus: FakeSMBus) -> None:
    d = TLC59116(bus, address=0x60)
    d.set_group_dim(0.0)
    assert bus.mem[REG_GRPPWM] == 0


def test_set_group_dim_sets_ledout_blink_all(bus: FakeSMBus) -> None:
    d = TLC59108(bus, address=0x40)
    d.set_group_dim(0.8)
    for ch in range(d.num_leds):
        assert _ledout_bits(bus.mem, 0x0C, ch) == LEDOUT_BLINK


def test_set_group_dim_sets_ledout_blink_subset(bus: FakeSMBus) -> None:
    d = TLC59108(bus, address=0x40)
    d.set_group_dim(0.5, channels=[2, 5])
    assert _ledout_bits(bus.mem, 0x0C, 2) == LEDOUT_BLINK
    assert _ledout_bits(bus.mem, 0x0C, 5) == LEDOUT_BLINK
    assert _ledout_bits(bus.mem, 0x0C, 0) == LEDOUT_OFF


def test_set_group_dim_invalid_level_raises(bus: FakeSMBus) -> None:
    d = TLC59108(bus, address=0x40)
    with pytest.raises(ValueError, match="level"):
        d.set_group_dim(-0.1)
    with pytest.raises(ValueError, match="level"):
        d.set_group_dim(1.1)
