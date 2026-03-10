/**
 * @file safety.h
 * @brief 安全监控模块
 */

#ifndef __SAFETY_H
#define __SAFETY_H

#include <stdint.h>
#include <stdbool.h>

/* 安全状态 */
typedef enum {
    SAFETY_OK,
    SAFETY_LIMIT_HIT,
    SAFETY_OVERCURRENT,
    SAFETY_OVERHEAT,
    SAFETY_COMM_LOST,
    SAFETY_ESTOP,
} SafetyStatus;

/* 限位开关状态 */
typedef struct {
    bool pan_pos;
    bool pan_neg;
    bool tilt_pos;
    bool tilt_neg;
    bool rail_pos;
    bool rail_neg;
} LimitSwitchState;

/* 函数声明 */
void safety_init(void);
SafetyStatus safety_check(void);
void safety_emergency_stop(void);
void safety_reset(void);
LimitSwitchState safety_get_limit_state(void);
bool safety_is_estop_pressed(void);

/* 通信看门狗 */
void safety_watchdog_feed(void);
void safety_watchdog_check(void);
void safety_set_watchdog_timeout(uint32_t timeout_ms);
void safety_watchdog_enable(bool enable);
bool safety_is_comm_timeout(void);

#endif /* __SAFETY_H */
