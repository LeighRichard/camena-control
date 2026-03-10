/**
 * @file motion.h
 * @brief 运动控制模块
 */

#ifndef __MOTION_H
#define __MOTION_H

#include <stdint.h>
#include <stdbool.h>

/* 位置结构 (0.01度/0.01mm 为单位) */
typedef struct {
    int32_t pan_angle;      /* 水平角度 */
    int32_t tilt_angle;     /* 俯仰角度 */
    int32_t rail_pos;       /* 滑轨位置 */
} Position;

/* PID 参数 */
typedef struct {
    float kp;               /* 比例系数 */
    float ki;               /* 积分系数 */
    float kd;               /* 微分系数 */
    float integral;         /* 积分累积 */
    float prev_error;       /* 上次误差 */
    float output_min;       /* 输出下限 */
    float output_max;       /* 输出上限 */
    float integral_max;     /* 积分限幅 */
} PIDController;

/* 运动配置 */
typedef struct {
    float max_velocity;     /* 最大速度 */
    float max_accel;        /* 最大加速度 */
    float jerk;             /* 加加速度 (S曲线) */
} MotionProfile;

/* 限位范围 */
typedef struct {
    int32_t pan_min;
    int32_t pan_max;
    int32_t tilt_min;
    int32_t tilt_max;
    int32_t rail_min;
    int32_t rail_max;
} PositionLimits;

/* 函数声明 - PID 控制 */
void pid_init(PIDController* pid, float kp, float ki, float kd);
void pid_reset(PIDController* pid);
float pid_compute(PIDController* pid, float setpoint, float current, float dt);
void pid_set_limits(PIDController* pid, float output_min, float output_max, float integral_max);

/* 函数声明 - 运动控制 */
void motion_init(void);
void motion_move_to_position(const Position* target);
void motion_move_to(uint8_t axis, int32_t value);
void motion_stop(void);
Position motion_get_current(void);
int32_t motion_get_position(uint8_t axis);
bool motion_is_complete(void);
bool motion_is_stable(void);
void motion_set_profile(const MotionProfile* profile);
void motion_set_limits(const PositionLimits* limits);
bool motion_check_limits(const Position* pos);
void motion_home(uint8_t axis);
void motion_update(void);

/* 函数声明 - S曲线规划 */
void motion_plan_s_curve(const Position* start, const Position* end, const MotionProfile* profile);

/* 函数声明 - 动态参数配置 (用于配置指令) */
void motion_set_max_velocity(float velocity);
void motion_set_max_accel(float accel);
void motion_set_pid_p(uint8_t axis, float p);
void motion_set_pid_i(uint8_t axis, float i);
void motion_set_pid_d(uint8_t axis, float d);
void motion_set_limit_min(uint8_t axis, int32_t value);
void motion_set_limit_max(uint8_t axis, int32_t value);

/* 轴定义 (与 protocol.h 保持一致) */
#ifndef AXIS_PAN
#define AXIS_PAN      0x00
#define AXIS_TILT     0x01
#define AXIS_RAIL     0x02
#define AXIS_ALL      0xFF
#endif

#endif /* __MOTION_H */
