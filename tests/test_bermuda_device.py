"""
Tests for BermudaDevice class in bermuda_device.py.
"""

import logging
import pytest
from unittest.mock import MagicMock, patch
from homeassistant.components.bluetooth import BaseHaScanner, BaseHaRemoteScanner
from custom_components.bermuda.bermuda_device import BermudaDevice
from bluetooth_data_tools import monotonic_time_coarse
from custom_components.bermuda.const import (
    CONF_SCANNER_COORDS,
    ICON_DEFAULT_AREA,
    ICON_DEFAULT_FLOOR,
)
from .const import MOCK_OPTIONS_GLOBALS


@pytest.fixture
def mock_coordinator():
    """Fixture for mocking BermudaDataUpdateCoordinator."""
    coordinator = MagicMock()
    coordinator.options = MOCK_OPTIONS_GLOBALS.copy()
    coordinator.hass_version_min_2025_4 = True
    return coordinator


@pytest.fixture
def mock_scanner():
    """Fixture for mocking BaseHaScanner."""
    scanner = MagicMock(spec=BaseHaScanner)
    scanner.time_since_last_detection.return_value = 5.0
    scanner.source = "mock_source"
    return scanner


@pytest.fixture
def mock_remote_scanner():
    """Fixture for mocking BaseHaRemoteScanner."""
    scanner = MagicMock(spec=BaseHaRemoteScanner)
    scanner.time_since_last_detection.return_value = 5.0
    scanner.source = "mock_source"
    return scanner


@pytest.fixture
def bermuda_device(mock_coordinator):
    """Fixture for creating a BermudaDevice instance."""
    return BermudaDevice(address="AA:BB:CC:DD:EE:FF", coordinator=mock_coordinator)


@pytest.fixture
def bermuda_scanner(mock_coordinator):
    """Fixture for creating a BermudaDevice Scanner instance."""
    return BermudaDevice(address="11:22:33:44:55:66", coordinator=mock_coordinator)


def test_bermuda_device_initialization(bermuda_device):
    """Test BermudaDevice initialization."""
    assert bermuda_device.address == "aa:bb:cc:dd:ee:ff"
    assert bermuda_device.name.startswith("bermuda_")
    assert bermuda_device.area_icon == ICON_DEFAULT_AREA
    assert bermuda_device.floor_icon == ICON_DEFAULT_FLOOR
    assert bermuda_device.zone == "not_home"
    assert bermuda_device.scanner_distance == {}
    assert bermuda_device.scanner_rssi == {}
    assert bermuda_device.position is None


def test_async_as_scanner_init(bermuda_scanner, mock_scanner):
    """Test async_as_scanner_init method."""
    bermuda_scanner.async_as_scanner_init(mock_scanner)
    assert bermuda_scanner._hascanner == mock_scanner
    assert bermuda_scanner.is_scanner is True
    assert bermuda_scanner.is_remote_scanner is False


def test_async_as_scanner_update(bermuda_scanner, mock_scanner):
    """Test async_as_scanner_update method."""
    bermuda_scanner.async_as_scanner_update(mock_scanner)
    assert bermuda_scanner.last_seen > 0


def test_async_as_scanner_get_stamp(bermuda_scanner, mock_scanner, mock_remote_scanner):
    """Test async_as_scanner_get_stamp method."""
    bermuda_scanner.async_as_scanner_init(mock_scanner)
    bermuda_scanner.stamps = {"AA:BB:CC:DD:EE:FF": 123.45}

    stamp = bermuda_scanner.async_as_scanner_get_stamp("AA:bb:CC:DD:EE:FF")
    assert stamp is None

    bermuda_scanner.async_as_scanner_init(mock_remote_scanner)

    stamp = bermuda_scanner.async_as_scanner_get_stamp("AA:bb:CC:DD:EE:FF")
    assert stamp == 123.45

    stamp = bermuda_scanner.async_as_scanner_get_stamp("AA:BB:CC:DD:E1:FF")
    assert stamp is None


def test_make_name(bermuda_device):
    """Test make_name method."""
    bermuda_device.name_by_user = "Custom Name"
    name = bermuda_device.make_name()
    assert name == "Custom Name"
    assert bermuda_device.name == "Custom Name"


def test_process_advertisement(bermuda_device, bermuda_scanner):
    """Test process_advertisement method."""
    advertisement_data = MagicMock()
    advertisement_data.rssi = -70
    advertisement_data.tx_power = -20
    advertisement_data.local_name = "test"
    advertisement_data.manufacturer_data = {}
    advertisement_data.service_data = {}
    advertisement_data.service_uuids = []
    bermuda_device.process_advertisement(bermuda_scanner, advertisement_data)
    assert len(bermuda_device.adverts) == 1
    assert bermuda_scanner.address in bermuda_device.scanner_rssi
    assert bermuda_device.scanner_rssi[bermuda_scanner.address] == -70
    assert bermuda_scanner.address in bermuda_device.scanner_distance
    assert bermuda_scanner.address in bermuda_device.scanner_distance_raw
    assert bermuda_scanner.address in bermuda_device.scanner_last_update


# def test_process_manufacturer_data(bermuda_device):
#     """Test process_manufacturer_data method."""
#     mock_advert = MagicMock()
#     mock_advert.service_uuids = ["0000abcd-0000-1000-8000-00805f9b34fb"]
#     mock_advert.manufacturer_data = [{"004C": b"\x02\x15"}]
#     bermuda_device.process_manufacturer_data(mock_advert)
#     assert bermuda_device.manufacturer == "Apple Inc."


def test_to_dict(bermuda_device):
    """Test to_dict method."""
    device_dict = bermuda_device.to_dict()
    assert isinstance(device_dict, dict)
    assert device_dict["address"] == "aa:bb:cc:dd:ee:ff"
    assert "scanner_rssi" in device_dict
    assert "scanner_distance" in device_dict
    assert "scanner_distance_raw" in device_dict


def test_repr(bermuda_device):
    """Test __repr__ method."""
    repr_str = repr(bermuda_device)
    assert repr_str == f"{bermuda_device.name} [{bermuda_device.address}]"


def test_compute_position(bermuda_device):
    """Test compute_position with three scanners."""
    bermuda_device.options[CONF_SCANNER_COORDS] = {
        "s1": [0.0, 0.0],
        "s2": [2.0, 0.0],
        "s3": [0.0, 2.0],
    }
    now = monotonic_time_coarse()
    d = 2**0.5
    bermuda_device.scanner_distance = {"s1": d, "s2": d, "s3": d}
    bermuda_device.scanner_last_update = {"s1": now, "s2": now, "s3": now}

    pos = bermuda_device.compute_position(bermuda_device.options[CONF_SCANNER_COORDS])
    assert pos is not None
    x, y = pos
    assert pytest.approx(x, rel=1e-3) == 1.0
    assert pytest.approx(y, rel=1e-3) == 1.0


def test_compute_position_insufficient_scanners_warns(bermuda_device, caplog):
    """Test warning when fewer than three scanners are available."""
    bermuda_device.options[CONF_SCANNER_COORDS] = {
        "s1": [0.0, 0.0],
        "s2": [2.0, 0.0],
    }
    now = monotonic_time_coarse()
    bermuda_device.scanner_distance = {"s1": 1.0, "s2": 1.0}
    bermuda_device.scanner_last_update = {"s1": now, "s2": now}

    with caplog.at_level(logging.WARNING):
        pos = bermuda_device.compute_position(bermuda_device.options[CONF_SCANNER_COORDS])
    assert pos is None
    assert any("Triangulation requires at least 3 scanners" in r.message for r in caplog.records)
