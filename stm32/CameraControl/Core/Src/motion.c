/**
 * @file motion.c
 * @brief Hybrid motion backend: pan/tilt PWM servo + rail stepper.
 */

#include "motion.h"
#include "main.h"
#include <math.h>
#include <string.h>

/* Rail stepper parameters */
#define STEPS_PER_REV           200.0f
#define MICROSTEPPING           16.0f
#define STEPS_PER_MM            ((STEPS_PER_REV * MICROSTEPPING) / 2.0f) /* T8 lead screw: 2mm pitch */

/* Servo output parameters */
#define SERVO_PWM_PERIOD_US     20000U
#define SERVO_MIN_PULSE_US      500U
#define SERVO_CENTER_PULSE_US   1500U
#define SERVO_MAX_PULSE_US      2500U

/* Physical travel range derived from the PWM gimbal manual */
#define PAN_MIN_CDEG            (-13500)
#define PAN_MAX_CDEG            (13500)
#define TILT_MIN_CDEG           (-11000)
#define TILT_MAX_CDEG           (11000)
#define RAIL_MIN_CMM            (0)
#define RAIL_MAX_CMM            (50000)

/* Jetson-side safety caps */
#define PAN_MAX_SPEED_STEPS     1000U
#define TILT_MAX_SPEED_STEPS    800U
#define RAIL_MAX_SPEED_STEPS    16000U

#define PAN_MAX_VEL_CENTI       3000.0f
#define TILT_MAX_VEL_CENTI      2000.0f
#define RAIL_MAX_VEL_CENTI      600.0f

#define PAN_MAX_ACCEL_CENTI     4500.0f
#define TILT_MAX_ACCEL_CENTI    4500.0f
#define RAIL_MAX_ACCEL_CENTI    1000.0f

/* Timer counter frequency after prescaler */
#define TIM_COUNTER_FREQ        1000000U
#define SERVO_UPDATE_DT         0.001f
#define STABLE_THRESHOLD        50U

extern TIM_HandleTypeDef htim1;
extern TIM_HandleTypeDef htim2;
extern TIM_HandleTypeDef htim3;

/*
 * Keep these globals for compatibility with the generated interrupt file.
 * Pan/tilt are servo-driven now, so only rail_step_count is used actively.
 */
volatile int32_t pan_step_count = 0;
volatile int32_t tilt_step_count = 0;
volatile int32_t rail_step_count = 0;

typedef struct {
    float current_cdeg;
    float target_cdeg;
    float velocity_cmd_cdeg_s;
    bool velocity_mode;
} ServoAxisState;

typedef struct {
    float position;
    float velocity;
    float acceleration;
    float target_position;
    float target_velocity;
    float direction;
    uint8_t phase;
    uint8_t complete;
} SCurveState;

static PIDController pid_pan;
static PIDController pid_tilt;
static PIDController pid_rail;

static Position current_position = {0, 0, 0};
static Position target_position = {0, 0, 0};

static MotionProfile motion_profile = {
    .max_velocity = 3000.0f,
    .max_accel = 4500.0f,
    .jerk = 1200.0f,
};

static PositionLimits position_limits = {
    .pan_min = PAN_MIN_CDEG,
    .pan_max = PAN_MAX_CDEG,
    .tilt_min = TILT_MIN_CDEG,
    .tilt_max = TILT_MAX_CDEG,
    .rail_min = RAIL_MIN_CMM,
    .rail_max = RAIL_MAX_CMM,
};

static ServoAxisState servo_pan = {0};
static ServoAxisState servo_tilt = {0};
static SCurveState scurve_rail = {0};

static bool is_moving = false;
static uint32_t stable_counter = 0;

static float clampf_value(float value, float min_value, float max_value)
{
    if (value < min_value) return min_value;
    if (value > max_value) return max_value;
    return value;
}

static int32_t clamp_i32(int32_t value, int32_t min_value, int32_t max_value)
{
    if (value < min_value) return min_value;
    if (value > max_value) return max_value;
    return value;
}

