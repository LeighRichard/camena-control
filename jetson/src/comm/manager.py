"""
通信管理器模块 - 封装串口通信，提供发送、接收、超时重试逻辑
"""

import threading
import time
import logging
from typing import Optional, Callable, List, Tuple
from dataclasses import dataclass
from enum import Enum

from .protocol import (
    Command, Response, 
    encode_command, decode_response,
    FRAME_HEAD, FRAME_TAIL,
    get_next_seq, reset_seq
)

logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """连接状态枚举"""
    DISCONNECTED = "disconnected"   # 未连接
    CONNECTING = "connecting"       # 正在连接
    CONNECTED = "connected"         # 已连接
    RECONNECTING = "reconnecting"   # 正在重连
    ERROR = "error"                 # 连接错误


@dataclass
class CommConfig:
    """通信配置"""
    port: str = "/dev/ttyUSB0"
    baudrate: int = 115200
    timeout: float = 1.0
    retry_count: int = 3
    retry_delay: float = 0.1
    auto_reconnect: bool = True         # 是否自动重连
    reconnect_interval: float = 2.0     # 重连间隔（秒）
    max_reconnect_attempts: int = 10    # 最大重连次数，0 表示无限
    heartbeat_interval: float = 5.0     # 心跳检测间隔（秒）
    heartbeat_timeout: float = 3.0      # 心跳超时时间（秒）


