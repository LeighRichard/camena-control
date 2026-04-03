/**
 * @file protocol.h
 * @brief STM32 <-> Jetson serial protocol definitions (v2.0)
 *
 * Frame format:
 *   [HEAD][SEQ][LEN][CMD][DATA][CRC16][TAIL]
 */

#ifndef __PROTOCOL_H
#define __PROTOCOL_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define PROTOCOL_VERSION    2

#define FRAME_HEAD          0xAA
#define FRAME_TAIL          0x55
#define FRAME_MAX_DATA_LEN  32
#define FRAME_MIN_LEN       7   /* HEAD + SEQ + LEN + CMD + CRC16 + TAIL */

typedef enum {
    CMD_POSITION       = 0x01,
    CMD_STATUS         = 0x02,
    CMD_CONFIG         = 0x03,
    CMD_ESTOP          = 0x04,
    CMD_HOME           = 0x05,
    CMD_SET_VELOCITY   = 0x06,
    CMD_STOP           = 0x07,
    CMD_MOVE_ABSOLUTE  = 0x08,
} CommandType;

typedef enum {
    RSP_POSITION       = 0x81,
    RSP_STATUS         = 0x82,
    RSP_CONFIG         = 0x83,
    RSP_ESTOP          = 0x84,
    RSP_HOME           = 0x85,
    RSP_SET_VELOCITY   = 0x86,
    RSP_STOP           = 0x87,
    RSP_MOVE_ABSOLUTE  = 0x88,
} ResponseType;

#undef AXIS_PAN
#undef AXIS_TILT
#undef AXIS_RAIL
#undef AXIS_ALL

typedef enum {
    AXIS_PAN   = 0x00,
    AXIS_TILT  = 0x01,
    AXIS_RAIL  = 0x02,
    AXIS_ALL   = 0xFF,
} AxisType;

typedef enum {
    STATUS_OK        = 0x00,
    STATUS_ERROR     = 0x01,
    STATUS_BUSY      = 0x02,
    STATUS_LIMIT_HIT = 0x03,
    STATUS_ESTOP     = 0x04,
} StatusCode;

/* CONFIG commands encode parameter id in the upper 16 bits and value in the lower 16 bits. */
typedef enum {
    CONFIG_MAX_VELOCITY        = 0x0001,
    CONFIG_MAX_ACCEL           = 0x0002,
    CONFIG_PID_P               = 0x0003,
    CONFIG_PID_I               = 0x0004,
    CONFIG_PID_D               = 0x0005,
    CONFIG_WATCHDOG_TIMEOUT_MS = 0x0010,
    CONFIG_WATCHDOG_ENABLE     = 0x0011,
    CONFIG_PAN_MIN_LIMIT       = 0x0020,
    CONFIG_PAN_MAX_LIMIT       = 0x0021,
    CONFIG_TILT_MIN_LIMIT      = 0x0022,
    CONFIG_TILT_MAX_LIMIT      = 0x0023,
    CONFIG_RAIL_MIN_LIMIT      = 0x0024,
    CONFIG_RAIL_MAX_LIMIT      = 0x0025,
} ConfigParamId;

typedef struct {
    CommandType type;
    uint8_t axis;
    int32_t value;
    uint8_t seq;
    uint16_t checksum;
} Command;

typedef struct {
    ResponseType type;
    StatusCode status;
    int32_t pan_pos;
    int32_t tilt_pos;
    int32_t rail_pos;
    uint8_t seq;
    uint16_t checksum;
} Response;

typedef enum {
    PARSE_OK,
    PARSE_INCOMPLETE,
    PARSE_ERROR_HEAD,
    PARSE_ERROR_TAIL,
    PARSE_ERROR_CHECKSUM,
    PARSE_ERROR_LENGTH,
} ParseResult;

ParseResult cmd_parse(const uint8_t* buffer, size_t len, Command* out);
size_t cmd_encode(const Response* rsp, uint8_t* buffer);
uint16_t crc16_calculate(const uint8_t* data, size_t len);
bool crc16_verify(const uint8_t* data, size_t len, uint16_t expected);

/* Helpers for unpacking CONFIG command payloads without repeating bit twiddling. */
static inline ConfigParamId config_param_from_value(int32_t packed_value)
{
    return (ConfigParamId)(((uint32_t)packed_value >> 16) & 0xFFFFu);
}

static inline uint16_t config_raw_value(int32_t packed_value)
{
    return (uint16_t)((uint32_t)packed_value & 0xFFFFu);
}

static inline int16_t config_signed_value(int32_t packed_value)
{
    return (int16_t)config_raw_value(packed_value);
}

static inline int32_t config_pack_value(ConfigParamId id, uint16_t value)
{
    return (int32_t)((((uint32_t)id) << 16) | value);
}

#endif /* __PROTOCOL_H */