static float get_axis_velocity_limit(uint8_t axis)
{
    float safe_limit;

    switch (axis)
    {
        case AXIS_PAN: safe_limit = PAN_MAX_VEL_CENTI; break;
        case AXIS_TILT: safe_limit = TILT_MAX_VEL_CENTI; break;
        case AXIS_RAIL: safe_limit = RAIL_MAX_VEL_CENTI; break;
        default: safe_limit = PAN_MAX_VEL_CENTI; break;
    }

    if (motion_profile.max_velocity <= 0.0f)
    {
        return safe_limit;
    }

    return fminf(motion_profile.max_velocity, safe_limit);
}

static float get_axis_accel_limit(uint8_t axis)
{
    float safe_limit;

    switch (axis)
    {
        case AXIS_PAN: safe_limit = PAN_MAX_ACCEL_CENTI; break;
        case AXIS_TILT: safe_limit = TILT_MAX_ACCEL_CENTI; break;
        case AXIS_RAIL: safe_limit = RAIL_MAX_ACCEL_CENTI; break;
        default: safe_limit = PAN_MAX_ACCEL_CENTI; break;
    }

    if (motion_profile.max_accel <= 0.0f)
    {
        return safe_limit;
    }

    return fminf(motion_profile.max_accel, safe_limit);
}

static float centi_velocity_to_step_frequency(float velocity_centi)
{
    return fabsf(velocity_centi) * STEPS_PER_MM / 100.0f;
}

static float servo_steps_to_centi_velocity(float steps_per_sec)
{
    const float steps_per_degree = (STEPS_PER_REV * MICROSTEPPING) / 360.0f;
    return (steps_per_sec / steps_per_degree) * 100.0f;
}

static bool has_active_velocity(const SCurveState* state)
{
    return fabsf(state->target_velocity) > 0.0001f;
}

static void scurve_init(SCurveState* state, float start, float target)
{
    state->position = start;
    state->velocity = 0.0f;
    state->acceleration = 0.0f;
    state->target_position = target;
    state->target_velocity = 0.0f;
    state->direction = (target >= start) ? 1.0f : -1.0f;
    state->phase = 0;
    state->complete = (fabsf(target - start) < 0.1f) ? 1u : 0u;
}

static float scurve_update(SCurveState* state, float dt, float max_vel, float max_acc, float jerk)
{
    float distance;
    float decel_distance;

    if (state->complete)
    {
        return state->target_position;
    }

    distance = fabsf(state->target_position - state->position);
    decel_distance = (state->velocity * state->velocity) / (2.0f * fmaxf(max_acc, 1.0f));

    switch (state->phase)
    {
        case 0:
            state->acceleration += jerk * dt;
            if (state->acceleration >= max_acc) { state->acceleration = max_acc; state->phase = 1; }
            break;
        case 1:
            if (state->velocity >= max_vel * 0.5f || distance < decel_distance * 2.0f) state->phase = 2;
            break;
        case 2:
            state->acceleration -= jerk * dt;
            if (state->acceleration <= 0.0f) { state->acceleration = 0.0f; state->phase = 3; }
            break;
        case 3:
            if (distance <= decel_distance * 1.5f) state->phase = 4;
            break;
        case 4:
            state->acceleration -= jerk * dt;
            if (state->acceleration <= -max_acc) { state->acceleration = -max_acc; state->phase = 5; }
            break;
        case 5:
            if (state->velocity <= max_vel * 0.1f || distance < 10.0f) state->phase = 6;
            break;
        case 6:
            state->acceleration += jerk * dt;
            if (state->acceleration >= 0.0f || distance < 1.0f)
            {
                state->acceleration = 0.0f;
                state->velocity = 0.0f;
                state->position = state->target_position;
                state->complete = 1u;
                return state->position;
            }
            break;
        default:
            break;
    }

    state->velocity += state->acceleration * dt * state->direction;
    if (fabsf(state->velocity) > max_vel)
    {
        state->velocity = max_vel * state->direction;
    }
    if (state->velocity * state->direction < 0.0f)
    {
        state->velocity = 0.0f;
    }

    state->position += state->velocity * dt;

    if ((state->direction > 0.0f && state->position >= state->target_position) ||
        (state->direction < 0.0f && state->position <= state->target_position))
    {
        state->position = state->target_position;
        state->velocity = 0.0f;
        state->complete = 1u;
    }

    return state->position;
}

