"""
CommManager 串口调试日志测试
"""

import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from comm.manager import CommConfig, CommManager
from comm.protocol import (
    AxisType,
    Command,
    CommandType,
    ConfigParamId,
    Response,
    ResponseType,
    StatusCode,
    encode_response,
)


class FakeSerial:
    """用于日志测试的最小串口桩。"""

    def __init__(self, rx_bytes: bytes = b""):
        self._rx = bytearray(rx_bytes)
        self.is_open = True
        self.written = []

    @property
    def in_waiting(self):
        return len(self._rx)

    def write(self, data: bytes):
        self.written.append(bytes(data))
        return len(data)

    def read(self, size: int = 1) -> bytes:
        if size <= 0 or not self._rx:
            return b""

        data = self._rx[:size]
        del self._rx[:size]
        return bytes(data)


def test_trace_protocol_logs_tx_and_rx(caplog):
    """开启 trace_protocol 后，应记录匹配的发送与响应日志。"""
    response_frame = encode_response(
        Response(
            type=ResponseType.STATUS,
            status=StatusCode.OK,
            pan_pos=100,
            tilt_pos=-50,
            rail_pos=2500,
            seq=7,
        )
    )
    manager = CommManager(
        CommConfig(
            timeout=0.05,
            retry_count=1,
            trace_protocol=True,
        )
    )
    manager._serial = FakeSerial(rx_bytes=response_frame)

    caplog.set_level(logging.INFO, logger="comm.manager")

    response, error = manager.send_command(
        Command(type=CommandType.STATUS, seq=7),
        wait_response=True,
    )

    assert error == ""
    assert response is not None
    assert response.seq == 7
    assert "[串口 TX]" in caplog.text
    assert "cmd=status" in caplog.text
    assert "seq=7" in caplog.text
    assert "[串口 RX]" in caplog.text
    assert "rsp=status" in caplog.text
    assert "status=ok" in caplog.text


def test_trace_protocol_logs_config_param_details(caplog):
    """CONFIG 命令的 trace 日志应展开参数 ID 和原始值。"""
    manager = CommManager(
        CommConfig(
            retry_count=1,
            trace_protocol=True,
        )
    )
    manager._serial = FakeSerial()

    caplog.set_level(logging.INFO, logger="comm.manager")

    response, error = manager.send_config(
        AxisType.RAIL,
        ConfigParamId.RAIL_MAX_LIMIT,
        50000,
        wait_response=False,
    )

    assert response is None
    assert error == ""
    assert "[串口 TX]" in caplog.text
    assert "cmd=config" in caplog.text
    assert "axis=rail" in caplog.text
    assert "param=rail_max_limit" in caplog.text
    assert "raw_value=50000" in caplog.text
    assert "signed_value=" in caplog.text


def test_trace_frames_hex_logs_raw_tx_and_rx_frames(caplog):
    """开启 trace_frames_hex 后，应记录原始帧十六进制内容。"""
    response_frame = encode_response(
        Response(
            type=ResponseType.STOP,
            status=StatusCode.OK,
            seq=3,
        )
    )
    manager = CommManager(
        CommConfig(
            timeout=0.05,
            retry_count=1,
            trace_frames_hex=True,
        )
    )
    manager._serial = FakeSerial(rx_bytes=response_frame)

    caplog.set_level(logging.INFO, logger="comm.manager")

    response, error = manager.send_command(
        Command(type=CommandType.STOP, seq=3),
        wait_response=True,
    )

    assert error == ""
    assert response is not None
    assert "[串口 TX-FRAME]" in caplog.text
    assert "[串口 RX-FRAME]" in caplog.text
    assert response_frame.hex(" ") in caplog.text
    assert "aa" in caplog.text


def test_trace_frames_hex_logs_invalid_rx_frame(caplog):
    """无效响应帧在开启 trace_frames_hex 时也应被记录。"""
    invalid_frame = bytes.fromhex("aa 05 02 87 00 00 00 55")
    manager = CommManager(
        CommConfig(
            timeout=0.02,
            retry_count=1,
            trace_frames_hex=True,
        )
    )
    manager._serial = FakeSerial(rx_bytes=invalid_frame)

    caplog.set_level(logging.INFO, logger="comm.manager")

    response, error = manager.send_command(
        Command(type=CommandType.STATUS, seq=1),
        wait_response=True,
    )

    assert response is None
    assert error != ""
    assert "[串口 RX-FRAME-INVALID]" in caplog.text
    assert invalid_frame.hex(" ") in caplog.text


def test_trace_history_keeps_recent_tx_rx_records():
    """诊断历史应保留最近的 TX/RX 结构化记录。"""
    response_frame = encode_response(
        Response(
            type=ResponseType.STATUS,
            status=StatusCode.OK,
            pan_pos=12,
            tilt_pos=34,
            rail_pos=56,
            seq=9,
        )
    )
    manager = CommManager(
        CommConfig(
            timeout=0.05,
            retry_count=1,
            trace_history_size=10,
        )
    )
    manager._serial = FakeSerial(rx_bytes=response_frame)

    response, error = manager.send_command(
        Command(type=CommandType.STATUS, seq=9),
        wait_response=True,
    )

    assert error == ""
    assert response is not None

    diagnostics = manager.get_trace_diagnostics(limit=10)
    assert diagnostics["history_capacity"] == 10
    assert diagnostics["history_count"] == 2
    assert diagnostics["records"][0]["source"] == "RX"
    assert diagnostics["records"][0]["status"] == "ok"
    assert diagnostics["records"][1]["source"] == "TX"
    assert diagnostics["records"][1]["command"] == "status"

    cleared = manager.clear_trace_history()
    assert cleared == 2
    assert manager.get_trace_diagnostics(limit=10)["history_count"] == 0
