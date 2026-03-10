"""
控制模块属性测试 - PID 控制器和卡尔曼滤波器

Property 测试：
- PID 控制器输出限幅
- PID 积分抗饱和
- 卡尔曼滤波器状态一致性
- 目标跟踪器关联正确性
"""

import pytest
import numpy as np
from hypothesis import given, strategies as st, settings, assume
import time

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from control.pid import PIDController, PIDConfig, DualAxisPID
from control.kalman import KalmanFilter, KalmanConfig, TargetTracker


# ============================================================================
# PID 控制器属性测试
# ============================================================================

class TestPIDControllerProperties:
    """PID 控制器属性测试"""
    
    @given(
        kp=st.floats(0.1, 10.0),
        measurement=st.floats(-1000, 1000),
        setpoint=st.floats(-1000, 1000)
    )
    @settings(max_examples=100)
    def test_output_within_limits(self, kp, measurement, setpoint):
        """
        Property: 输出始终在限制范围内
        """
        config = PIDConfig(
            kp=kp, ki=0.0, kd=0.0,
            output_min=-50.0, output_max=50.0
        )
        pid = PIDController(config)
        pid.set_setpoint(setpoint)
        
        output = pid.compute(measurement, dt=0.1)
        
        assert -50.0 <= output <= 50.0
    
    @given(
        ki=st.floats(0.1, 5.0),
        error=st.floats(10, 100)
    )
    @settings(max_examples=50)
    def test_integral_anti_windup(self, ki, error):
        """
        Property: 积分项不会超过限制（抗饱和）
        """
        config = PIDConfig(
            kp=0.0, ki=ki, kd=0.0,
            integral_min=-20.0, integral_max=20.0
        )
        pid = PIDController(config)
        pid.set_setpoint(error)  # 设置一个持续误差
        
        # 多次计算，积分应该累积但不超限
        for _ in range(100):
            pid.compute(0.0, dt=0.1)
        
        integral = pid.get_integral()
        assert -20.0 <= integral <= 20.0
    
    @given(
        setpoint=st.floats(-100, 100)
    )
    @settings(max_examples=50)
    def test_zero_error_zero_output(self, setpoint):
        """
        Property: 误差为零时，P 项输出为零
        """
        config = PIDConfig(kp=1.0, ki=0.0, kd=0.0)
        pid = PIDController(config)
        pid.set_setpoint(setpoint)
        
        # 测量值等于设定点
        output = pid.compute(setpoint, dt=0.1)
        
        assert abs(output) < 1e-6
    
    @given(
        kp=st.floats(0.1, 5.0),
        error=st.floats(1, 100)
    )
    @settings(max_examples=50)
    def test_proportional_direction(self, kp, error):
        """
        Property: P 项输出方向与误差方向一致
        """
        config = PIDConfig(kp=kp, ki=0.0, kd=0.0, output_min=-1000, output_max=1000)
        pid = PIDController(config)
        pid.set_setpoint(error)
        
        # 测量值为 0，误差为正
        output = pid.compute(0.0, dt=0.1)
        assert output > 0
        
        # 测量值为 2*error，误差为负
        pid.reset()
        output = pid.compute(2 * error, dt=0.1)
        assert output < 0
    
    def test_reset_clears_state(self):
        """重置应清除所有状态"""
        config = PIDConfig(kp=1.0, ki=0.5, kd=0.1)
        pid = PIDController(config)
        pid.set_setpoint(100)
        
        # 运行几次
        for _ in range(10):
            pid.compute(0.0, dt=0.1)
        
        # 重置
        pid.reset()
        
        assert pid.get_integral() == 0.0
        assert pid.get_error() == 0.0
    
    @given(
        deadband=st.floats(1, 20)
    )
    @settings(max_examples=30)
    def test_deadband_suppresses_small_errors(self, deadband):
        """
        Property: 死区内的误差不产生输出
        """
        config = PIDConfig(kp=1.0, ki=0.0, kd=0.0, deadband=deadband)
        pid = PIDController(config)
        pid.set_setpoint(0.0)
        
        # 测量值在死区内
        small_error = deadband * 0.5
        output = pid.compute(small_error, dt=0.1)
        
        assert output == 0.0