static uint32_t servo_angle_to_pulse_us(int32_t angle_cdeg, int32_t min_cdeg, int32_t max_cdeg)
{
    int32_t clamped = clamp_i32(angle_cdeg, min_cdeg, max_cdeg);
    float ratio = (float)(clamped - min_cdeg) / (float)(max_cdeg - min_cdeg);
    float pulse = (float)SERVO_MIN_PULSE_US +
                  ratio * (float)(SERVO_MAX_PULSE_US - SERVO_MIN_PULSE_US);

    if (pulse < (float)SERVO_MIN_PULSE_US) pulse = (float)SERVO_MIN_PULSE_US;
    if (pulse > (float)SERVO_MAX_PULSE_US) pulse = (float)SERVO_MAX_PULSE_US;
    return (uint32_t)lroundf(pulse);
}

static void servo_write_pulse_us(TIM_HandleTypeDef* htim, uint32_t pulse_us)
{
    if (pulse_us > SERVO_PWM_PERIOD_US)
    {
        pulse_us = SERVO_PWM_PERIOD_US;
    }

    __HAL_TIM_SET_COMPARE(htim, TIM_CHANNEL_1, pulse_us);
}

static void servo_sync_output(uint8_t axis)
{
    switch (axis)
    {
        case AXIS_PAN:
            servo_write_pulse_us(
                &htim1,
                servo_angle_to_pulse_us(
                    (int32_t)lroundf(servo_pan.current_cdeg),
                    position_limits.pan_min,
                    position_limits.pan_max
                )
            );
            break;

        case AXIS_TILT:
            servo_write_pulse_us(
                &htim2,
                servo_angle_to_pulse_us(
                    (int32_t)lroundf(servo_tilt.current_cdeg),
                    position_limits.tilt_min,
                    position_limits.tilt_max
                )
            );
            break;

        default:
            break;
    }
}

static bool servo_update_axis(
    uint8_t axis,
    ServoAxisState* state,
    int32_t* current_field,
    int32_t* target_field,
    int32_t min_limit,
    int32_t max_limit,
    float max_speed_cdeg_s
)
{
    float max_delta = fmaxf(max_speed_cdeg_s * SERVO_UPDATE_DT, 1.0f);
    bool active = false;

    state->target_cdeg = clampf_value(state->target_cdeg, (float)min_limit, (float)max_limit);

    if (state->velocity_mode)
    {
        float velocity = clampf_value(
            state->velocity_cmd_cdeg_s,
            -max_speed_cdeg_s,
            max_speed_cdeg_s
        );

        if (fabsf(velocity) < 0.5f)
        {
            state->velocity_mode = false;
            state->velocity_cmd_cdeg_s = 0.0f;
            state->target_cdeg = state->current_cdeg;
        }
        else
        {
            state->current_cdeg += velocity * SERVO_UPDATE_DT;
            state->current_cdeg = clampf_value(
                state->current_cdeg,
                (float)min_limit,
                (float)max_limit
            );
            state->target_cdeg = state->current_cdeg;
            active = true;
        }
    }
    else
    {
        float error = state->target_cdeg - state->current_cdeg;

        if (fabsf(error) > 0.5f)
        {
            float delta = clampf_value(error, -max_delta, max_delta);
            state->current_cdeg += delta;

            if (fabsf(state->target_cdeg - state->current_cdeg) <= 0.5f)
            {
                state->current_cdeg = state->target_cdeg;
            }

            active = true;
        }
    }

    *current_field = (int32_t)lroundf(state->current_cdeg);
    *target_field = (int32_t)lroundf(state->target_cdeg);
    servo_sync_output(axis);
    return active;
}

