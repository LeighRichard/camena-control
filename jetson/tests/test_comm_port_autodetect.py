import os
import sys
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from comm.manager import CommConfig, CommManager


def test_connect_falls_back_to_detected_port_when_configured_port_is_missing():
    pytest.importorskip("serial")

    manager = CommManager(
        CommConfig(
            port="/dev/ttyUSB0",
            auto_reconnect=False,
            heartbeat_interval=0,
        )
    )

    opened_ports = []

    def serial_factory(*, port, baudrate, timeout):
        opened_ports.append(port)
        if port == "/dev/ttyUSB0":
            raise OSError("missing")

        handle = Mock()
        handle.is_open = True
        handle.close = Mock()
        return handle

    detected_ports = [
        SimpleNamespace(
            device="/dev/ttyACM0",
            description="STM32 Virtual COM Port",
            manufacturer="STMicroelectronics",
            hwid="USB VID:PID=0483:5740",
        )
    ]

    with patch("serial.Serial", side_effect=serial_factory), patch(
        "serial.tools.list_ports.comports",
        return_value=detected_ports,
    ):
        assert manager.connect() is True

    assert opened_ports[:2] == ["/dev/ttyUSB0", "/dev/ttyACM0"]
    assert manager.get_connected_port() == "/dev/ttyACM0"

    manager.disconnect()
