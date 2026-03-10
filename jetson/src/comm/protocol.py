"""
通信协议模块 - 定义帧格式、指令类型和编解码函数

帧格式 v2.0（带序列号）:
  [HEAD][SEQ][LEN][CMD][DATA][CRC16][TAIL]
  - HEAD: 帧头 (0xAA)
  - SEQ: 序列号 (1字节, 0-255 循环)
  - LEN: 数据长度 (CMD + DATA)
  - CMD: 指令类型
  - DATA: 数据内容
  - CRC16: 校验和 (SEQ + LEN + CMD + DATA)
  - TAIL: 帧尾 (0x55)
"""

from dataclasses import dataclass
from enum import IntEnum
from typing import Optional, Tuple
import struct
import threading


# 帧格式常量
FRAME_HEAD = 0xAA
FRAME_TAIL = 0x55
FRAME_MAX_DATA_LEN = 32
FRAME_MIN_LEN = 7  # HEAD + SEQ + LEN + CMD + CHECKSUM(2) + TAIL

# 协议版本
PROTOCOL_VERSION = 2


class CommandType(IntEnum):
    """指令类型"""
    POSITION = 0x01     # 位置控制
    STATUS = 0x02       # 状态查询
    CONFIG = 0x03       # 参数配置
    ESTOP = 0x04        # 急停
    HOME = 0x05         # 归零


class ResponseType(IntEnum):
    """响应类型"""
    POSITION = 0x81
    STATUS = 0x82
    CONFIG = 0x83
    ESTOP = 0x84
    HOME = 0x85


class AxisType(IntEnum):
    """轴类型"""
    PAN = 0x00
    TILT = 0x01
    RAIL = 0x02
    ALL = 0xFF


class StatusCode(IntEnum):
    """状态码"""
    OK = 0x00
    ERROR = 0x01
    BUSY = 0x02
    LIMIT_HIT = 0x03
    ESTOP = 0x04


@dataclass
class Command:
    """指令数据结构"""
    type: CommandType
    axis: AxisType = AxisType.ALL
    value: int = 0
    seq: int = 0  # 序列号

    def __eq__(self, other):
        if not isinstance(other, Command):
            return False
        return (self.type == other.type and 
                self.axis == other.axis and 
                self.value == other.value)


@dataclass
class Response:
    """响应数据结构"""
    type: ResponseType
    status: StatusCode
    pan_pos: int = 0
    tilt_pos: int = 0
    rail_pos: int = 0
    seq: int = 0  # 序列号（回显请求的序列号）


class SequenceManager:
    """
    序列号管理器
    
    线程安全的序列号生成器，用于请求响应匹配
    """
    
    def __init__(self):
        self._seq = 0
        self._lock = threading.Lock()
    
    def next(self) -> int:
        """获取下一个序列号 (0-255 循环)"""
        with self._lock:
            seq = self._seq
            self._seq = (self._seq + 1) & 0xFF
            return seq
    
    def reset(self):
        """重置序列号"""
        with self._lock:
            self._seq = 0


# 全局序列号管理器
_seq_manager = SequenceManager()


def get_next_seq() -> int:
    """获取下一个序列号"""
    return _seq_manager.next()


def reset_seq():
    """重置序列号"""
    _seq_manager.reset()


def crc16_calculate(data: bytes) -> int:
    """
    计算 CRC16-CCITT 校验和
    
    Args:
        data: 待校验的数据
        
    Returns:
        16位校验和
    """
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
    """
    验证 CRC16 校验和
    
    Args:
        data: 待校验的数据
        expected: 期望的校验和
        
    Returns:
        校验是否通过
    """
    return crc16_calculate(data) == expected


def encode_command(cmd: Command, auto_seq: bool = True) -> bytes:
    """
    编码指令为字节帧
    
    帧格式 v2: HEAD(1) + SEQ(1) + LEN(1) + CMD(1) + DATA(N) + CHECKSUM(2) + TAIL(1)
    
    Args:
        cmd: 指令对象
        auto_seq: 是否自动分配序列号
        
    Returns:
        编码后的字节帧
    """
    # 自动分配序列号
    if auto_seq and cmd.seq == 0:
        cmd.seq = get_next_seq()
    
    # 构建数据部分
    if cmd.type == CommandType.POSITION:
        data = struct.pack('<Bi', cmd.axis, cmd.value)
    elif cmd.type == CommandType.STATUS:
        data = b''
    elif cmd.type == CommandType.CONFIG:
        data = struct.pack('<Bi', cmd.axis, cmd.value)
    elif cmd.type == CommandType.ESTOP:
        data = b''
    elif cmd.type == CommandType.HOME:
        data = struct.pack('<B', cmd.axis)
    else:
        data = b''
    
    # 构建帧体 (SEQ + LEN + CMD + DATA)
    frame_body = bytes([cmd.seq, len(data) + 1, cmd.type]) + data
    
    # 计算校验和
    checksum = crc16_calculate(frame_body)
    
    # 组装完整帧
    frame = bytes([FRAME_HEAD]) + frame_body + struct.pack('<H', checksum) + bytes([FRAME_TAIL])
    
    return frame


