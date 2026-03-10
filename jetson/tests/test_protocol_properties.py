"""
通信协议属性测试

Property 1: 通信协议编解码往返一致性
Property 2: 校验和完整性验证

验证需求: 3.3, 3.5
"""

import pytest
from hypothesis import given, strategies as st, settings, assume

import sys
sys.path.insert(0, 'src')

from comm.protocol import (
    Command, Response, CommandType, ResponseType,
    AxisType, StatusCode,
    encode_command, decode_command,
    encode_response, decode_response,
    crc16_calculate, crc16_verify
)


# ==================== 生成器策略 ====================

@st.composite
def command_strategy(draw):
    """生成随机 Command 对象"""
    cmd_type = draw(st.sampled_from(list(CommandType)))
    axis = draw(st.sampled_from(list(AxisType)))
    # 使用 32 位有符号整数范围
    value = draw(st.integers(min_value=-2147483648, max_value=2147483647))
    return Command(type=cmd_type, axis=axis, value=value)


@st.composite
def response_strategy(draw):
    """生成随机 Response 对象"""
    rsp_type = draw(st.sampled_from(list(ResponseType)))
    status = draw(st.sampled_from(list(StatusCode)))
    pan = draw(st.integers(min_value=-2147483648, max_value=2147483647))
    tilt = draw(st.integers(min_value=-2147483648, max_value=2147483647))
    rail = draw(st.integers(min_value=-2147483648, max_value=2147483647))
    return Response(type=rsp_type, status=status, pan_pos=pan, tilt_pos=tilt, rail_pos=rail)


# ==================== Property 1: 往返一致性 ====================

@given(cmd=command_strategy())
@settings(max_examples=100)
def test_command_roundtrip(cmd: Command):
    """
    Property 1: 通信协议编解码往返一致性 (Command)
    
    *For any* valid Command object, encoding then decoding should produce
    an equivalent Command object.
    
    **Validates: Requirements 3.3, 3.5**
    """
    # 编码
    encoded = encode_command(cmd)
    
    # 解码
    decoded, error = decode_command(encoded)
    
    # 验证往返一致性
    assert error == "", f"解码失败: {error}"
    assert decoded is not None, "解码结果为空"
    assert decoded.type == cmd.type, f"类型不匹配: {decoded.type} != {cmd.type}"
    
    # 根据指令类型验证字段
    if cmd.type == CommandType.POSITION:
        # POSITION 指令携带 axis 和 value
        assert decoded.axis == cmd.axis, f"轴不匹配: {decoded.axis} != {cmd.axis}"
        assert decoded.value == cmd.value, f"值不匹配: {decoded.value} != {cmd.value}"
    elif cmd.type == CommandType.CONFIG:
        # CONFIG 指令携带 axis 和 value
        assert decoded.axis == cmd.axis, f"轴不匹配: {decoded.axis} != {cmd.axis}"
        assert decoded.value == cmd.value, f"值不匹配: {decoded.value} != {cmd.value}"
    elif cmd.type == CommandType.HOME:
        # HOME 指令只携带 axis
        assert decoded.axis == cmd.axis, f"轴不匹配: {decoded.axis} != {cmd.axis}"
    # STATUS 和 ESTOP 指令不携带额外数据，无需验证 axis/value


@given(rsp=response_strategy())
@settings(max_examples=100)
def test_response_roundtrip(rsp: Response):
    """
    Property 1: 通信协议编解码往返一致性 (Response)
    
    *For any* valid Response object, encoding then decoding should produce
    an equivalent Response object.
    
    **Validates: Requirements 3.3, 3.5**
    """
    # 编码
    encoded = encode_response(rsp)
    
    # 解码
    decoded, error = decode_response(encoded)
    
    # 验证往返一致性
    assert error == "", f"解码失败: {error}"
    assert decoded is not None, "解码结果为空"
    assert decoded.type == rsp.type, f"类型不匹配: {decoded.type} != {rsp.type}"
    assert decoded.status == rsp.status, f"状态不匹配: {decoded.status} != {rsp.status}"
    
    # 对于 STATUS 响应，验证位置值
    if rsp.type == ResponseType.STATUS:
        assert decoded.pan_pos == rsp.pan_pos, f"Pan 位置不匹配"
        assert decoded.tilt_pos == rsp.tilt_pos, f"Tilt 位置不匹配"
        assert decoded.rail_pos == rsp.rail_pos, f"Rail 位置不匹配"


# ==================== Property 2: 校验和完整性 ====================

@given(data=st.binary(min_size=1, max_size=64))
@settings(max_examples=100)
def test_crc16_consistency(data: bytes):
    """
    Property 2: 校验和完整性验证 - CRC 一致性
    
    *For any* byte sequence, calculating CRC twice should produce the same result.
    
    **Validates: Requirements 3.3**
    """
    crc1 = crc16_calculate(data)
    crc2 = crc16_calculate(data)
    assert crc1 == crc2, "CRC 计算不一致"


@given(data=st.binary(min_size=1, max_size=64))
@settings(max_examples=100)
def test_crc16_verify_correct(data: bytes):
    """
    Property 2: 校验和完整性验证 - 正确校验
    
    *For any* byte sequence, verifying with the calculated CRC should pass.
    
    **Validates: Requirements 3.3**
    """
    crc = crc16_calculate(data)
    assert crc16_verify(data, crc), "正确的 CRC 验证失败"


@given(data=st.binary(min_size=1, max_size=64), wrong_crc=st.integers(min_value=0, max_value=65535))
@settings(max_examples=100)
def test_crc16_detect_corruption(data: bytes, wrong_crc: int):
    """
    Property 2: 校验和完整性验证 - 错误检测
    
    *For any* byte sequence and incorrect CRC, verification should fail
    (unless the wrong CRC happens to match by chance).
    
    **Validates: Requirements 3.3**
    """
    correct_crc = crc16_calculate(data)
    # 只有当 wrong_crc 不等于正确值时才测试
    assume(wrong_crc != correct_crc)
    assert not crc16_verify(data, wrong_crc), "错误的 CRC 未被检测"


@given(cmd=command_strategy(), bit_pos=st.integers(min_value=0, max_value=7))
@settings(max_examples=100)
def test_command_corruption_detected(cmd: Command, bit_pos: int):
    """
    Property 2: 校验和完整性验证 - 数据损坏检测
    
    *For any* encoded command frame, flipping a bit in the data portion
    should cause decoding to fail with checksum error.
    
    **Validates: Requirements 3.3**
    """
    encoded = encode_command(cmd)
    
    # 确保帧足够长
    assume(len(encoded) > 5)
    
    # 在数据部分翻转一个比特 (避开帧头、校验和、帧尾)
    byte_pos = 2  # 选择 CMD 字节位置
    corrupted = bytearray(encoded)
    corrupted[byte_pos] ^= (1 << bit_pos)
    
    # 解码应该失败
    decoded, error = decode_command(bytes(corrupted))
    
    # 应该检测到错误（校验和错误或类型错误）
    assert decoded is None or error != "", "数据损坏未被检测"
