"""
Integration tests against a real TLC591xx on I²C.

Run on the machine wired to the chip, with the bus device available (e.g. ``/dev/i2c-1``):

.. code-block:: shell

   export TLC591XX_I2C_BUS=1
   # optional: TLC591XX_ADDRESS=0x60  TLC591XX_MODEL=59116
   pytest -m hardware -v

If ``TLC591XX_I2C_BUS`` is not set, tests are skipped so CI without hardware still passes.
"""

from __future__ import annotations

import pytest

from tlc591xx import (
    LEDOUT_DIM,
    LEDOUT_OFF,
    LEDOUT_ON,
    REG59108_EFLAG,
    REG_EFLAG1,
    REG_EFLAG2,
    REG_MODE1,
    REG_MODE2,
    REG_PWM0,
    TLC59108,
    TLC59116,
    TLC591xx,
)


def _ledout_base(device: TLC591xx) -> int:
    if isinstance(device, TLC59116):
        return 0x14
    if isinstance(device, TLC59108):
        return 0x0C
    raise TypeError(f"unsupported device type: {type(device)!r}")


def _ledout_register_count(num_leds: int) -> int:
    return (num_leds + 3) // 4


def _ledout_state(device: TLC591xx, channel: int) -> int:
    base = _ledout_base(device)
    reg = base + (channel >> 2)
    shift = (channel % 4) * 2
    b = device.read_register(reg)
    return (b >> shift) & 0x3


pytestmark = pytest.mark.hardware


def test_init_mode_registers(tlc591xx_device: TLC591xx) -> None:
    """Constructor should program MODE1 / MODE2 like the bring-up sequence."""
    assert tlc591xx_device.read_register(REG_MODE1) == 0x01
    assert tlc591xx_device.read_register(REG_MODE2) == 0x00


def test_pwm_readback_after_set_brightness(tlc591xx_device: TLC591xx) -> None:
    tlc591xx_device.set_all_off()
    duty = 170
    tlc591xx_device.set_brightness(0, duty)
    assert tlc591xx_device.read_register(REG_PWM0) == duty


def test_set_all_brightness_pwm_block(tlc591xx_device: TLC591xx) -> None:
    n = tlc591xx_device.num_leds
    values = [(17 * i) % 255 or 1 for i in range(n)]
    # avoid all 255 so every channel exercises DIM + PWM path in set_all_brightness
    values[-1] = 42
    tlc591xx_device.set_all_brightness(values)
    for ch, v in enumerate(values):
        assert tlc591xx_device.read_register(REG_PWM0 + ch) == v


def test_set_all_off_clears_ledout(tlc591xx_device: TLC591xx) -> None:
    tlc591xx_device.set_brightness(0, 255)
    tlc591xx_device.set_brightness(min(3, tlc591xx_device.num_leds - 1), 128)
    tlc591xx_device.set_all_off()
    base = _ledout_base(tlc591xx_device)
    for i in range(_ledout_register_count(tlc591xx_device.num_leds)):
        assert tlc591xx_device.read_register(base + i) == 0x00


def test_read_errors_returns_two_bytes(tlc591xx_device: TLC591xx) -> None:
    e1, e2 = tlc591xx_device.read_errors()
    assert 0 <= e1 <= 0xFF
    assert 0 <= e2 <= 0xFF


def test_read_errors_matches_individual_registers(tlc591xx_device: TLC591xx) -> None:
    e1, e2 = tlc591xx_device.read_errors()
    if isinstance(tlc591xx_device, TLC59108):
        assert e2 == 0
        assert tlc591xx_device.read_register(REG59108_EFLAG) == e1
    else:
        assert tlc591xx_device.read_register(REG_EFLAG1) == e1
        assert tlc591xx_device.read_register(REG_EFLAG2) == e2


def test_device_properties_match_env(
    tlc591xx_device: TLC591xx,
    hardware_params: tuple[int, int, type[TLC591xx]],
) -> None:
    _bus_num, addr, cls = hardware_params
    assert tlc591xx_device.address == addr
    assert isinstance(tlc591xx_device, cls)
    assert tlc591xx_device.num_leds == (16 if cls is TLC59116 else 8)


def test_ledout_encoding_for_off_dim_on(tlc591xx_device: TLC591xx) -> None:
    ch = min(2, tlc591xx_device.num_leds - 1)
    tlc591xx_device.set_all_off()
    tlc591xx_device.set_brightness(ch, 0)
    assert _ledout_state(tlc591xx_device, ch) == LEDOUT_OFF
    tlc591xx_device.set_brightness(ch, 100)
    assert _ledout_state(tlc591xx_device, ch) == LEDOUT_DIM
    assert tlc591xx_device.read_register(REG_PWM0 + ch) == 100
    tlc591xx_device.set_brightness(ch, 255)
    assert _ledout_state(tlc591xx_device, ch) == LEDOUT_ON


def test_read_register_rejects_past_chip_max(tlc591xx_device: TLC591xx) -> None:
    if isinstance(tlc591xx_device, TLC59108):
        bad = REG59108_EFLAG + 1
    else:
        bad = REG_EFLAG2 + 1
    with pytest.raises(ValueError, match="out of range"):
        tlc591xx_device.read_register(bad)


def test_set_all_brightness_all_on_then_all_off(tlc591xx_device: TLC591xx) -> None:
    n = tlc591xx_device.num_leds
    tlc591xx_device.set_all_brightness([255] * n)
    for ch in range(n):
        assert _ledout_state(tlc591xx_device, ch) == LEDOUT_ON
    tlc591xx_device.set_all_brightness([0] * n)
    for ch in range(n):
        assert _ledout_state(tlc591xx_device, ch) == LEDOUT_OFF


def test_context_manager_can_reopen_i2c_bus(
    hardware_params: tuple[int, int, type[TLC591xx]],
) -> None:
    """Owning SMBus is closed after ``with``; a new instance must be able to talk again."""
    bus_num, addr, cls = hardware_params
    with cls(bus_num, address=addr) as d:
        assert d.read_register(REG_MODE1) == 0x01
    with cls(bus_num, address=addr) as d2:
        d2.set_all_off()
        assert d2.read_register(REG_MODE2) == 0x00
