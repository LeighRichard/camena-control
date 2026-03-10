"""
安全监控属性测试

Property 7: 通信超时看门狗

验证需求: 6.5
"""

import pytest
from hypothesis import given, strategies as st, settings, assume

import sys
sys.path.insert(0, 'src')

from safety.watchdog import WatchdogSimulator


# ==================== Property 7: 通信超时看门狗 ====================

@given(
    timeout_ms=st.integers(min_value=100, max_value=5000),
    feed_intervals=st.lists(
        st.integers(min_value=10, max_value=2000),
        min_size=1, max_size=20
    )
)
@settings(max_examples=100)
def test_watchdog_timeout_detection(timeout_ms, feed_intervals):
    """
    Property 7: 通信超时看门狗 - 超时检测
    
    *For any* timeout setting and feed intervals,
    the watchdog should correctly detect timeout when elapsed time exceeds timeout.
    
    **Validates: Requirements 6.5**
    """
    watchdog = WatchdogSimulator(timeout_ms=timeout_ms)
    watchdog.feed()  # 初始喂狗
    
    for interval in feed_intervals:
        # 推进时间
        watchdog.advance_time(interval)
        
        # 检查超时状态
        is_timeout = watchdog.check()
        elapsed = watchdog._current_time_ms - watchdog._last_feed_time_ms
        
        # 验证：超时状态应该与实际经过时间一致
        expected_timeout = elapsed > timeout_ms
        assert is_timeout == expected_timeout, \
            f"超时检测错误: elapsed={elapsed}ms, timeout={timeout_ms}ms, detected={is_timeout}"
        
        # 如果没超时，喂狗
        if not is_timeout:
            watchdog.feed()


@given(
    timeout_ms=st.integers(min_value=100, max_value=5000),
    time_before_timeout=st.integers(min_value=10, max_value=4999)
)
@settings(max_examples=100)
def test_watchdog_no_false_positive(timeout_ms, time_before_timeout):
    """
    Property 7: 通信超时看门狗 - 无误报
    
    *For any* timeout setting, if time elapsed is less than timeout,
    the watchdog should NOT report timeout.
    
    **Validates: Requirements 6.5**
    """
    assume(time_before_timeout < timeout_ms)
    
    watchdog = WatchdogSimulator(timeout_ms=timeout_ms)
    watchdog.feed()
    
    # 推进时间但不超过超时
    watchdog.advance_time(time_before_timeout)
    
    # 不应该超时
    assert not watchdog.check(), \
        f"误报超时: elapsed={time_before_timeout}ms < timeout={timeout_ms}ms"
    assert not watchdog.is_timeout


@given(
    timeout_ms=st.integers(min_value=100, max_value=2000),
    extra_time=st.integers(min_value=1, max_value=1000)
)
@settings(max_examples=100)
def test_watchdog_timeout_triggers_stop(timeout_ms, extra_time):
    """
    Property 7: 通信超时看门狗 - 超时触发停止
    
    *For any* timeout setting, when timeout occurs,
    the motion should be stopped.
    
    **Validates: Requirements 6.5**
    """
    watchdog = WatchdogSimulator(timeout_ms=timeout_ms)
    watchdog.feed()
    
    # 推进时间超过超时
    watchdog.advance_time(timeout_ms + extra_time)
    
    # 检查超时
    watchdog.check()
    
    # 验证运动已停止
    assert watchdog.is_timeout, "应该检测到超时"
    assert watchdog.motion_stopped, "超时后运动应该停止"


@given(
    timeout_ms=st.integers(min_value=100, max_value=2000),
    feed_count=st.integers(min_value=1, max_value=10)
)
@settings(max_examples=100)
def test_watchdog_feed_resets_timer(timeout_ms, feed_count):
    """
    Property 7: 通信超时看门狗 - 喂狗重置计时器
    
    *For any* timeout setting, feeding the watchdog should reset the timer.
    
    **Validates: Requirements 6.5**
    """
    watchdog = WatchdogSimulator(timeout_ms=timeout_ms)
    
    for _ in range(feed_count):
        watchdog.feed()
        
        # 推进时间但不超过超时
        watchdog.advance_time(timeout_ms - 10)
        
        # 不应该超时
        assert not watchdog.check(), "喂狗后不应该超时"
    
    # 最后一次喂狗后，推进超过超时时间
    watchdog.advance_time(timeout_ms + 100)
    
    # 现在应该超时
    assert watchdog.check(), "超过超时时间后应该超时"


@given(
    timeout_ms=st.integers(min_value=100, max_value=2000)
)
@settings(max_examples=50)
def test_watchdog_disabled_no_timeout(timeout_ms):
    """
    Property 7: 通信超时看门狗 - 禁用时不超时
    
    *For any* timeout setting, when watchdog is disabled,
    it should never report timeout.
    
    **Validates: Requirements 6.5**
    """
    watchdog = WatchdogSimulator(timeout_ms=timeout_ms)
    watchdog.enabled = False
    watchdog.feed()
    
    # 推进大量时间
    watchdog.advance_time(timeout_ms * 10)
    
    # 禁用时不应该超时
    assert not watchdog.check(), "禁用时不应该报告超时"
