/**
 * @file motion.c
 * @brief 运动控制模块实现 - PID 控制器和 S 曲线速度规划
 */

#include "motion.h"
#include "protocol.h"
#include "main.h"
#include <math.h>
#include <string.h>

/* 步进电机参数 */
#define STEPS_PER_REV           200     /* 1.8度步距角 */
#define MICROSTEPPING           16      /* 16 细分 */
#define STEPS_PER_DEGREE        ((STEPS_PER_REV * MICROSTEPPING) / 360.0f)  /* 每度步数 */
#define STEPS_PER_MM            ((STEPS_PER_REV * MICROSTEPPING) / 2.0f)    /* T8 丝杆导程 2mm */

/* 定时器计数频率 (预分频后) */
/* TIM1: APB2 (168MHz) / (167+1) = 1MHz */
/* TIM2/3: APB1 (84MHz) / (83+1) = 1MHz */
#define TIM_COUNTER_FREQ        1000000  /* 1MHz */

/* 外部定时器句柄 */
extern TIM_HandleTypeDef htim1, htim2, htim3;

/* 步数计数器 (在中断中更新) */
volatile int32_t pan_step_count = 0;
volatile int32_t tilt_step_count = 0;
volatile int32_t rail_step_count = 0;

/* ==================== 私有变量 ==================== */

/* 三轴 PID 控制器 */
static PIDController pid_pan;
static PIDController pid_tilt;
static PIDController pid_rail;

/* 当前位置和目标位置 */
static Position current_position = {0, 0, 0};
static Position target_position = {0, 0, 0};

/* 运动配置 */
static MotionProfile motion_profile = {
    .max_velocity = 1000.0f,    /* 最大速度 */
    .max_accel = 500.0f,        /* 最大加速度 */
    .jerk = 200.0f              /* 加加速度 */
};

/* 位置限位 */
static PositionLimits position_limits = {
    .pan_min = -18000,          /* -180.00 度 */
    .pan_max = 18000,           /* +180.00 度 */
    .tilt_min = -9000,          /* -90.00 度 */
    .tilt_max = 9000,           /* +90.00 度 */
    .rail_min = 0,              /* 0 mm */
    .rail_max = 100000          /* 1000.00 mm */
};

/* S 曲线规划状态 */
typedef struct {
    float position;             /* 当前规划位置 */
    float velocity;             /* 当前速度 */
    float acceleration;         /* 当前加速度 */
    float target_position;      /* 目标位置 */
    float direction;            /* 运动方向 (+1/-1) */
    uint8_t phase;              /* 当前阶段 (0-6) */
    bool complete;              /* 是否完成 */
} SCurveState;

static SCurveState scurve_pan;
static SCurveState scurve_tilt;
static SCurveState scurve_rail;

/* 运动状态 */
static bool is_moving = false;
static uint32_t stable_counter = 0;
#define STABLE_THRESHOLD 50     /* 稳定计数阈值 */

/* ==================== PID 控制器实现 ==================== */

void pid_init(PIDController* pid, float kp, float ki, float kd)
{
    pid->kp = kp;
    pid->ki = ki;
    pid->kd = kd;
    pid->integral = 0.0f;
    pid->prev_error = 0.0f;
    pid->output_min = -1000.0f;
    pid->output_max = 1000.0f;
    pid->integral_max = 500.0f;
}

void pid_reset(PIDController* pid)
{
    pid->integral = 0.0f;
    pid->prev_error = 0.0f;
}

void pid_set_limits(PIDController* pid, float output_min, float output_max, float integral_max)
{
    pid->output_min = output_min;
    pid->output_max = output_max;
    pid->integral_max = integral_max;
}