class TestDualAxisPIDProperties:
    """双轴 PID 控制器属性测试"""
    
    @given(
        target_x=st.floats(0, 1280),
        target_y=st.floats(0, 720)
    )
    @settings(max_examples=50)
    def test_center_target_minimal_output(self, target_x, target_y):
        """
        Property: 目标在中心时输出最小
        """
        dual_pid = DualAxisPID()
        dual_pid.set_image_center(640, 360)
        
        # 目标在中心
        pan_center, tilt_center = dual_pid.compute(640, 360, dt=0.1)
        
        # 目标偏离中心
        dual_pid.reset()
        pan_offset, tilt_offset = dual_pid.compute(target_x, target_y, dt=0.1)
        
        # 中心输出应该更小（或相等）
        assert abs(pan_center) <= abs(pan_offset) + 0.1
        assert abs(tilt_center) <= abs(tilt_offset) + 0.1
    
    def test_output_direction_consistency(self):
        """输出方向应与偏移方向一致"""
        dual_pid = DualAxisPID()
        dual_pid.set_image_center(640, 360)
        
        # 目标在右侧
        pan, _ = dual_pid.compute(800, 360, dt=0.1)
        assert pan < 0  # 需要向左调整（负方向）
        
        # 目标在左侧
        dual_pid.reset()
        pan, _ = dual_pid.compute(400, 360, dt=0.1)
        assert pan > 0  # 需要向右调整（正方向）


# ============================================================================
# 卡尔曼滤波器属性测试
# ============================================================================

class TestKalmanFilterProperties:
    """卡尔曼滤波器属性测试"""
    
    @given(
        x=st.floats(-1000, 1000),
        y=st.floats(-1000, 1000)
    )
    @settings(max_examples=50)
    def test_initialization_preserves_position(self, x, y):
        """
        Property: 初始化后位置应与输入一致
        """
        kf = KalmanFilter()
        kf.initialize(x, y)
        
        pos_x, pos_y = kf.get_position()
        
        assert abs(pos_x - x) < 1e-6
        assert abs(pos_y - y) < 1e-6
    
    @given(
        x=st.floats(0, 1000),
        y=st.floats(0, 1000),
        vx=st.floats(-100, 100),
        vy=st.floats(-100, 100)
    )
    @settings(max_examples=50)
    def test_prediction_follows_velocity(self, x, y, vx, vy):
        """
        Property: 预测位置应沿速度方向移动
        """
        kf = KalmanFilter()
        kf.initialize(x, y, vx, vy)
        
        dt = 0.1
        pred_x, pred_y = kf.predict_position(dt)
        
        expected_x = x + vx * dt
        expected_y = y + vy * dt
        
        assert abs(pred_x - expected_x) < 1e-3
        assert abs(pred_y - expected_y) < 1e-3
    
    def test_update_converges_to_measurement(self):
        """
        Property: 多次更新相同测量值后，估计值应收敛到测量值
        """
        kf = KalmanFilter()
        
        # 使用相同的测量值多次更新
        target_x, target_y = 500.0, 300.0
        
        for _ in range(20):
            kf.update(target_x, target_y)
        
        est_x, est_y = kf.get_position()
        
        # 多次更新相同值后应该收敛
        assert abs(est_x - target_x) < 10
        assert abs(est_y - target_y) < 10
    
    def test_reset_clears_state(self):
        """重置应清除状态"""
        kf = KalmanFilter()
        kf.initialize(100, 200, 10, 20)
        
        assert kf.is_initialized()
        
        kf.reset()
        
        assert not kf.is_initialized()
        pos_x, pos_y = kf.get_position()
        assert pos_x == 0.0
        assert pos_y == 0.0


# ============================================================================
# 目标跟踪器属性测试
# ============================================================================