static void set_rail_stepper_frequency(uint32_t freq_hz)
{
    uint32_t arr;

    if (freq_hz == 0U)
    {
        HAL_TIM_PWM_Stop(&htim3, TIM_CHANNEL_1);
        return;
    }

    if (freq_hz > RAIL_MAX_SPEED_STEPS)
    {
        freq_hz = RAIL_MAX_SPEED_STEPS;
    }
    if (freq_hz < 10U)
    {
        freq_hz = 10U;
    }

    arr = (TIM_COUNTER_FREQ / freq_hz) - 1U;
    if (arr > 65535U) arr = 65535U;
    if (arr < 1U) arr = 1U;

    __HAL_TIM_DISABLE_IT(&htim3, TIM_IT_UPDATE);
    __HAL_TIM_SET_AUTORELOAD(&htim3, arr);
    __HAL_TIM_SET_COMPARE(&htim3, TIM_CHANNEL_1, arr / 2U);
    htim3.Instance->EGR = TIM_EGR_UG;
    __HAL_TIM_CLEAR_FLAG(&htim3, TIM_FLAG_UPDATE);
    __HAL_TIM_ENABLE_IT(&htim3, TIM_IT_UPDATE);

    HAL_TIM_PWM_Start(&htim3, TIM_CHANNEL_1);
}

static void stop_axis_state(uint8_t axis)
{
    switch (axis)
    {
        case AXIS_PAN:
            servo_pan.velocity_mode = false;
            servo_pan.velocity_cmd_cdeg_s = 0.0f;
            servo_pan.target_cdeg = servo_pan.current_cdeg;
            target_position.pan_angle = (int32_t)lroundf(servo_pan.current_cdeg);
            servo_sync_output(AXIS_PAN);
            pid_reset(&pid_pan);
            break;

        case AXIS_TILT:
            servo_tilt.velocity_mode = false;
            servo_tilt.velocity_cmd_cdeg_s = 0.0f;
            servo_tilt.target_cdeg = servo_tilt.current_cdeg;
            target_position.tilt_angle = (int32_t)lroundf(servo_tilt.current_cdeg);
            servo_sync_output(AXIS_TILT);
            pid_reset(&pid_tilt);
            break;

        case AXIS_RAIL:
            set_rail_stepper_frequency(0U);
            scurve_rail.position = (float)current_position.rail_pos;
            scurve_rail.target_position = (float)current_position.rail_pos;
            scurve_rail.target_velocity = 0.0f;
            scurve_rail.velocity = 0.0f;
            scurve_rail.acceleration = 0.0f;
            scurve_rail.phase = 0u;
            scurve_rail.complete = 1u;
            target_position.rail_pos = current_position.rail_pos;
            pid_reset(&pid_rail);
            break;

        default:
            break;
    }
}

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
    float error;
    float p_term;
    float i_term;
    float derivative;
    float d_term;
    float output;

    if (dt <= 0.0f) dt = 0.001f;

    error = setpoint - current;
    p_term = pid->kp * error;

    pid->integral += error * dt;
    if (pid->integral > pid->integral_max) pid->integral = pid->integral_max;
    else if (pid->integral < -pid->integral_max) pid->integral = -pid->integral_max;
    i_term = pid->ki * pid->integral;

    derivative = (error - pid->prev_error) / dt;
    d_term = pid->kd * derivative;
    pid->prev_error = error;

    output = p_term + i_term + d_term;
    if (output > pid->output_max) output = pid->output_max;
    else if (output < pid->output_min) output = pid->output_min;

    return output;
}

