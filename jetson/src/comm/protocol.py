"""
Jetson 与 STM32 共用的串口协议定义。

当前帧格式（v2.0）:
    [HEAD][SEQ][LEN][CMD][DATA][CRC16][TAIL]
"""

from dataclasses import dataclass
from enum import IntEnum
from typing import Optional, Tuple
import struct
import threading


FRAME_HEAD = 0xAA
FRAME_TAIL = 0x55
FRAME_MAX_DATA_LEN = 32
FRAME_MIN_LEN = 7  # HEAD + SEQ + LEN + CMD + CRC16 + TAIL

PROTOCOL_VERSION = 2


class CommandType(IntEnum):
    """Jetson 发送给 STM32 的命令 ID。"""

    POSITION = 0x01
    STATUS = 0x02
    CONFIG = 0x03
    ESTOP = 0x04
    HOME = 0x05
    SET_VELOCITY = 0x06
    STOP = 0x07
    MOVE_ABSOLUTE = 0x08


class ResponseType(IntEnum):
    """STM32 返回给 Jetson 的响应 ID。"""

    POSITION = 0x81
    STATUS = 0x82
    CONFIG = 0x83
    ESTOP = 0x84
    HOME = 0x85
    SET_VELOCITY = 0x86
    STOP = 0x87
    MOVE_ABSOLUTE = 0x88


class AxisType(IntEnum):
    """协议中使用的轴标识。"""

    PAN = 0x00
    TILT = 0x01
    RAIL = 0x02
    ALL = 0xFF


class StatusCode(IntEnum):
    """通用响应状态码。"""

    OK = 0x00
    ERROR = 0x01
    BUSY = 0x02
    LIMIT_HIT = 0x03
    ESTOP = 0x04


class ConfigParamId(IntEnum):
    """与 STM32 固件共享的 CONFIG 参数 ID。"""

    MAX_VELOCITY = 0x0001
    MAX_ACCEL = 0x0002
    PID_P = 0x0003
    PID_I = 0x0004
    PID_D = 0x0005
    WATCHDOG_TIMEOUT_MS = 0x0010
    WATCHDOG_ENABLE = 0x0011
    PAN_MIN_LIMIT = 0x0020
    PAN_MAX_LIMIT = 0x0021
    TILT_MIN_LIMIT = 0x0022
    TILT_MAX_LIMIT = 0x0023
    RAIL_MIN_LIMIT = 0x0024
    RAIL_MAX_LIMIT = 0x0025


@dataclass
class Command:
    """命令对象。"""

    type: CommandType
    axis: AxisType = AxisType.ALL
    value: int = 0
    seq: int = 0
    data: Optional[dict] = None

    def __eq__(self, other):
        if not isinstance(other, Command):
            return False
        return (
            self.type == other.type
            and self.axis == other.axis
            and self.value == other.value
            and self.data == other.data
        )

    @property
    def cmd_type(self):
        """兼容旧调用方使用的别名属性。"""

        return self.type


@dataclass
class Response:
    """响应对象。"""

    type: ResponseType
    status: StatusCode
    pan_pos: int = 0
    tilt_pos: int = 0
    rail_pos: int = 0
    seq: int = 0


class SequenceManager:
    """线程安全的序列号生成器，用于请求与响应匹配。"""

    def __init__(self):
        self._seq = 0
        self._lock = threading.Lock()

    def next(self) -> int:
        with self._lock:
            seq = self._seq
            self._seq = (self._seq + 1) & 0xFF
            return seq

    def reset(self):
        with self._lock:
            self._seq = 0


_seq_manager = SequenceManager()


def get_next_seq() -> int:
    """获取下一个全局序列号。"""

    return _seq_manager.next()


def reset_seq():
    """重置全局序列号计数器。"""

    _seq_manager.reset()


def config_param_from_value(packed_value: int) -> ConfigParamId:
    """解析 CONFIG 负载高 16 位中的参数 ID。"""

    return ConfigParamId((packed_value >> 16) & 0xFFFF)


def config_raw_value(packed_value: int) -> int:
    """按无符号整数解析 CONFIG 负载低 16 位的值。"""

    return packed_value & 0xFFFF


def config_signed_value(packed_value: int) -> int:
    """按有符号整数解析 CONFIG 负载低 16 位的值。"""

    raw_value = config_raw_value(packed_value)
    if raw_value & 0x8000:
        return raw_value - 0x10000
    return raw_value


def config_pack_value(param_id: ConfigParamId, value: int) -> int:
    """将参数 ID 与 16 位参数值打包成 32 位 CONFIG 字段。"""

    return ((int(param_id) & 0xFFFF) << 16) | (value & 0xFFFF)


def crc16_calculate(data: bytes) -> int:
    """计算字节序列的 CRC16-CCITT 校验值。"""

    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc <<= 1
            crc &= 0xFFFF
    return crc


def crc16_verify(data: bytes, expected: int) -> bool:
    """校验 CRC16-CCITT。"""

    return crc16_calculate(data) == expected


def _encode_axis_and_value(axis: AxisType, value: int) -> bytes:
    return struct.pack("<Bi", int(axis), int(value))


