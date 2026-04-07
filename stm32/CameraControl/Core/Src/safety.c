/**
 * @file safety.c
 * @brief Safety monitoring module implementation
 */

#include "safety.h"
#include "main.h"
#include "motion.h"
#include "adc.h"
#include <math.h>
#include <string.h>

#ifdef HAL_ADC_MODULE_ENABLED
extern ADC_HandleTypeDef hadc1;
extern ADC_HandleTypeDef hadc2;
static ADC_HandleTypeDef* adc1_ptr = &hadc1;
static ADC_HandleTypeDef* adc2_ptr = &hadc2;
#else
static void* adc1_ptr = NULL;
static void* adc2_ptr = NULL;
#endif

#define CURRENT_THRESHOLD_MA        2000.0f
#define TEMPERATURE_THRESHOLD_C     70.0f

#define ADC_REFERENCE_VOLTAGE       3.3f
#define ADC_RESOLUTION              4096.0f

#define CURRENT_SENSOR_SENSITIVITY  0.185f
#define CURRENT_SENSOR_OFFSET       2.5f

#define TEMP_SENSOR_BETA            3950.0f
#define TEMP_SENSOR_R25             10000.0f
#define TEMP_SENSOR_R_DIVIDER       10000.0f

static SafetyStatus current_status = SAFETY_OK;
static bool estop_active = false;
static LimitSwitchState limit_state = {0};

static uint32_t watchdog_timeout_ms = 1000;
static uint32_t last_comm_time = 0;
static bool watchdog_enabled = true;

static float motor_current_ma = 0.0f;
static float motor_temperature_c = 25.0f;

static void read_limit_switches(void);
static bool check_overcurrent(void);
static bool check_overheat(void);

void safety_init(void)
{
    current_status = SAFETY_OK;
    estop_active = false;
    memset(&limit_state, 0, sizeof(LimitSwitchState));

    last_comm_time = HAL_GetTick();
    watchdog_enabled = true;
}

SafetyStatus safety_check(void)
{
    if (estop_active)
    {
        return SAFETY_ESTOP;
    }

    if (SAFETY_ENABLE_ESTOP_INPUT && safety_is_estop_pressed())
    {
        current_status = SAFETY_ESTOP;
        estop_active = true;
        return current_status;
    }

    if (SAFETY_ENABLE_LIMIT_SWITCH_INPUTS)
    {
        read_limit_switches();

        if (limit_state.pan_pos || limit_state.pan_neg ||
            limit_state.tilt_pos || limit_state.tilt_neg ||
            limit_state.rail_pos || limit_state.rail_neg)
        {
            current_status = SAFETY_LIMIT_HIT;
            return current_status;
        }
    }

    if (check_overcurrent())
    {
        current_status = SAFETY_OVERCURRENT;
        return current_status;
    }

    if (check_overheat())
    {
        current_status = SAFETY_OVERHEAT;
        return current_status;
    }

    current_status = SAFETY_OK;
    return current_status;
}

void safety_emergency_stop(void)
{
    estop_active = true;
    current_status = SAFETY_ESTOP;

    motion_stop();

    /* Pan/tilt are PWM servos now and hold their last commanded position.
     * Only the rail stepper driver is actively disabled here.
     */
    HAL_GPIO_WritePin(RAIL_EN_GPIO_Port, RAIL_EN_Pin, GPIO_PIN_SET);
}

void safety_reset(void)
{
    if (!SAFETY_ENABLE_ESTOP_INPUT || !safety_is_estop_pressed())
    {
        estop_active = false;
        current_status = SAFETY_OK;

        HAL_GPIO_WritePin(RAIL_EN_GPIO_Port, RAIL_EN_Pin, GPIO_PIN_RESET);
    }
}

LimitSwitchState safety_get_limit_state(void)
{
    read_limit_switches();
    return limit_state;
}

bool safety_is_estop_pressed(void)
{
#if SAFETY_ENABLE_ESTOP_INPUT
    /* NC estop loop: open circuit reads high and means triggered. */
    return HAL_GPIO_ReadPin(ESTOP_GPIO_Port, ESTOP_Pin) == GPIO_PIN_SET;
#else
    return false;
#endif
}

void safety_watchdog_feed(void)
{
    last_comm_time = HAL_GetTick();
}

void safety_watchdog_check(void)
{
    uint32_t current_time;
    uint32_t elapsed;

    if (!watchdog_enabled)
    {
        return;
    }

    current_time = HAL_GetTick();

    if (current_time >= last_comm_time)
    {
        elapsed = current_time - last_comm_time;
    }
    else
    {
        elapsed = (0xFFFFFFFFu - last_comm_time) + current_time + 1u;
    }

    if (elapsed > watchdog_timeout_ms)
    {
        current_status = SAFETY_COMM_LOST;
        motion_stop();
    }
}

void safety_set_watchdog_timeout(uint32_t timeout_ms)
{
    watchdog_timeout_ms = timeout_ms;
}

