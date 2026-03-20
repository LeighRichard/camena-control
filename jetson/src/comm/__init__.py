"""通信模块 - 负责与 STM32 的串口通信"""

from .protocol import (
    Command, Response, CommandType, ResponseType,
    AxisType, StatusCode,
    encode_command, decode_command,
    encode_response, decode_response,
    crc16_calculate, crc16_verify
)
from .manager import CommManager, CommConfig

__all__ = [
    "Command", "Response", "CommandType", "ResponseType",
    "AxisType", "StatusCode",
    "encode_command", "decode_command",
    "encode_response", "decode_response",
    "crc16_calculate", "crc16_verify",
    "CommManager", "CommConfig"
]