def encode_command(cmd: Command, auto_seq: bool = True) -> bytes:
    """
    将命令编码为协议帧。

    帧格式:
        HEAD + SEQ + LEN + CMD + DATA + CRC16 + TAIL
    """

    if auto_seq and cmd.seq == 0:
        cmd.seq = get_next_seq()

    if cmd.type in (
        CommandType.POSITION,
        CommandType.CONFIG,
        CommandType.SET_VELOCITY,
        CommandType.MOVE_ABSOLUTE,
    ):
        data = _encode_axis_and_value(cmd.axis, cmd.value)
    elif cmd.type == CommandType.HOME:
        data = struct.pack("<B", int(cmd.axis))
    elif cmd.type == CommandType.STOP:
        data = b"" if cmd.axis == AxisType.ALL else struct.pack("<B", int(cmd.axis))
    else:
        data = b""

    frame_body = bytes([cmd.seq, len(data) + 1, int(cmd.type)]) + data
    checksum = crc16_calculate(frame_body)
    return bytes([FRAME_HEAD]) + frame_body + struct.pack("<H", checksum) + bytes([FRAME_TAIL])


def decode_command(data: bytes) -> Tuple[Optional[Command], str]:
    """Decode a command frame."""

    if len(data) < FRAME_MIN_LEN:
        return None, "frame too short"
    if data[0] != FRAME_HEAD:
        return None, "invalid frame head"
    if data[-1] != FRAME_TAIL:
        return None, "invalid frame tail"

    seq = data[1]
    length = data[2]
    expected_len = 1 + 1 + 1 + length + 2 + 1
    if len(data) != expected_len:
        return None, f"frame length mismatch: expected {expected_len}, got {len(data)}"

    checksum_received = struct.unpack("<H", data[-3:-1])[0]
    frame_body = data[1:-3]
    if not crc16_verify(frame_body, checksum_received):
        return None, "crc mismatch"

    try:
        cmd_type = CommandType(data[3])
    except ValueError:
        return None, f"unknown command type: {data[3]}"

    cmd_data = data[4:-3]

    if cmd_type in (
        CommandType.POSITION,
        CommandType.CONFIG,
        CommandType.SET_VELOCITY,
        CommandType.MOVE_ABSOLUTE,
    ):
        if len(cmd_data) != 5:
            return None, "invalid axis/value payload"
        axis, value = struct.unpack("<Bi", cmd_data)
        return Command(type=cmd_type, axis=AxisType(axis), value=value, seq=seq), ""

    if cmd_type == CommandType.STATUS:
        return Command(type=cmd_type, seq=seq), ""

    if cmd_type == CommandType.ESTOP:
        return Command(type=cmd_type, seq=seq), ""

    if cmd_type == CommandType.HOME:
        if len(cmd_data) != 1:
            return None, "invalid home payload"
        return Command(type=cmd_type, axis=AxisType(cmd_data[0]), seq=seq), ""

    if cmd_type == CommandType.STOP:
        if len(cmd_data) == 0:
            return Command(type=cmd_type, seq=seq), ""
        if len(cmd_data) != 1:
            return None, "invalid stop payload"
        return Command(type=cmd_type, axis=AxisType(cmd_data[0]), seq=seq), ""

    return None, f"unsupported command type: {cmd_type}"


def encode_response(rsp: Response) -> bytes:
    """Encode a response frame."""

    if rsp.type == ResponseType.STATUS:
        data = struct.pack("<Biii", int(rsp.status), rsp.pan_pos, rsp.tilt_pos, rsp.rail_pos)
    else:
        data = struct.pack("<B", int(rsp.status))

    frame_body = bytes([rsp.seq, len(data) + 1, int(rsp.type)]) + data
    checksum = crc16_calculate(frame_body)
    return bytes([FRAME_HEAD]) + frame_body + struct.pack("<H", checksum) + bytes([FRAME_TAIL])


def decode_response(data: bytes) -> Tuple[Optional[Response], str]:
    """Decode a response frame."""

    if len(data) < FRAME_MIN_LEN:
        return None, "frame too short"
    if data[0] != FRAME_HEAD:
        return None, "invalid frame head"
    if data[-1] != FRAME_TAIL:
        return None, "invalid frame tail"

    seq = data[1]
    length = data[2]
    expected_len = 1 + 1 + 1 + length + 2 + 1
    if len(data) != expected_len:
        return None, f"frame length mismatch: expected {expected_len}, got {len(data)}"

    checksum_received = struct.unpack("<H", data[-3:-1])[0]
    frame_body = data[1:-3]
    if not crc16_verify(frame_body, checksum_received):
        return None, "crc mismatch"

    try:
        rsp_type = ResponseType(data[3])
    except ValueError:
        return None, f"unknown response type: {data[3]}"

    rsp_data = data[4:-3]

    if rsp_type == ResponseType.STATUS:
        if len(rsp_data) != 13:
            return None, "invalid status payload"
        status, pan, tilt, rail = struct.unpack("<Biii", rsp_data)
        return (
            Response(
                type=rsp_type,
                status=StatusCode(status),
                pan_pos=pan,
                tilt_pos=tilt,
                rail_pos=rail,
                seq=seq,
            ),
            "",
        )

    if len(rsp_data) != 1:
        return None, "invalid response payload"

    return Response(type=rsp_type, status=StatusCode(rsp_data[0]), seq=seq), ""