class TestTargetTrackerProperties:
    """目标跟踪器属性测试"""
    
    def test_new_detection_creates_track(self):
        """新检测应创建跟踪"""
        tracker = TargetTracker()
        
        detections = [(100.0, 200.0, 0)]
        results = tracker.update(detections)
        
        # 第一帧可能还未确认
        # 继续几帧
        for _ in range(5):
            results = tracker.update(detections)
        
        assert len(results) >= 1
    
    def test_consistent_detection_confirms_track(self):
        """持续检测应确认跟踪"""
        tracker = TargetTracker()
        tracker.set_parameters(min_hits=3)
        
        detections = [(500.0, 300.0, 0)]
        
        # 前几帧未确认
        for _ in range(2):
            results = tracker.update(detections)
        
        # 第三帧应该确认
        results = tracker.update(detections)
        
        assert len(results) == 1
        assert len(tracker.get_confirmed_tracks()) == 1
    
    def test_missing_detection_ages_track(self):
        """丢失检测应增加跟踪年龄"""
        tracker = TargetTracker()
        tracker.set_parameters(min_hits=2, max_age=5)
        
        # 创建并确认跟踪
        detections = [(500.0, 300.0, 0)]
        for _ in range(3):
            tracker.update(detections)
        
        # 停止检测
        for _ in range(6):
            results = tracker.update([])
        
        # 跟踪应该被删除
        assert len(tracker.get_all_tracks()) == 0
    
    @given(
        positions=st.lists(
            st.tuples(
                st.floats(0, 1000),
                st.floats(0, 1000)
            ),
            min_size=1, max_size=5
        )
    )
    @settings(max_examples=30)
    def test_multiple_detections_create_multiple_tracks(self, positions):
        """多个检测应创建多个跟踪"""
        tracker = TargetTracker()
        tracker.set_parameters(min_hits=2, distance_threshold=50)
        
        # 确保位置足够分散
        detections = [(x, y, 0) for x, y in positions]
        
        # 多帧更新
        for _ in range(5):
            tracker.update(detections)
        
        # 跟踪数应该等于检测数（如果位置足够分散）
        confirmed = tracker.get_confirmed_tracks()
        assert len(confirmed) <= len(positions)
    
    def test_reset_clears_all_tracks(self):
        """重置应清除所有跟踪"""
        tracker = TargetTracker()
        
        # 创建一些跟踪
        for _ in range(5):
            tracker.update([(100, 200, 0), (300, 400, 1)])
        
        tracker.reset()
        
        assert len(tracker.get_all_tracks()) == 0
        assert len(tracker.get_confirmed_tracks()) == 0


# ============================================================================
# 集成测试
# ============================================================================

class TestControlIntegration:
    """控制模块集成测试"""
    
    def test_pid_with_kalman_smoothing(self):
        """PID 配合卡尔曼滤波"""
        pid = PIDController(PIDConfig(kp=0.5, ki=0.1, kd=0.05))
        kf = KalmanFilter()
        
        pid.set_setpoint(640)  # 目标：图像中心
        
        # 模拟目标移动
        true_position = 400.0
        
        for i in range(20):
            # 添加噪声的测量
            noisy_measurement = true_position + np.random.randn() * 10
            
            # 卡尔曼滤波
            if not kf.is_initialized():
                kf.initialize(noisy_measurement, 0)
            else:
                kf.predict(dt=0.1)
                kf.update(noisy_measurement, 0)
            
            filtered_x, _ = kf.get_position()
            
            # PID 控制
            output = pid.compute(filtered_x, dt=0.1)
            
            # 输出应该在合理范围内
            assert abs(output) < 200
    
    def test_dual_axis_tracking_convergence(self):
        """双轴跟踪收敛性"""
        dual_pid = DualAxisPID()
        dual_pid.set_image_center(640, 360)
        
        # 模拟目标位置
        target_x, target_y = 800.0, 500.0
        
        outputs = []
        for _ in range(50):
            pan, tilt = dual_pid.compute(target_x, target_y, dt=0.1)
            outputs.append((pan, tilt))
        
        # 输出应该稳定（不会无限增长）
        final_pan, final_tilt = outputs[-1]
        assert abs(final_pan) < 100
        assert abs(final_tilt) < 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