float pid_compute(PIDController* pid, float setpoint, float current, float dt)
{
    /* 防止除零 */
    if (dt <= 0.0f) dt = 0.001f;
    
    float error = setpoint - current;
    float p_term = pid->kp * error;
    
    pid->integral += error * dt;
    if (pid->integral > pid->integral_max) pid->integral = pid->integral_max;
    else if (pid->integral < -pid->integral_max) pid->integral = -pid->integral_max;
    float i_term = pid->ki * pid->integral;
    
    float derivative = (error - pid->prev_error) / dt;
    float d_term = pid->kd * derivative;
    pid->prev_error = error;
    
    float output = p_term + i_term + d_term;
    if (output > pid->output_max) output = pid->output_max;
    else if (output < pid->output_min) output = pid->output_min;
    
    return output;
}

/* ==================== S 曲线速度规划 ==================== */

static void scurve_init(SCurveState* state, float start, float target)
{
    state->position = start;
    state->velocity = 0.0f;
    state->acceleration = 0.0f;
    state->target_position = target;
    state->direction = (target >= start) ? 1.0f : -1.0f;
    state->phase = 0;
    state->complete = (fabsf(target - start) < 0.1f);
}

static float scurve_update(SCurveState* state, float dt)
{
    if (state->complete) return state->target_position;
    
    float distance = fabsf(state->target_position - state->position);
    float max_vel = motion_profile.max_velocity;
    float max_acc = motion_profile.max_accel;
    float jerk = motion_profile.jerk;
    float decel_distance = (state->velocity * state->velocity) / (2.0f * max_acc);
    
    switch (state->phase)
    {
        case 0: /* 加加速 */
            state->acceleration += jerk * dt;
            if (state->acceleration >= max_acc) { state->acceleration = max_acc; state->phase = 1; }
            break;
        case 1: /* 匀加速 */
            if (state->velocity >= max_vel * 0.5f || distance < decel_distance * 2.0f) state->phase = 2;
            break;
        case 2: /* 减加速 */
            state->acceleration -= jerk * dt;
            if (state->acceleration <= 0.0f) { state->acceleration = 0.0f; state->phase = 3; }
            break;
        case 3: /* 匀速 */
            if (distance <= decel_distance * 1.5f) state->phase = 4;
            break;
        case 4: /* 加减速 */
            state->acceleration -= jerk * dt;
            if (state->acceleration <= -max_acc) { state->acceleration = -max_acc; state->phase = 5; }
            break;
        case 5: /* 匀减速 */
            if (state->velocity <= max_vel * 0.1f || distance < 10.0f) state->phase = 6;
            break;
        case 6: /* 减减速 */
            state->acceleration += jerk * dt;
            if (state->acceleration >= 0.0f || distance < 1.0f) {
                state->acceleration = 0.0f;
                state->velocity = 0.0f;
                state->position = state->target_position;
                state->complete = true;
                return state->position;
            }
            break;
    }
    
    state->velocity += state->acceleration * dt * state->direction;
    if (fabsf(state->velocity) > max_vel) state->velocity = max_vel * state->direction;
    if (state->velocity * state->direction < 0) state->velocity = 0;
    
    state->position += state->velocity * dt;
    
    if ((state->direction > 0 && state->position >= state->target_position) ||
        (state->direction < 0 && state->position <= state->target_position))
    {
        state->position = state->target_position;
        state->velocity = 0.0f;
        state->complete = true;
    }
    
    return state->position;
}

/* ==================== 运动控制接口 ==================== */

void motion_init(void)
{
    pid_init(&pid_pan, 2.0f, 0.1f, 0.5f);
    pid_init(&pid_tilt, 2.0f, 0.1f, 0.5f);
    pid_init(&pid_rail, 1.5f, 0.05f, 0.3f);
    
    pid_set_limits(&pid_pan, -1000.0f, 1000.0f, 500.0f);
    pid_set_limits(&pid_tilt, -1000.0f, 1000.0f, 500.0f);
    pid_set_limits(&pid_rail, -1000.0f, 1000.0f, 500.0f);
    
    memset(&current_position, 0, sizeof(Position));
    memset(&target_position, 0, sizeof(Position));
    
    is_moving = false;
    stable_counter = 0;
}

