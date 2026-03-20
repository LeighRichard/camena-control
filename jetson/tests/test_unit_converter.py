"""
单位转换工具测试
"""

import pytest
from hypothesis import given, strategies as st

from src.comm.unit_converter import (
    UnitConverter, MotionValidator,
    deg_to_steps, steps_to_deg,
    mm_to_steps, steps_to_mm,
    STEPS_PER_REV_PAN, STEPS_PER_REV_TILT, STEPS_PER_MM_RAIL,
    MAX_SPEED_PAN_STEPS, MAX_SPEED_TILT_STEPS, MAX_SPEED_RAIL_STEPS,
    MAX_ACCEL_PAN_STEPS, MAX_ACCEL_TILT_STEPS, MAX_ACCEL_RAIL_STEPS,
    PAN_MIN_ANGLE, PAN_MAX_ANGLE, TILT_MIN_ANGLE, TILT_MAX_ANGLE,
    RAIL_MIN_POS, RAIL_MAX_POS
)


class TestUnitConverter:
    """单位转换器测试"""
    
    def test_degrees_to_steps_pan(self):
        """测试 Pan 轴角度转步数"""
        # 360 度 = 3200 步
        assert UnitConverter.degrees_to_steps(360, 'pan') == 3200
        # 180 度 = 1600 步
        assert UnitConverter.degrees_to_steps(180, 'pan') == 1600
        # 90 度 = 800 步
        assert UnitConverter.degrees_to_steps(90, 'pan') == 800
        # 0 度 = 0 步
        assert UnitConverter.degrees_to_steps(0, 'pan') == 0
    
    def test_degrees_to_steps_tilt(self):
        """测试 Tilt 轴角度转步数"""
        # 360 度 = 3200 步
        assert UnitConverter.degrees_to_steps(360, 'tilt') == 3200
        # 90 度 = 800 步
        assert UnitConverter.degrees_to_steps(90, 'tilt') == 800
    
    def test_steps_to_degrees_pan(self):
        """测试 Pan 轴步数转角度"""
        # 3200 步 = 360 度
        assert abs(UnitConverter.steps_to_degrees(3200, 'pan') - 360.0) < 0.01
        # 1600 步 = 180 度
        assert abs(UnitConverter.steps_to_degrees(1600, 'pan') - 180.0) < 0.01
        # 800 步 = 90 度
        assert abs(UnitConverter.steps_to_degrees(800, 'pan') - 90.0) < 0.01
    
    def test_mm_to_steps(self):
        """测试毫米转步数"""
        # 1 mm = 80 步
        assert UnitConverter.mm_to_steps(1.0) == 80
        # 10 mm = 800 步
        assert UnitConverter.mm_to_steps(10.0) == 800
        # 0.5 mm = 40 步
        assert UnitConverter.mm_to_steps(0.5) == 40
    
    def test_steps_to_mm(self):
        """测试步数转毫米"""
        # 80 步 = 1 mm
        assert abs(UnitConverter.steps_to_mm(80) - 1.0) < 0.01
        # 800 步 = 10 mm
        assert abs(UnitConverter.steps_to_mm(800) - 10.0) < 0.01
    
    def test_speed_conversion_pan(self):
        """测试 Pan 速度转换"""
        # 30 度/秒 ≈ 267 步/秒
        speed_steps = UnitConverter.speed_to_steps(30.0, 'pan')
        assert 266 <= speed_steps <= 268
        
        # 反向转换
        speed_deg = UnitConverter.steps_to_speed(267, 'pan')
        assert abs(speed_deg - 30.0) < 0.5
    
    def test_speed_conversion_rail(self):
        """测试 Rail 速度转换"""
        # 6 mm/秒 = 480 步/秒
        speed_steps = UnitConverter.speed_to_steps(6.0, 'rail')
        assert speed_steps == 480
        
        # 反向转换
        speed_mm = UnitConverter.steps_to_speed(480, 'rail')
        assert abs(speed_mm - 6.0) < 0.01
    
    def test_accel_conversion(self):
        """测试加速度转换"""
        # Pan: 15 度/秒² ≈ 133 步/秒²
        accel_steps = UnitConverter.accel_to_steps(15.0, 'pan')
        assert 132 <= accel_steps <= 134
        
        # Rail: 3 mm/秒² = 240 步/秒²
        accel_steps = UnitConverter.accel_to_steps(3.0, 'rail')
        assert accel_steps == 240
    
    def test_convenience_functions(self):
        """测试便捷函数"""
        assert deg_to_steps(90, 'pan') == 800
        assert abs(steps_to_deg(800, 'pan') - 90.0) < 0.01
        assert mm_to_steps(1.0) == 80
        assert abs(steps_to_mm(80) - 1.0) < 0.01
    
    def test_invalid_axis(self):
        """测试无效轴名称"""
        with pytest.raises(ValueError):
            UnitConverter.degrees_to_steps(90, 'invalid')
        
        with pytest.raises(ValueError):
            UnitConverter.speed_to_steps(10, 'invalid')


