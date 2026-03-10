/**
 * @file safety.c
 * @brief 安全监控模块实现
 */

#include "safety.h"
#include "main.h"
#include "motion.h"
#include <string.h>

/* ADC 句柄（需要在 main.c 中定义并导出） */
extern ADC_HandleTypeDef hadc1;
extern ADC_HandleTypeDef hadc2;

/* 电流和温度阈值 */
#define CURRENT_THRESHOLD_MA     2000.0f   /* 过流阈值 2A */
#define TEMPERATURE_THRESHOLD_C  70.0f     /* 过温阈值 70°C */

/* ADC 转换参数 */
#define ADC_REFERENCE_VOLTAGE    3.3f      /* ADC 参考电压 */
#define ADC_RESOLUTION           4096.0f   /* 12位 ADC */

/* 电流传感器参数（假设使用 ACS712-5A） */
#define CURRENT_SENSOR_SENSITIVITY  0.185f /* 185mV/A */
#define CURRENT_SENSOR_OFFSET       2.5f   /* 零电流输出电压 */

/* 温度传感器参数（假设使用 NTC 热敏电阻） */
#define TEMP_SENSOR_BETA        3950.0f     /* B值 */
#define TEMP_SENSOR_R25         10000.0f    /* 25°C时的电阻 10kΩ */
#define TEMP_SENSOR_R_DIVIDER   10000.0f    /* 分压电阻 10kΩ */

/* ==================== 私有变量 ==================== */

static SafetyStatus current_status = SAFETY_OK;
static bool estop_active = false;
static LimitSwitchState limit_state = {0};

/* 通信看门狗 */
static uint32_t watchdog_timeout_ms = 1000;
static uint32_t last_comm_time = 0;
static bool watchdog_enabled = true;

/* ADC 读取值缓存 */
static float motor_current_ma = 0.0f;
static float motor_temperature_c = 25.0f;

/* ==================== 私有函数声明 ==================== */

static void read_limit_switches(void);
static bool check_overcurrent(void);
static bool check_overheat(void);

/* ==================== 公共函数实现 ==================== */

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
    if (estop_active) return SAFETY_ESTOP;
    
    if (safety_is_estop_pressed())
    {
        current_status = SAFETY_ESTOP;
        estop_active = true;
        return current_status;
    }
    
    read_limit_switches();
    
    if (limit_state.pan_pos || limit_state.pan_neg ||
        limit_state.tilt_pos || limit_state.tilt_neg ||
        limit_state.rail_pos || limit_state.rail_neg)
    {
        current_status = SAFETY_LIMIT_HIT;
        return current_status;
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
    /* 先设置状态标志 */
    estop_active = true;
    current_status = SAFETY_ESTOP;
    
    /* 停止运动 */
    motion_stop();
    
    /* 禁用电机驱动器 (高电平禁用 TMC2209) */
    /* 使用直接寄存器操作确保原子性 */
    GPIOB->BSRR = PAN_EN_Pin | TILT_EN_Pin | RAIL_EN_Pin;
}

