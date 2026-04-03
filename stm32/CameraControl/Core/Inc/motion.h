/**
 * @file motion.h
 * @brief Motion control interface for the STM32 motor controller
 */

#ifndef __MOTION_H
#define __MOTION_H

#include <stdbool.h>
#include <stdint.h>

/* Position uses 0.01 degree for pan/tilt and 0.01 mm for rail. */
typedef struct {
    int32_t pan_angle;
    int32_t tilt_angle;
    int32_t rail_pos;
} Position;

typedef struct {
    float kp;
    float ki;
    float kd;
    float integral;
    float prev_error;
    float output_min;
    float output_max;
    float integral_max;
} PIDController;

typedef struct {
    float max_velocity;
    float max_accel;
    float jerk;
} MotionProfile;

typedef struct {
    int32_t pan_min;
    int32_t pan_max;
    int32_t tilt_min;
    int32_t tilt_max;
    int32_t rail_min;
    int32_t rail_max;
} PositionLimits;

void pid_init(PIDController* pid, float kp, float ki, float kd);
void pid_reset(PIDController* pid);
float pid_compute(PIDController* pid, float setpoint, float current, float dt);
void pid_set_limits(PIDController* pid, float output_min, float output_max, float integral_max);

void motion_init(void);
void motion_move_to_position(const Position* target);
void motion_move_to(uint8_t axis, int32_t value);
void motion_stop(void);
void motion_stop_axis(uint8_t axis);
Position motion_get_current(void);
int32_t motion_get_position(uint8_t axis);
bool motion_is_complete(void);
bool motion_is_stable(void);
void motion_set_profile(const MotionProfile* profile);
void motion_set_limits(const PositionLimits* limits);
bool motion_check_limits(const Position* pos);
void motion_home(uint8_t axis);
void motion_update(void);

void motion_plan_s_curve(const Position* start, const Position* end, const MotionProfile* profile);

void motion_set_max_velocity(float velocity);
void motion_set_max_accel(float accel);
void motion_set_pid_p(uint8_t axis, float p);
void motion_set_pid_i(uint8_t axis, float i);
void motion_set_pid_d(uint8_t axis, float d);
void motion_set_limit_min(uint8_t axis, int32_t value);
void motion_set_limit_max(uint8_t axis, int32_t value);
void motion_set_velocity(uint8_t axis, float velocity);
void motion_stop_all(void);

#ifndef AXIS_PAN
#define AXIS_PAN    0x00
#define AXIS_TILT   0x01
#define AXIS_RAIL   0x02
#define AXIS_ALL    0xFF
#endif

#endif /* __MOTION_H */