void motion_move_to_position(const Position* target)
{
    Position safe_target = *target;
    
    if (safe_target.pan_angle < position_limits.pan_min) safe_target.pan_angle = position_limits.pan_min;
    if (safe_target.pan_angle > position_limits.pan_max) safe_target.pan_angle = position_limits.pan_max;
    if (safe_target.tilt_angle < position_limits.tilt_min) safe_target.tilt_angle = position_limits.tilt_min;
    if (safe_target.tilt_angle > position_limits.tilt_max) safe_target.tilt_angle = position_limits.tilt_max;
    if (safe_target.rail_pos < position_limits.rail_min) safe_target.rail_pos = position_limits.rail_min;
    if (safe_target.rail_pos > position_limits.rail_max) safe_target.rail_pos = position_limits.rail_max;
    
    target_position = safe_target;
    
    scurve_init(&scurve_pan, (float)current_position.pan_angle, (float)safe_target.pan_angle);
    scurve_init(&scurve_tilt, (float)current_position.tilt_angle, (float)safe_target.tilt_angle);
    scurve_init(&scurve_rail, (float)current_position.rail_pos, (float)safe_target.rail_pos);
    
    pid_reset(&pid_pan);
    pid_reset(&pid_tilt);
    pid_reset(&pid_rail);
    
    is_moving = true;
    stable_counter = 0;
}

void motion_move_to(uint8_t axis, int32_t value)
{
    Position target = target_position;
    
    switch (axis)
    {
        case AXIS_PAN: target.pan_angle = value; break;
        case AXIS_TILT: target.tilt_angle = value; break;
        case AXIS_RAIL: target.rail_pos = value; break;
        case AXIS_ALL: return;
    }
    
    motion_move_to_position(&target);
}

void motion_stop(void)
{
    /* 先停止 PWM 输出 */
    HAL_TIM_PWM_Stop(&htim1, TIM_CHANNEL_1);
    HAL_TIM_PWM_Stop(&htim2, TIM_CHANNEL_1);
    HAL_TIM_PWM_Stop(&htim3, TIM_CHANNEL_1);
    
    /* 更新状态 */
    target_position = current_position;
    scurve_pan.complete = true;
    scurve_tilt.complete = true;
    scurve_rail.complete = true;
    scurve_pan.velocity = 0.0f;
    scurve_tilt.velocity = 0.0f;
    scurve_rail.velocity = 0.0f;
    scurve_pan.acceleration = 0.0f;
    scurve_tilt.acceleration = 0.0f;
    scurve_rail.acceleration = 0.0f;
    is_moving = false;
}

Position motion_get_current(void)
{
    return current_position;
}

int32_t motion_get_position(uint8_t axis)
{
    switch (axis)
    {
        case AXIS_PAN: return current_position.pan_angle;
        case AXIS_TILT: return current_position.tilt_angle;
        case AXIS_RAIL: return current_position.rail_pos;
        default: return 0;
    }
}

bool motion_is_complete(void)
{
    return scurve_pan.complete && scurve_tilt.complete && scurve_rail.complete;
}

bool motion_is_stable(void)
{
    return !is_moving && stable_counter >= STABLE_THRESHOLD;
}

void motion_set_profile(const MotionProfile* profile)
{
    motion_profile = *profile;
}

void motion_set_limits(const PositionLimits* limits)
{
    position_limits = *limits;
}

bool motion_check_limits(const Position* pos)
{
    if (pos->pan_angle < position_limits.pan_min || pos->pan_angle > position_limits.pan_max) return false;
    if (pos->tilt_angle < position_limits.tilt_min || pos->tilt_angle > position_limits.tilt_max) return false;
    if (pos->rail_pos < position_limits.rail_min || pos->rail_pos > position_limits.rail_max) return false;
    return true;
}