class TestMotionValidator:
    """运动参数验证器测试"""
    
    def test_validate_position_pan(self):
        """测试 Pan 位置验证"""
        # 有效范围内
        valid, _ = MotionValidator.validate_position(0, 'pan')
        assert valid
        
        valid, _ = MotionValidator.validate_position(180, 'pan')
        assert valid
        
        valid, _ = MotionValidator.validate_position(-180, 'pan')
        assert valid
        
        # 超出范围
        valid, error = MotionValidator.validate_position(181, 'pan')
        assert not valid
        assert 'Pan' in error
        
        valid, error = MotionValidator.validate_position(-181, 'pan')
        assert not valid
    
    def test_validate_position_tilt(self):
        """测试 Tilt 位置验证"""
        # 有效范围内
        valid, _ = MotionValidator.validate_position(0, 'tilt')
        assert valid
        
        valid, _ = MotionValidator.validate_position(90, 'tilt')
        assert valid
        
        valid, _ = MotionValidator.validate_position(-90, 'tilt')
        assert valid
        
        # 超出范围
        valid, error = MotionValidator.validate_position(91, 'tilt')
        assert not valid
        assert 'Tilt' in error
    
    def test_validate_position_rail(self):
        """测试 Rail 位置验证"""
        # 有效范围内
        valid, _ = MotionValidator.validate_position(0, 'rail')
        assert valid
        
        valid, _ = MotionValidator.validate_position(250, 'rail')
        assert valid
        
        valid, _ = MotionValidator.validate_position(500, 'rail')
        assert valid
        
        # 超出范围
        valid, error = MotionValidator.validate_position(-1, 'rail')
        assert not valid
        
        valid, error = MotionValidator.validate_position(501, 'rail')
        assert not valid
    
    def test_validate_speed_pan(self):
        """测试 Pan 速度验证"""
        # 30 度/秒 = 267 步/秒 < 1000 (有效)
        valid, _ = MotionValidator.validate_speed(30.0, 'pan')
        assert valid
        
        # 100 度/秒 = 889 步/秒 < 1000 (有效)
        valid, _ = MotionValidator.validate_speed(100.0, 'pan')
        assert valid
        
        # 150 度/秒 = 1333 步/秒 > 1000 (无效)
        valid, error = MotionValidator.validate_speed(150.0, 'pan')
        assert not valid
        assert 'Pan' in error
        assert '1000' in error
    
    def test_validate_speed_rail(self):
        """测试 Rail 速度验证"""
        # 6 mm/秒 = 480 步/秒 < 500 (有效)
        valid, _ = MotionValidator.validate_speed(6.0, 'rail')
        assert valid
        
        # 50 mm/秒 = 4000 步/秒 > 500 (无效)
        valid, error = MotionValidator.validate_speed(50.0, 'rail')
        assert not valid
        assert 'Rail' in error
        assert '4000' in error
        assert '500' in error
    
    def test_validate_acceleration_rail(self):
        """测试 Rail 加速度验证"""
        # 3 mm/秒² = 240 步/秒² < 300 (有效)
        valid, _ = MotionValidator.validate_acceleration(3.0, 'rail')
        assert valid
        
        # 30 mm/秒² = 2400 步/秒² > 300 (无效)
        valid, error = MotionValidator.validate_acceleration(30.0, 'rail')
        assert not valid
        assert 'Rail' in error
        assert '2400' in error
        assert '300' in error
    
    def test_validate_motion_params(self):
        """测试完整运动参数验证"""
        # 全部有效
        valid, _ = MotionValidator.validate_motion_params(
            position=90, speed=30, accel=15, axis='pan'
        )
        assert valid
        
        # 位置无效
        valid, error = MotionValidator.validate_motion_params(
            position=200, speed=30, accel=15, axis='pan'
        )
        assert not valid
        assert 'Pan' in error
        
        # 速度无效
        valid, error = MotionValidator.validate_motion_params(
            position=90, speed=150, accel=15, axis='pan'
        )
        assert not valid
        assert '速度' in error or 'speed' in error.lower()