void safety_reset(void)
{
    if (!safety_is_estop_pressed())
    {
        estop_active = false;
        current_status = SAFETY_OK;
        
        /* 重新使能电机驱动器 (低电平使能 TMC2209) */
        HAL_GPIO_WritePin(PAN_EN_GPIO_Port, PAN_EN_Pin, GPIO_PIN_RESET);
        HAL_GPIO_WritePin(TILT_EN_GPIO_Port, TILT_EN_Pin, GPIO_PIN_RESET);
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
    /* 急停按钮常闭，断开时为高电平，表示急停触发 */
    return HAL_GPIO_ReadPin(ESTOP_GPIO_Port, ESTOP_Pin) == GPIO_PIN_SET;
}

/* ==================== 通信看门狗 ==================== */

void safety_watchdog_feed(void)
{
    last_comm_time = HAL_GetTick();
}

void safety_watchdog_check(void)
{
    if (!watchdog_enabled) return;
    
    uint32_t current_time = HAL_GetTick();
    
    /* 处理 HAL_GetTick() 溢出 (约 49.7 天后) */
    uint32_t elapsed;
    if (current_time >= last_comm_time)
    {
        elapsed = current_time - last_comm_time;
    }
    else
    {
        /* 溢出情况 */
        elapsed = (0xFFFFFFFF - last_comm_time) + current_time + 1;
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
    if (enable) last_comm_time = HAL_GetTick();
}

bool safety_is_comm_timeout(void)
{
    if (!watchdog_enabled) return false;
    
    uint32_t current_time = HAL_GetTick();
    uint32_t elapsed;
    
    /* 处理溢出 */
    if (current_time >= last_comm_time)
    {
        elapsed = current_time - last_comm_time;
    }
    else
    {
        elapsed = (0xFFFFFFFF - last_comm_time) + current_time + 1;
    }
    
    return elapsed > watchdog_timeout_ms;
}

/* ==================== 私有函数实现 ==================== */

static void read_limit_switches(void)
{
    /* 限位开关为常开触点，触发时为低电平 */
    limit_state.pan_pos = HAL_GPIO_ReadPin(PAN_LIMIT_POS_GPIO_Port, PAN_LIMIT_POS_Pin) == GPIO_PIN_RESET;
    limit_state.pan_neg = HAL_GPIO_ReadPin(PAN_LIMIT_NEG_GPIO_Port, PAN_LIMIT_NEG_Pin) == GPIO_PIN_RESET;
    limit_state.tilt_pos = HAL_GPIO_ReadPin(TILT_LIMIT_POS_GPIO_Port, TILT_LIMIT_POS_Pin) == GPIO_PIN_RESET;
    limit_state.tilt_neg = HAL_GPIO_ReadPin(TILT_LIMIT_NEG_GPIO_Port, TILT_LIMIT_NEG_Pin) == GPIO_PIN_RESET;
    limit_state.rail_pos = HAL_GPIO_ReadPin(RAIL_LIMIT_POS_GPIO_Port, RAIL_LIMIT_POS_Pin) == GPIO_PIN_RESET;
    limit_state.rail_neg = HAL_GPIO_ReadPin(RAIL_LIMIT_NEG_GPIO_Port, RAIL_LIMIT_NEG_Pin) == GPIO_PIN_RESET;
}

static bool check_overcurrent(void)
{
    /* 读取电流传感器 ADC (使用 ADC1 通道 0) */
    ADC_ChannelConfTypeDef sConfig = {0};
    sConfig.Channel = ADC_CHANNEL_0;
    sConfig.Rank = 1;
    sConfig.SamplingTime = ADC_SAMPLETIME_3CYCLES;
    
    if (HAL_ADC_ConfigChannel(&hadc1, &sConfig) != HAL_OK) {
        return false;
    }
    
    /* 启动 ADC 转换 */
    HAL_ADC_Start(&hadc1);
    HAL_ADC_PollForConversion(&hadc1, 10);
    
    /* 读取 ADC 值 */
    uint32_t adc_value = HAL_ADC_GetValue(&hadc1);
    HAL_ADC_Stop(&hadc1);
    
    /* 转换为电压 */
    float voltage = (adc_value / ADC_RESOLUTION) * ADC_REFERENCE_VOLTAGE;
    
    /* 转换为电流 (ACS712 传感器) */
    motor_current_ma = ((voltage - CURRENT_SENSOR_OFFSET) / CURRENT_SENSOR_SENSITIVITY) * 1000.0f;
    
    /* 检查是否过流 */
    if (motor_current_ma > CURRENT_THRESHOLD_MA) {
        return true;
    }
    
    return false;
}

static bool check_overheat(void)
{
    /* 读取温度传感器 ADC (使用 ADC2 通道 1) */
    ADC_ChannelConfTypeDef sConfig = {0};
    sConfig.Channel = ADC_CHANNEL_1;
    sConfig.Rank = 1;
    sConfig.SamplingTime = ADC_SAMPLETIME_3CYCLES;
    
    if (HAL_ADC_ConfigChannel(&hadc2, &sConfig) != HAL_OK) {
        return false;
    }
    
    /* 启动 ADC 转换 */
    HAL_ADC_Start(&hadc2);
    HAL_ADC_PollForConversion(&hadc2, 10);
    
    /* 读取 ADC 值 */
    uint32_t adc_value = HAL_ADC_GetValue(&hadc2);
    HAL_ADC_Stop(&hadc2);
    
    /* 转换为电压 */
    float voltage = (adc_value / ADC_RESOLUTION) * ADC_REFERENCE_VOLTAGE;
    
    /* 计算 NTC 热敏电阻阻值 */
    float r_ntc = TEMP_SENSOR_R_DIVIDER * voltage / (ADC_REFERENCE_VOLTAGE - voltage);
    
    /* 使用 B参数方程计算温度 */
    float t_kelvin = 1.0f / (1.0f / 298.15f + (1.0f / TEMP_SENSOR_BETA) * logf(r_ntc / TEMP_SENSOR_R25));
    motor_temperature_c = t_kelvin - 273.15f;
    
    /* 检查是否过温 */
    if (motor_temperature_c > TEMPERATURE_THRESHOLD_C) {
        return true;
    }
    
    return false;
}