void motion_home(uint8_t axis)
{
    Position home = {0, 0, 0};
    
    switch (axis)
    {
        case AXIS_PAN:
            home.tilt_angle = current_position.tilt_angle;
            home.rail_pos = current_position.rail_pos;
            break;
        case AXIS_TILT:
            home.pan_angle = current_position.pan_angle;
            home.rail_pos = current_position.rail_pos;
            break;
        case AXIS_RAIL:
            home.pan_angle = current_position.pan_angle;
            home.tilt_angle = current_position.tilt_angle;
            break;
        case AXIS_ALL:
            break;
    }
    
    motion_move_to_position(&home);
}

static void set_stepper_frequency(TIM_HandleTypeDef* htim, uint32_t freq_hz)
{
    if (freq_hz == 0)
    {
        HAL_TIM_PWM_Stop(htim, TIM_CHANNEL_1);
        return;
    }
    
    if (freq_hz > 50000) freq_hz = 50000;
    if (freq_hz < 10) freq_hz = 10;
    
    uint32_t arr = (TIM_COUNTER_FREQ / freq_hz) - 1;
    if (arr > 65535) arr = 65535;
    if (arr < 1) arr = 1;  /* 防止 ARR 为 0 */
    
    /* 禁用定时器更新中断，防止在修改 ARR 时触发中断 */
    __HAL_TIM_DISABLE_IT(htim, TIM_IT_UPDATE);
    
    __HAL_TIM_SET_AUTORELOAD(htim, arr);
    __HAL_TIM_SET_COMPARE(htim, TIM_CHANNEL_1, arr / 2);
    
    /* 生成更新事件以立即加载新的 ARR 值 */
    htim->Instance->EGR = TIM_EGR_UG;
    
    /* 清除更新中断标志 (EGR 会产生更新事件) */
    __HAL_TIM_CLEAR_FLAG(htim, TIM_FLAG_UPDATE);
    
    /* 重新启用更新中断 */
    __HAL_TIM_ENABLE_IT(htim, TIM_IT_UPDATE);
    
    HAL_TIM_PWM_Start(htim, TIM_CHANNEL_1);
}

void motion_update(void)
{
    const float dt = 0.001f;
    
    if (!is_moving)
    {
        if (stable_counter < STABLE_THRESHOLD) stable_counter++;
        return;
    }
    
    float planned_pan = scurve_update(&scurve_pan, dt);
    float planned_tilt = scurve_update(&scurve_tilt, dt);
    float planned_rail = scurve_update(&scurve_rail, dt);
    
    float actual_pan = (float)pan_step_count / STEPS_PER_DEGREE * 100.0f;
    float actual_tilt = (float)tilt_step_count / STEPS_PER_DEGREE * 100.0f;
    float actual_rail = (float)rail_step_count / STEPS_PER_MM * 100.0f;
    
    float output_pan = pid_compute(&pid_pan, planned_pan, actual_pan, dt);
    float output_tilt = pid_compute(&pid_tilt, planned_tilt, actual_tilt, dt);
    float output_rail = pid_compute(&pid_rail, planned_rail, actual_rail, dt);
    
    HAL_GPIO_WritePin(PAN_DIR_GPIO_Port, PAN_DIR_Pin, output_pan >= 0 ? GPIO_PIN_SET : GPIO_PIN_RESET);
    HAL_GPIO_WritePin(TILT_DIR_GPIO_Port, TILT_DIR_Pin, output_tilt >= 0 ? GPIO_PIN_SET : GPIO_PIN_RESET);
    HAL_GPIO_WritePin(RAIL_DIR_GPIO_Port, RAIL_DIR_Pin, output_rail >= 0 ? GPIO_PIN_SET : GPIO_PIN_RESET);
    
    float velocity_pan = fabsf(scurve_pan.velocity);
    float velocity_tilt = fabsf(scurve_tilt.velocity);
    float velocity_rail = fabsf(scurve_rail.velocity);
    
    uint32_t freq_pan = (uint32_t)(velocity_pan * STEPS_PER_DEGREE / 100.0f);
    uint32_t freq_tilt = (uint32_t)(velocity_tilt * STEPS_PER_DEGREE / 100.0f);
    uint32_t freq_rail = (uint32_t)(velocity_rail * STEPS_PER_MM / 100.0f);
    
    set_stepper_frequency(&htim1, freq_pan);
    set_stepper_frequency(&htim2, freq_tilt);
    set_stepper_frequency(&htim3, freq_rail);
    
    current_position.pan_angle = (int32_t)actual_pan;
    current_position.tilt_angle = (int32_t)actual_tilt;
    current_position.rail_pos = (int32_t)actual_rail;
    
    if (motion_is_complete())
    {
        is_moving = false;
        stable_counter = 0;
        set_stepper_frequency(&htim1, 0);
        set_stepper_frequency(&htim2, 0);
        set_stepper_frequency(&htim3, 0);
    }
}