void safety_watchdog_enable(bool enable)
{
    watchdog_enabled = enable;
    if (enable)
    {
        last_comm_time = HAL_GetTick();
    }
}

bool safety_is_comm_timeout(void)
{
    uint32_t current_time;
    uint32_t elapsed;

    if (!watchdog_enabled)
    {
        return false;
    }

    current_time = HAL_GetTick();

    if (current_time >= last_comm_time)
    {
        elapsed = current_time - last_comm_time;
    }
    else
    {
        elapsed = (0xFFFFFFFFu - last_comm_time) + current_time + 1u;
    }

    return elapsed > watchdog_timeout_ms;
}

static void read_limit_switches(void)
{
#if SAFETY_ENABLE_LIMIT_SWITCH_INPUTS
    /* NO limit switches: triggered state is pulled low. */
    limit_state.pan_pos = HAL_GPIO_ReadPin(PAN_LIMIT_POS_GPIO_Port, PAN_LIMIT_POS_Pin) == GPIO_PIN_RESET;
    limit_state.pan_neg = HAL_GPIO_ReadPin(PAN_LIMIT_NEG_GPIO_Port, PAN_LIMIT_NEG_Pin) == GPIO_PIN_RESET;
    limit_state.tilt_pos = HAL_GPIO_ReadPin(TILT_LIMIT_POS_GPIO_Port, TILT_LIMIT_POS_Pin) == GPIO_PIN_RESET;
    limit_state.tilt_neg = HAL_GPIO_ReadPin(TILT_LIMIT_NEG_GPIO_Port, TILT_LIMIT_NEG_Pin) == GPIO_PIN_RESET;
    limit_state.rail_pos = HAL_GPIO_ReadPin(RAIL_LIMIT_POS_GPIO_Port, RAIL_LIMIT_POS_Pin) == GPIO_PIN_RESET;
    limit_state.rail_neg = HAL_GPIO_ReadPin(RAIL_LIMIT_NEG_GPIO_Port, RAIL_LIMIT_NEG_Pin) == GPIO_PIN_RESET;
#else
    memset(&limit_state, 0, sizeof(limit_state));
#endif
}

static bool check_overcurrent(void)
{
    if (adc1_ptr == NULL)
    {
        return false;
    }

#ifdef HAL_ADC_MODULE_ENABLED
    ADC_ChannelConfTypeDef sConfig = {0};
    uint32_t adc_value;
    float voltage;

    /* Current sensor uses ADC1 channel 2 on PA2. */
    sConfig.Channel = ADC_CHANNEL_2;
    sConfig.Rank = 1;
    sConfig.SamplingTime = ADC_SAMPLETIME_3CYCLES;

    if (HAL_ADC_ConfigChannel(adc1_ptr, &sConfig) != HAL_OK)
    {
        return false;
    }

    HAL_ADC_Start(adc1_ptr);
    HAL_ADC_PollForConversion(adc1_ptr, 10);

    adc_value = HAL_ADC_GetValue(adc1_ptr);
    HAL_ADC_Stop(adc1_ptr);

    voltage = (adc_value / ADC_RESOLUTION) * ADC_REFERENCE_VOLTAGE;
    motor_current_ma = ((voltage - CURRENT_SENSOR_OFFSET) / CURRENT_SENSOR_SENSITIVITY) * 1000.0f;

    if (motor_current_ma > CURRENT_THRESHOLD_MA)
    {
        return true;
    }
#endif

    return false;
}

static bool check_overheat(void)
{
    if (adc2_ptr == NULL)
    {
        return false;
    }

#ifdef HAL_ADC_MODULE_ENABLED
    ADC_ChannelConfTypeDef sConfig = {0};
    uint32_t adc_value;
    float voltage;
    float r_ntc;
    float t_kelvin;

    /* Temperature sensor uses ADC2 channel 1 on PA1. */
    sConfig.Channel = ADC_CHANNEL_1;
    sConfig.Rank = 1;
    sConfig.SamplingTime = ADC_SAMPLETIME_3CYCLES;

    if (HAL_ADC_ConfigChannel(adc2_ptr, &sConfig) != HAL_OK)
    {
        return false;
    }

    HAL_ADC_Start(adc2_ptr);
    HAL_ADC_PollForConversion(adc2_ptr, 10);

    adc_value = HAL_ADC_GetValue(adc2_ptr);
    HAL_ADC_Stop(adc2_ptr);

    voltage = (adc_value / ADC_RESOLUTION) * ADC_REFERENCE_VOLTAGE;
    r_ntc = TEMP_SENSOR_R_DIVIDER * voltage / (ADC_REFERENCE_VOLTAGE - voltage);
    t_kelvin = 1.0f / (1.0f / 298.15f + (1.0f / TEMP_SENSOR_BETA) * logf(r_ntc / TEMP_SENSOR_R25));
    motor_temperature_c = t_kelvin - 273.15f;

    if (motor_temperature_c > TEMPERATURE_THRESHOLD_C)
    {
        return true;
    }
#endif

    return false;
}
