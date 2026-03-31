/**
 * @file safety.h
 * @brief Safety monitoring module
 */

#ifndef __SAFETY_H
#define __SAFETY_H

#include <stdint.h>
#include <stdbool.h>

/*
 * Hardware safety input switches.
 * Set to 1 when the corresponding external wiring is installed.
 */
#ifndef SAFETY_ENABLE_ESTOP_INPUT
#define SAFETY_ENABLE_ESTOP_INPUT         0
#endif

#ifndef SAFETY_ENABLE_LIMIT_SWITCH_INPUTS
#define SAFETY_ENABLE_LIMIT_SWITCH_INPUTS 0
#endif

typedef enum {
    SAFETY_OK,
    SAFETY_LIMIT_HIT,
    SAFETY_OVERCURRENT,
    SAFETY_OVERHEAT,
    SAFETY_COMM_LOST,
    SAFETY_ESTOP,
} SafetyStatus;

typedef struct {
    bool pan_pos;
    bool pan_neg;
    bool tilt_pos;
    bool tilt_neg;
    bool rail_pos;
    bool rail_neg;
} LimitSwitchState;

void safety_init(void);
SafetyStatus safety_check(void);
void safety_emergency_stop(void);
void safety_reset(void);
LimitSwitchState safety_get_limit_state(void);
bool safety_is_estop_pressed(void);

void safety_watchdog_feed(void);
void safety_watchdog_check(void);
void safety_set_watchdog_timeout(uint32_t timeout_ms);
void safety_watchdog_enable(bool enable);
bool safety_is_comm_timeout(void);

#endif /* __SAFETY_H */
