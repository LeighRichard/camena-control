"""
Compatibility PID controller for motion property tests.

The visual-servo runtime PID implementation lives in `control.pid`.
This module provides the minimal API expected by `tests/test_motion_properties.py`.
"""

from dataclasses import dataclass


@dataclass
class PIDController:
    """Simple bounded PID controller with a test-friendly constructor."""
    kp: float = 1.0
    ki: float = 0.0
    kd: float = 0.0
    output_min: float = -1000.0
    output_max: float = 1000.0
    integral_limit: float = 1e6

    def __post_init__(self):
        self._integral = 0.0
        self._prev_error = 0.0

    def reset(self):
        self._integral = 0.0
        self._prev_error = 0.0

    def compute(self, setpoint: float, current: float, dt: float) -> float:
        if dt <= 0:
            dt = 0.001

        error = setpoint - current
        self._integral += error * dt
        if self._integral > self.integral_limit:
            self._integral = self.integral_limit
        elif self._integral < -self.integral_limit:
            self._integral = -self.integral_limit

        derivative = (error - self._prev_error) / dt
        self._prev_error = error

        output = self.kp * error + self.ki * self._integral + self.kd * derivative
        if output > self.output_max:
            return self.output_max
        if output < self.output_min:
            return self.output_min
        return output