class TestPropertyBasedConversion:
    """基于属性的转换测试"""
    
    @given(st.floats(min_value=-360, max_value=360, allow_nan=False, allow_infinity=False))
    def test_degrees_roundtrip_pan(self, degrees):
        """测试角度转换往返一致性（Pan）"""
        steps = UnitConverter.degrees_to_steps(degrees, 'pan')
        degrees_back = UnitConverter.steps_to_degrees(steps, 'pan')
        # 允许一定的舍入误差
        assert abs(degrees - degrees_back) < 0.5
    
    @given(st.floats(min_value=0, max_value=1000, allow_nan=False, allow_infinity=False))
    def test_mm_roundtrip(self, mm):
        """测试毫米转换往返一致性"""
        steps = UnitConverter.mm_to_steps(mm)
        mm_back = UnitConverter.steps_to_mm(steps)
        # 允许一定的舍入误差
        assert abs(mm - mm_back) < 0.02
    
    @given(st.floats(min_value=PAN_MIN_ANGLE, max_value=PAN_MAX_ANGLE, 
                     allow_nan=False, allow_infinity=False))
    def test_valid_pan_positions(self, position):
        """测试所有有效 Pan 位置都能通过验证"""
        valid, _ = MotionValidator.validate_position(position, 'pan')
        assert valid
    
    @given(st.floats(min_value=TILT_MIN_ANGLE, max_value=TILT_MAX_ANGLE,
                     allow_nan=False, allow_infinity=False))
    def test_valid_tilt_positions(self, position):
        """测试所有有效 Tilt 位置都能通过验证"""
        valid, _ = MotionValidator.validate_position(position, 'tilt')
        assert valid
    
    @given(st.floats(min_value=RAIL_MIN_POS, max_value=RAIL_MAX_POS,
                     allow_nan=False, allow_infinity=False))
    def test_valid_rail_positions(self, position):
        """测试所有有效 Rail 位置都能通过验证"""
        valid, _ = MotionValidator.validate_position(position, 'rail')
        assert valid


class TestConfigValidation:
    """配置验证测试"""
    
    def test_validate_config_with_valid_params(self):
        """测试有效配置"""
        from src.comm.unit_converter import validate_config_motion_params
        
        config = {
            'visual_servo': {
                'max_pan_speed': 30.0,
                'max_tilt_speed': 20.0,
                'max_rail_speed': 6.0
            }
        }
        
        warnings = validate_config_motion_params(config)
        assert len(warnings) == 0
    
    def test_validate_config_with_invalid_rail_speed(self):
        """测试无效 Rail 速度配置"""
        from src.comm.unit_converter import validate_config_motion_params
        
        config = {
            'visual_servo': {
                'max_rail_speed': 50.0  # 超出限制
            }
        }
        
        warnings = validate_config_motion_params(config)
        assert len(warnings) > 0
        assert any('Rail' in w and '速度' in w for w in warnings)
    
    def test_validate_config_with_invalid_pan_speed(self):
        """测试无效 Pan 速度配置"""
        from src.comm.unit_converter import validate_config_motion_params
        
        config = {
            'visual_servo': {
                'max_pan_speed': 150.0  # 超出限制
            }
        }
        
        warnings = validate_config_motion_params(config)
        assert len(warnings) > 0
        assert any('Pan' in w and '速度' in w for w in warnings)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
