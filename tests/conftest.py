"""Pytest fixtures for hardware integration tests."""

from __future__ import annotations

import os

import pytest

from tlc591xx import TLC59108, TLC59116, TLC591xx


def _parse_address(raw: str | None, default: int) -> int:
    if raw is None or raw == "":
        return default
    return int(raw.strip(), 0)


def _device_class_and_default_addr() -> tuple[type[TLC591xx], int]:
    model = os.environ.get("TLC591XX_MODEL", "59108").strip().lower()
    if model in ("59116", "16", "tlc59116"):
        return TLC59116, 0x60
    if model in ("59108", "08", "tlc59108"):
        return TLC59108, 0x40
    pytest.fail(
        f"Unknown TLC591XX_MODEL={model!r}; use 59116 or 59108",
    )


@pytest.fixture
def hardware_params() -> tuple[int, int, type[TLC591xx]]:
    """(bus_number, i2c_address, device_class). Skips if TLC591XX_I2C_BUS is unset."""
    bus_raw = os.environ.get("TLC591XX_I2C_BUS")
    if bus_raw is None or bus_raw.strip() == "":
        pytest.skip(
            "Hardware tests skipped: set TLC591XX_I2C_BUS (e.g. 1 for /dev/i2c-1)",
        )
    bus_num = int(bus_raw.strip(), 0)
    cls, default_addr = _device_class_and_default_addr()
    addr = _parse_address(os.environ.get("TLC591XX_ADDRESS"), default_addr)
    return bus_num, addr, cls


@pytest.fixture
def tlc591xx_device(hardware_params: tuple[int, int, type[TLC591xx]]) -> TLC591xx:
    bus_num, addr, cls = hardware_params
    dev = cls(bus_num, address=addr)
    try:
        yield dev
    finally:
        dev.close()