void motion_init(void)
{
    pid_init(&pid_pan, 2.0f, 0.1f, 0.5f);
    pid_init(&pid_tilt, 2.0f, 0.1f, 0.5f);
    pid_init(&pid_rail, 1.5f, 0.05f, 0.3f);

    pid_set_limits(&pid_pan, -PAN_MAX_VEL_CENTI, PAN_MAX_VEL_CENTI, 1500.0f);
    pid_set_limits(&pid_tilt, -TILT_MAX_VEL_CENTI, TILT_MAX_VEL_CENTI, 1000.0f);
    pid_set_limits(&pid_rail, -RAIL_MAX_VEL_CENTI, RAIL_MAX_VEL_CENTI, 300.0f);

    memset(&current_position, 0, sizeof(current_position));
    memset(&target_position, 0, sizeof(target_position));
    memset(&servo_pan, 0, sizeof(servo_pan));
    memset(&servo_tilt, 0, sizeof(servo_tilt));
    memset(&scurve_rail, 0, sizeof(scurve_rail));
    scurve_rail.complete = 1u;

    servo_pan.current_cdeg = 0.0f;
    servo_pan.target_cdeg = 0.0f;
    servo_tilt.current_cdeg = 0.0f;
    servo_tilt.target_cdeg = 0.0f;

    if (HAL_TIM_PWM_Start(&htim1, TIM_CHANNEL_1) != HAL_OK)
    {
        Error_Handler();
    }
    if (HAL_TIM_PWM_Start(&htim2, TIM_CHANNEL_1) != HAL_OK)
    {
        Error_Handler();
    }

    servo_write_pulse_us(&htim1, SERVO_CENTER_PULSE_US);
    servo_write_pulse_us(&htim2, SERVO_CENTER_PULSE_US);

    is_moving = false;
    stable_counter = 0U;
}

void motion_move_to_position(const Position* target)
{
    Position safe_target = *target;

    safe_target.pan_angle = clamp_i32(safe_target.pan_angle, position_limits.pan_min, position_limits.pan_max);
    safe_target.tilt_angle = clamp_i32(safe_target.tilt_angle, position_limits.tilt_min, position_limits.tilt_max);
    safe_target.rail_pos = clamp_i32(safe_target.rail_pos, position_limits.rail_min, position_limits.rail_max);

    target_position = safe_target;

    servo_pan.target_cdeg = (float)safe_target.pan_angle;
    servo_pan.velocity_mode = false;
    servo_pan.velocity_cmd_cdeg_s = 0.0f;

    servo_tilt.target_cdeg = (float)safe_target.tilt_angle;
    servo_tilt.velocity_mode = false;
    servo_tilt.velocity_cmd_cdeg_s = 0.0f;

    scurve_init(&scurve_rail, (float)current_position.rail_pos, (float)safe_target.rail_pos);

    pid_reset(&pid_pan);
    pid_reset(&pid_tilt);
    pid_reset(&pid_rail);

    is_moving = true;
    stable_counter = 0U;
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
        default: return;
    }

    motion_move_to_position(&target);
}

void motion_stop(void)
{
    motion_stop_all();
}

void motion_stop_axis(uint8_t axis)
{
    if (axis == AXIS_ALL)
    {
        motion_stop_all();
        return;
    }

    stop_axis_state(axis);
    is_moving = !motion_is_complete();
    stable_counter = 0U;
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
    bool pan_done = !servo_pan.velocity_mode &&
                    fabsf(servo_pan.target_cdeg - servo_pan.current_cdeg) <= 0.5f;
    bool tilt_done = !servo_tilt.velocity_mode &&
                     fabsf(servo_tilt.target_cdeg - servo_tilt.current_cdeg) <= 0.5f;
    bool rail_done = scurve_rail.complete && !has_active_velocity(&scurve_rail);

    return pan_done && tilt_done && rail_done;
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
    servo_pan.target_cdeg = clampf_value(
        servo_pan.target_cdeg,
        (float)position_limits.pan_min,
        (float)position_limits.pan_max
    );
    servo_tilt.target_cdeg = clampf_value(
        servo_tilt.target_cdeg,
        (float)position_limits.tilt_min,
        (float)position_limits.tilt_max
    );
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
    Position home = current_position;

    switch (axis)
    {
        case AXIS_PAN:
            home.pan_angle = 0;
            break;
        case AXIS_TILT:
            home.tilt_angle = 0;
            break;
        case AXIS_RAIL:
            home.rail_pos = 0;
            break;
        case AXIS_ALL:
            home.pan_angle = 0;
            home.tilt_angle = 0;
            home.rail_pos = 0;
            break;
        default:
            return;
    }

    motion_move_to_position(&home);
}