void motion_plan_s_curve(const Position* start, const Position* end, const MotionProfile* profile)
{
    if (profile) motion_profile = *profile;
    current_position = *start;
    motion_move_to_position(end);
}

/* ==================== 动态参数配置函数 ==================== */

void motion_set_max_velocity(float velocity)
{
    if (velocity > 0 && velocity < 10000.0f) {
        motion_profile.max_velocity = velocity;
    }
}

void motion_set_max_accel(float accel)
{
    if (accel > 0 && accel < 5000.0f) {
        motion_profile.max_accel = accel;
    }
}

void motion_set_pid_p(uint8_t axis, float p)
{
    if (p < 0) return;
    
    switch (axis) {
        case AXIS_PAN:
            pid_pan.kp = p;
            break;
        case AXIS_TILT:
            pid_tilt.kp = p;
            break;
        case AXIS_RAIL:
            pid_rail.kp = p;
            break;
        case AXIS_ALL:
            pid_pan.kp = p;
            pid_tilt.kp = p;
            pid_rail.kp = p;
            break;
    }
}

void motion_set_pid_i(uint8_t axis, float i)
{
    if (i < 0) return;
    
    switch (axis) {
        case AXIS_PAN:
            pid_pan.ki = i;
            break;
        case AXIS_TILT:
            pid_tilt.ki = i;
            break;
        case AXIS_RAIL:
            pid_rail.ki = i;
            break;
        case AXIS_ALL:
            pid_pan.ki = i;
            pid_tilt.ki = i;
            pid_rail.ki = i;
            break;
    }
}

void motion_set_pid_d(uint8_t axis, float d)
{
    if (d < 0) return;
    
    switch (axis) {
        case AXIS_PAN:
            pid_pan.kd = d;
            break;
        case AXIS_TILT:
            pid_tilt.kd = d;
            break;
        case AXIS_RAIL:
            pid_rail.kd = d;
            break;
        case AXIS_ALL:
            pid_pan.kd = d;
            pid_tilt.kd = d;
            pid_rail.kd = d;
            break;
    }
}

void motion_set_limit_min(uint8_t axis, int32_t value)
{
    switch (axis) {
        case AXIS_PAN:
            position_limits.pan_min = value;
            break;
        case AXIS_TILT:
            position_limits.tilt_min = value;
            break;
        case AXIS_RAIL:
            position_limits.rail_min = value;
            break;
        case AXIS_ALL:
            position_limits.pan_min = value;
            position_limits.tilt_min = value;
            position_limits.rail_min = value;
            break;
    }
}

void motion_set_limit_max(uint8_t axis, int32_t value)
{
    switch (axis) {
        case AXIS_PAN:
            position_limits.pan_max = value;
            break;
        case AXIS_TILT:
            position_limits.tilt_max = value;
            break;
        case AXIS_RAIL:
            position_limits.rail_max = value;
            break;
        case AXIS_ALL:
            position_limits.pan_max = value;
            position_limits.tilt_max = value;
            position_limits.rail_max = value;
            break;
    }
}