class CommManager:
    """
    串口通信管理器
    
    负责与 STM32 的串口通信，包括：
    - 连接管理
    - 指令发送和响应接收
    - 超时重试机制
    - 异步接收处理
    - 连接状态回调通知
    - 自动重连机制
    - 心跳检测
    """
    
    def __init__(self, config: Optional[CommConfig] = None):
        """
        初始化通信管理器
        
        Args:
            config: 通信配置，为 None 时使用默认配置
        """
        self.config = config or CommConfig()
        self._serial = None
        self._lock = threading.Lock()
        self._running = False
        self._recv_thread: Optional[threading.Thread] = None
        self._recv_callback: Optional[Callable[[Response], None]] = None
        self._recv_buffer = bytearray()
        
        # 连接状态管理
        self._state = ConnectionState.DISCONNECTED
        self._state_callbacks: List[Callable[[ConnectionState, Optional[str]], None]] = []
        self._reconnect_thread: Optional[threading.Thread] = None
        self._reconnect_attempts = 0
        self._last_recv_time = 0.0
        self._heartbeat_thread: Optional[threading.Thread] = None
    
    @property
    def state(self) -> ConnectionState:
        """获取当前连接状态"""
        return self._state
    
    def _set_state(self, new_state: ConnectionState, reason: str = None):
        """
        设置连接状态并通知回调
        
        Args:
            new_state: 新状态
            reason: 状态变化原因
        """
        if self._state != new_state:
            old_state = self._state
            self._state = new_state
            logger.info(f"连接状态变化: {old_state.value} -> {new_state.value}" + 
                       (f" ({reason})" if reason else ""))
            
            # 通知所有回调
            for callback in self._state_callbacks:
                try:
                    callback(new_state, reason)
                except Exception as e:
                    logger.error(f"状态回调执行错误: {e}")
    
    def add_state_callback(self, callback: Callable[[ConnectionState, Optional[str]], None]):
        """
        添加连接状态变化回调
        
        Args:
            callback: 回调函数，参数为 (新状态, 原因)
        """
        if callback not in self._state_callbacks:
            self._state_callbacks.append(callback)
    
    def remove_state_callback(self, callback: Callable[[ConnectionState, Optional[str]], None]):
        """
        移除连接状态变化回调
        
        Args:
            callback: 要移除的回调函数
        """
        if callback in self._state_callbacks:
            self._state_callbacks.remove(callback)
    
    def connect(self) -> bool:
        """
        建立串口连接
        
        Returns:
            连接是否成功
        """
        self._set_state(ConnectionState.CONNECTING)
        
        try:
            import serial
            self._serial = serial.Serial(
                port=self.config.port,
                baudrate=self.config.baudrate,
                timeout=self.config.timeout
            )
            self._running = True
            self._reconnect_attempts = 0
            self._last_recv_time = time.time()
            self._set_state(ConnectionState.CONNECTED)
            
            # 启动心跳检测
            if self.config.heartbeat_interval > 0:
                self._start_heartbeat()
            
            return True
        except Exception as e:
            logger.error(f"串口连接失败: {e}")
            self._set_state(ConnectionState.ERROR, str(e))
            
            # 尝试自动重连
            if self.config.auto_reconnect:
                self._start_reconnect()
            
            return False
    
    def disconnect(self):
        """断开串口连接"""
        self._running = False
        
        # 停止心跳线程
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            self._heartbeat_thread.join(timeout=1.0)
        
        # 停止重连线程
        if self._reconnect_thread and self._reconnect_thread.is_alive():
            self._reconnect_thread.join(timeout=1.0)
        
        # 停止接收线程
        if self._recv_thread and self._recv_thread.is_alive():
            self._recv_thread.join(timeout=1.0)
        
        if self._serial:
            self._serial.close()
            self._serial = None
        
        self._set_state(ConnectionState.DISCONNECTED, "主动断开")
    
    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self._serial is not None and self._serial.is_open
    
    def _start_reconnect(self):
        """启动重连线程"""
        if self._reconnect_thread and self._reconnect_thread.is_alive():
            return
        
        self._reconnect_thread = threading.Thread(target=self._reconnect_loop, daemon=True)
        self._reconnect_thread.start()
    
    def _reconnect_loop(self):
        """重连循环"""
        while self._running or self._state == ConnectionState.ERROR:
            # 检查重连次数限制
            if (self.config.max_reconnect_attempts > 0 and 
                self._reconnect_attempts >= self.config.max_reconnect_attempts):
                logger.error(f"达到最大重连次数 ({self.config.max_reconnect_attempts})，停止重连")
                self._set_state(ConnectionState.ERROR, "达到最大重连次数")
                return
            
            self._reconnect_attempts += 1
            self._set_state(ConnectionState.RECONNECTING, 
                           f"第 {self._reconnect_attempts} 次重连")
            
            logger.info(f"尝试重连 ({self._reconnect_attempts})...")
            
            try:
                import serial
                self._serial = serial.Serial(
                    port=self.config.port,
                    baudrate=self.config.baudrate,
                    timeout=self.config.timeout
                )
                self._running = True
                self._reconnect_attempts = 0
                self._last_recv_time = time.time()
                self._set_state(ConnectionState.CONNECTED, "重连成功")
                
                # 重新启动心跳检测
                if self.config.heartbeat_interval > 0:
                    self._start_heartbeat()
                
                return
            except Exception as e:
                logger.warning(f"重连失败: {e}")
            
            # 等待后重试
            time.sleep(self.config.reconnect_interval)
    
    def _start_heartbeat(self):
        """启动心跳检测线程"""
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            return
        
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._heartbeat_thread.start()
    
    def _heartbeat_loop(self):
        """
        心跳检测循环
        
        定期检查连接状态，如果超时未收到数据则触发重连
        """
        while self._running and self.is_connected():
            time.sleep(self.config.heartbeat_interval)
            
            # 检查线程是否应该退出
            if not self._running:
                break
            
            # 检查是否超时未收到数据
            elapsed = time.time() - self._last_recv_time
            if elapsed > self.config.heartbeat_timeout + self.config.heartbeat_interval:
                logger.warning(f"心跳超时 ({elapsed:.1f}s)，连接可能已断开")
                self._handle_connection_lost("心跳超时")
                break
    
    def _handle_connection_lost(self, reason: str):
        """
        处理连接丢失
        
        Args:
            reason: 丢失原因
        """
        if self._serial:
            try:
                self._serial.close()
            except Exception:
                # 关闭串口失败，忽略
                pass
            self._serial = None
        
        self._set_state(ConnectionState.ERROR, reason)
        
        # 尝试自动重连
        if self.config.auto_reconnect:
            self._start_reconnect()

    def send_command(self, cmd: Command, wait_response: bool = True) -> Tuple[Optional[Response], str]:
        """
        发送指令并等待响应（带序列号匹配）
        
        Args:
            cmd: 要发送的指令
            wait_response: 是否等待响应
            
        Returns:
            (响应对象, 错误信息) - 成功时错误信息为空字符串
        """
        if not self.is_connected():
            return None, "未连接"
        
        # 编码指令（自动分配序列号）
        frame = encode_command(cmd, auto_seq=True)
        expected_seq = cmd.seq
        
        for attempt in range(self.config.retry_count):
            with self._lock:
                try:
                    self._serial.write(frame)
                    
                    if not wait_response:
                        return None, ""
                    
                    # 等待响应（带序列号匹配）
                    response = self._read_response_with_seq(expected_seq)
                    if response:
                        self._last_recv_time = time.time()
                        return response, ""
                    
                    logger.warning(f"发送失败 (尝试 {attempt + 1}/{self.config.retry_count}): 响应超时或序列号不匹配")
                        
                except Exception as e:
                    logger.warning(f"发送失败 (尝试 {attempt + 1}): {e}")
                    
                    # 检查是否是连接问题
                    if not self.is_connected():
                        self._handle_connection_lost(f"发送时连接丢失: {e}")
                        return None, f"连接丢失: {e}"
            
            if attempt < self.config.retry_count - 1:
                time.sleep(self.config.retry_delay)
        
        return None, f"发送失败: 重试 {self.config.retry_count} 次后仍无响应"
    
    def _read_response_with_seq(self, expected_seq: int) -> Optional[Response]:
        """
        读取响应帧（带序列号匹配）
        
        Args:
            expected_seq: 期望的序列号
            
        Returns:
            响应对象，失败返回 None
        """
        buffer = bytearray()
        start_time = time.time()
        
        while time.time() - start_time < self.config.timeout:
            try:
                if self._serial.in_waiting > 0:
                    byte = self._serial.read(1)
                    if byte:
                        buffer.extend(byte)
                        
                        # 检查是否收到完整帧
                        if len(buffer) >= 7 and buffer[-1] == FRAME_TAIL:
                            response, error = decode_response(bytes(buffer))
                            if response:
                                # 检查序列号匹配
                                if response.seq == expected_seq:
                                    return response
                                else:
                                    logger.warning(f"序列号不匹配: 期望 {expected_seq}, 收到 {response.seq}")
                            buffer.clear()
            except Exception as e:
                logger.error(f"读取响应错误: {e}")
                break
        
        return None
    
    def start_async_receive(self, callback: Callable[[Response], None]):
        """
        启动异步接收线程
        
        Args:
            callback: 收到响应时的回调函数
        """
        self._recv_callback = callback
        self._recv_thread = threading.Thread(target=self._async_receive_loop, daemon=True)
        self._recv_thread.start()
    
    def _async_receive_loop(self):
        """异步接收循环"""
        while self._running and self.is_connected():
            try:
                if self._serial.in_waiting > 0:
                    byte = self._serial.read(1)
                    if byte:
                        self._recv_buffer.extend(byte)
                        self._last_recv_time = time.time()
                        self._process_recv_buffer()
                else:
                    time.sleep(0.001)
            except Exception as e:
                logger.error(f"异步接收错误: {e}")
                if not self.is_connected():
                    self._handle_connection_lost(f"接收时连接丢失: {e}")
                    break
                time.sleep(0.1)
    
    def _process_recv_buffer(self):
        """处理接收缓冲区"""
        # 查找帧头
        while len(self._recv_buffer) > 0 and self._recv_buffer[0] != FRAME_HEAD:
            self._recv_buffer.pop(0)
        
        # 检查是否有完整帧
        if len(self._recv_buffer) >= 6:
            # 查找帧尾
            for i in range(5, len(self._recv_buffer)):
                if self._recv_buffer[i] == FRAME_TAIL:
                    frame = bytes(self._recv_buffer[:i+1])
                    self._recv_buffer = self._recv_buffer[i+1:]
                    
                    response, error = decode_response(frame)
                    if response and self._recv_callback:
                        self._recv_callback(response)
                    break