void motion_update(void)
{
    bool pan_active;
    bool tilt_active;
    bool rail_active = false;
    float actual_rail;

    pan_active = servo_update_axis(
        AXIS_PAN,
        &servo_pan,
        &current_position.pan_angle,
        &target_position.pan_angle,
        position_limits.pan_min,
        position_limits.pan_max,
        get_axis_velocity_limit(AXIS_PAN)
    );

    tilt_active = servo_update_axis(
        AXIS_TILT,
        &servo_tilt,
        &current_position.tilt_angle,
        &target_position.tilt_angle,
        position_limits.tilt_min,
        position_limits.tilt_max,
        get_axis_velocity_limit(AXIS_TILT)
    );

    actual_rail = ((float)rail_step_count / STEPS_PER_MM) * 100.0f;
    current_position.rail_pos = (int32_t)lroundf(actual_rail);

    if (has_active_velocity(&scurve_rail))
    {
        HAL_GPIO_WritePin(
            RAIL_DIR_GPIO_Port,
            RAIL_DIR_Pin,
            scurve_rail.target_velocity >= 0.0f ? GPIO_PIN_SET : GPIO_PIN_RESET
        );
        set_rail_stepper_frequency(
            (uint32_t)fminf(fabsf(scurve_rail.target_velocity), (float)RAIL_MAX_SPEED_STEPS)
        );
        rail_active = true;
    }
    else if (!scurve_rail.complete)
    {
        float planned_rail = scurve_update(
            &scurve_rail,
            SERVO_UPDATE_DT,
            get_axis_velocity_limit(AXIS_RAIL),
            get_axis_accel_limit(AXIS_RAIL),
            motion_profile.jerk
        );
        float output_rail = pid_compute(&pid_rail, planned_rail, actual_rail, SERVO_UPDATE_DT);
        uint32_t freq_rail = (uint32_t)centi_velocity_to_step_frequency(output_rail);

        HAL_GPIO_WritePin(
            RAIL_DIR_GPIO_Port,
            RAIL_DIR_Pin,
            output_rail >= 0.0f ? GPIO_PIN_SET : GPIO_PIN_RESET
        );
        set_rail_stepper_frequency(freq_rail);
        rail_active = true;
    }
    else
    {
        set_rail_stepper_frequency(0U);
    }

    target_position.rail_pos = (int32_t)lroundf(scurve_rail.target_position);

    is_moving = pan_active || tilt_active || rail_active;
    if (!is_moving)
    {
        if (stable_counter < STABLE_THRESHOLD) stable_counter++;
        return;
    }

    stable_counter = 0U;
}

void motion_plan_s_curve(const Position* start, const Position* end, const MotionProfile* profile)
{
    if (profile != NULL)
    {
        motion_profile = *profile;
    }

    current_position = *start;
    target_position = *start;

    servo_pan.current_cdeg = (float)clamp_i32(start->pan_angle, position_limits.pan_min, position_limits.pan_max);
    servo_pan.target_cdeg = servo_pan.current_cdeg;
    servo_pan.velocity_cmd_cdeg_s = 0.0f;
    servo_pan.velocity_mode = false;

    servo_tilt.current_cdeg = (float)clamp_i32(start->tilt_angle, position_limits.tilt_min, position_limits.tilt_max);
    servo_tilt.target_cdeg = servo_tilt.current_cdeg;
    servo_tilt.velocity_cmd_cdeg_s = 0.0f;
    servo_tilt.velocity_mode = false;

    rail_step_count = (int32_t)lroundf(((float)start->rail_pos / 100.0f) * STEPS_PER_MM);
    servo_sync_output(AXIS_PAN);
    servo_sync_output(AXIS_TILT);

    motion_move_to_position(end);
}

void motion_set_max_velocity(float velocity)
{
    if (velocity > 0.0f && velocity <= PAN_MAX_VEL_CENTI)
    {
        motion_profile.max_velocity = velocity;
    }
}