def decode_command(data: bytes) -> Tuple[Optional[Command], str]:
    """
    解码字节帧为指令
    
    Args:
        data: 字节帧数据
        
    Returns:
        (指令对象, 错误信息) - 成功时错误信息为空字符串
    """
    # 检查最小长度
    if len(data) < FRAME_MIN_LEN:
        return None, "数据长度不足"
    
    # 检查帧头
    if data[0] != FRAME_HEAD:
        return None, "帧头错误"
    
    # 检查帧尾
    if data[-1] != FRAME_TAIL:
        return None, "帧尾错误"
    
    # 解析序列号和长度
    seq = data[1]
    length = data[2]
    expected_len = 1 + 1 + 1 + length + 2 + 1  # HEAD + SEQ + LEN + DATA + CHECKSUM + TAIL
    
    if len(data) != expected_len:
        return None, f"帧长度不匹配: 期望 {expected_len}, 实际 {len(data)}"
    
    # 提取校验和
    checksum_received = struct.unpack('<H', data[-3:-1])[0]
    
    # 验证校验和 (SEQ + LEN + CMD + DATA)
    frame_body = data[1:-3]
    if not crc16_verify(frame_body, checksum_received):
        return None, "校验和错误"
    
    # 解析指令类型
    cmd_type = CommandType(data[3])
    
    # 解析数据
    cmd_data = data[4:-3]
    
    if cmd_type == CommandType.POSITION:
        axis, value = struct.unpack('<Bi', cmd_data)
        return Command(type=cmd_type, axis=AxisType(axis), value=value, seq=seq), ""
    elif cmd_type == CommandType.STATUS:
        return Command(type=cmd_type, seq=seq), ""
    elif cmd_type == CommandType.CONFIG:
        axis, value = struct.unpack('<Bi', cmd_data)
        return Command(type=cmd_type, axis=AxisType(axis), value=value, seq=seq), ""
    elif cmd_type == CommandType.ESTOP:
        return Command(type=cmd_type, seq=seq), ""
    elif cmd_type == CommandType.HOME:
        axis = cmd_data[0]
        return Command(type=cmd_type, axis=AxisType(axis), seq=seq), ""
    else:
        return None, f"未知指令类型: {cmd_type}"


def encode_response(rsp: Response) -> bytes:
    """
    编码响应为字节帧
    
    Args:
        rsp: 响应对象
        
    Returns:
        编码后的字节帧
    """
    # 构建数据部分
    if rsp.type == ResponseType.STATUS:
        data = struct.pack('<Biii', rsp.status, rsp.pan_pos, rsp.tilt_pos, rsp.rail_pos)
    else:
        data = struct.pack('<B', rsp.status)
    
    # 构建帧体 (SEQ + LEN + CMD + DATA)
    frame_body = bytes([rsp.seq, len(data) + 1, rsp.type]) + data
    
    # 计算校验和
    checksum = crc16_calculate(frame_body)
    
    # 组装完整帧
    frame = bytes([FRAME_HEAD]) + frame_body + struct.pack('<H', checksum) + bytes([FRAME_TAIL])
    
    return frame


def decode_response(data: bytes) -> Tuple[Optional[Response], str]:
    """
    解码字节帧为响应
    
    Args:
        data: 字节帧数据
        
    Returns:
        (响应对象, 错误信息) - 成功时错误信息为空字符串
    """
    # 检查最小长度
    if len(data) < FRAME_MIN_LEN:
        return None, "数据长度不足"
    
    # 检查帧头帧尾
    if data[0] != FRAME_HEAD:
        return None, "帧头错误"
    if data[-1] != FRAME_TAIL:
        return None, "帧尾错误"
    
    # 解析序列号和长度
    seq = data[1]
    length = data[2]
    expected_len = 1 + 1 + 1 + length + 2 + 1  # HEAD + SEQ + LEN + DATA + CHECKSUM + TAIL
    
    if len(data) != expected_len:
        return None, f"帧长度不匹配"
    
    # 验证校验和
    checksum_received = struct.unpack('<H', data[-3:-1])[0]
    frame_body = data[1:-3]  # SEQ + LEN + CMD + DATA
    if not crc16_verify(frame_body, checksum_received):
        return None, "校验和错误"
    
    # 解析响应类型
    rsp_type = ResponseType(data[3])
    rsp_data = data[4:-3]
    
    if rsp_type == ResponseType.STATUS:
        status, pan, tilt, rail = struct.unpack('<Biii', rsp_data)
        return Response(type=rsp_type, status=StatusCode(status), 
                       pan_pos=pan, tilt_pos=tilt, rail_pos=rail, seq=seq), ""
    else:
        status = rsp_data[0]
        return Response(type=rsp_type, status=StatusCode(status), seq=seq), ""
