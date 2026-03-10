/**
 * @file protocol.h
 * @brief 通信协议定义 v2.0（带序列号）
 * 
 * 帧格式 v2.0:
 *   [HEAD][SEQ][LEN][CMD][DATA][CRC16][TAIL]
 *   - HEAD: 帧头 (0xAA)
 *   - SEQ: 序列号 (1字节, 0-255 循环)
 *   - LEN: 数据长度 (CMD + DATA)
 *   - CMD: 指令类型
 *   - DATA: 数据内容
 *   - CRC16: 校验和 (SEQ + LEN + CMD + DATA)
 *   - TAIL: 帧尾 (0x55)
 */

#ifndef __PROTOCOL_H
#define __PROTOCOL_H

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

/* 协议版本 */
#define PROTOCOL_VERSION    2

/* 帧格式常量 */
#define FRAME_HEAD          0xAA
#define FRAME_TAIL          0x55
#define FRAME_MAX_DATA_LEN  32
#define FRAME_MIN_LEN       7   /* HEAD + SEQ + LEN + CMD + CHECKSUM(2) + TAIL */

/* 指令类型 */
typedef enum {
    CMD_POSITION    = 0x01,     /* 位置控制 */
    CMD_STATUS      = 0x02,     /* 状态查询 */
    CMD_CONFIG      = 0x03,     /* 参数配置 */
    CMD_ESTOP       = 0x04,     /* 急停 */
    CMD_HOME        = 0x05,     /* 归零 */
} CommandType;

/* 响应类型 */
typedef enum {
    RSP_POSITION    = 0x81,
    RSP_STATUS      = 0x82,
    RSP_CONFIG      = 0x83,
    RSP_ESTOP       = 0x84,
    RSP_HOME        = 0x85,
} ResponseType;

/* 轴定义 */
typedef enum {
    AXIS_PAN        = 0x00,
    AXIS_TILT       = 0x01,
    AXIS_RAIL       = 0x02,
    AXIS_ALL        = 0xFF,
} AxisType;

/* 状态码 */
typedef enum {
    STATUS_OK           = 0x00,
    STATUS_ERROR        = 0x01,
    STATUS_BUSY         = 0x02,
    STATUS_LIMIT_HIT    = 0x03,
    STATUS_ESTOP        = 0x04,
} StatusCode;

/* 指令结构 */
typedef struct {
    CommandType type;
    uint8_t axis;
    int32_t value;
    uint8_t seq;        /* 序列号 */
    uint16_t checksum;
} Command;

/* 响应结构 */
typedef struct {
    ResponseType type;
    StatusCode status;
    int32_t pan_pos;
    int32_t tilt_pos;
    int32_t rail_pos;
    uint8_t seq;        /* 序列号（回显请求的序列号）*/
    uint16_t checksum;
} Response;

/* 解析结果 */
typedef enum {
    PARSE_OK,
    PARSE_INCOMPLETE,
    PARSE_ERROR_HEAD,
    PARSE_ERROR_TAIL,
    PARSE_ERROR_CHECKSUM,
    PARSE_ERROR_LENGTH,
} ParseResult;

/* 函数声明 */
ParseResult cmd_parse(const uint8_t* buffer, size_t len, Command* out);
size_t cmd_encode(const Response* rsp, uint8_t* buffer);
uint16_t crc16_calculate(const uint8_t* data, size_t len);
bool crc16_verify(const uint8_t* data, size_t len, uint16_t expected);

#endif /* __PROTOCOL_H */