void motion_set_max_accel(float accel)
{
    if (accel > 0.0f && accel <= PAN_MAX_ACCEL_CENTI)
    {
        motion_profile.max_accel = accel;
    }
}

void motion_set_pid_p(uint8_t axis, float p)
{
    if (p < 0.0f) return;

    switch (axis)
    {
        case AXIS_PAN: pid_pan.kp = p; break;
        case AXIS_TILT: pid_tilt.kp = p; break;
        case AXIS_RAIL: pid_rail.kp = p; break;
        case AXIS_ALL:
            pid_pan.kp = p;
            pid_tilt.kp = p;
            pid_rail.kp = p;
            break;
        default:
            break;
    }
}

void motion_set_pid_i(uint8_t axis, float i)
{
    if (i < 0.0f) return;

    switch (axis)
    {
        case AXIS_PAN: pid_pan.ki = i; break;
        case AXIS_TILT: pid_tilt.ki = i; break;
        case AXIS_RAIL: pid_rail.ki = i; break;
        case AXIS_ALL:
            pid_pan.ki = i;
            pid_tilt.ki = i;
            pid_rail.ki = i;
            break;
        default:
            break;
    }
}

void motion_set_pid_d(uint8_t axis, float d)
{
    if (d < 0.0f) return;

    switch (axis)
    {
        case AXIS_PAN: pid_pan.kd = d; break;
        case AXIS_TILT: pid_tilt.kd = d; break;
        case AXIS_RAIL: pid_rail.kd = d; break;
        case AXIS_ALL:
            pid_pan.kd = d;
            pid_tilt.kd = d;
            pid_rail.kd = d;
            break;
        default:
            break;
    }
}

void motion_set_limit_min(uint8_t axis, int32_t value)
{
    switch (axis)
    {
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
        default:
            break;
    }
}

void motion_set_limit_max(uint8_t axis, int32_t value)
{
    switch (axis)
    {
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
        default:
            break;
    }
}

void motion_set_velocity(uint8_t axis, float velocity)
{
    switch (axis)
    {
        case AXIS_PAN:
            servo_pan.velocity_cmd_cdeg_s = clampf_value(
                servo_steps_to_centi_velocity(velocity),
                -get_axis_velocity_limit(AXIS_PAN),
                get_axis_velocity_limit(AXIS_PAN)
            );
            servo_pan.velocity_mode = fabsf(servo_pan.velocity_cmd_cdeg_s) >= 0.5f;
            if (!servo_pan.velocity_mode)
            {
                servo_pan.target_cdeg = servo_pan.current_cdeg;
            }
            break;

        case AXIS_TILT:
            servo_tilt.velocity_cmd_cdeg_s = clampf_value(
                servo_steps_to_centi_velocity(velocity),
                -get_axis_velocity_limit(AXIS_TILT),
                get_axis_velocity_limit(AXIS_TILT)
            );
            servo_tilt.velocity_mode = fabsf(servo_tilt.velocity_cmd_cdeg_s) >= 0.5f;
            if (!servo_tilt.velocity_mode)
            {
                servo_tilt.target_cdeg = servo_tilt.current_cdeg;
            }
            break;

        case AXIS_RAIL:
            velocity = clampf_value(velocity, -(float)RAIL_MAX_SPEED_STEPS, (float)RAIL_MAX_SPEED_STEPS);
            scurve_rail.target_velocity = velocity;
            break;

        case AXIS_ALL:
            motion_set_velocity(AXIS_PAN, velocity);
            motion_set_velocity(AXIS_TILT, velocity);
            motion_set_velocity(AXIS_RAIL, velocity);
            return;

        default:
            return;
    }

    is_moving = true;
    stable_counter = 0U;
}

void motion_stop_all(void)
{
    is_moving = false;
    stable_counter = 0U;

    stop_axis_state(AXIS_PAN);
    stop_axis_state(AXIS_TILT);
    stop_axis_state(AXIS_RAIL);
}
