/**
 * @file protocol.c
 * @brief 通信协议实现 v2.0（带序列号）
 */

#include "protocol.h"
#include <string.h>

/**
 * @brief 计算 CRC16-CCITT 校验和
 * @param data 数据指针
 * @param len 数据长度
 * @return CRC16 校验和
 */
uint16_t crc16_calculate(const uint8_t* data, size_t len)
{
    uint16_t crc = 0xFFFF;
    
    for (size_t i = 0; i < len; i++)
    {
        crc ^= (uint16_t)data[i] << 8;
        for (int j = 0; j < 8; j++)
        {
            if (crc & 0x8000)
            {
                crc = (crc << 1) ^ 0x1021;
            }
            else
            {
                crc <<= 1;
            }
        }
    }
    
    return crc;
}

/**
 * @brief 验证 CRC16 校验和
 * @param data 数据指针
 * @param len 数据长度
 * @param expected 期望的校验和
 * @return 校验是否通过
 */
bool crc16_verify(const uint8_t* data, size_t len, uint16_t expected)
{
    return crc16_calculate(data, len) == expected;
}

/**
 * @brief 解析指令帧 v2.0（带序列号）
 * @param buffer 接收缓冲区
 * @param len 缓冲区长度
 * @param out 输出指令结构
 * @return 解析结果
 * 
 * 帧格式: [HEAD][SEQ][LEN][CMD][DATA][CRC16][TAIL]
 */
ParseResult cmd_parse(const uint8_t* buffer, size_t len, Command* out)
{
    /* 检查最小长度 */
    if (len < FRAME_MIN_LEN)
    {
        return PARSE_INCOMPLETE;
    }
    
    /* 检查帧头 */
    if (buffer[0] != FRAME_HEAD)
    {
        return PARSE_ERROR_HEAD;
    }
    
    /* 解析序列号和长度字段 */
    uint8_t seq = buffer[1];
    uint8_t data_len = buffer[2];
    size_t expected_len = 1 + 1 + 1 + data_len + 2 + 1;  /* HEAD + SEQ + LEN + DATA + CRC + TAIL */
    
    /* 检查是否收到完整帧 */
    if (len < expected_len)
    {
        return PARSE_INCOMPLETE;
    }
    
    /* 检查帧尾 */
    if (buffer[expected_len - 1] != FRAME_TAIL)
    {
        return PARSE_ERROR_TAIL;
    }
    
    /* 提取并验证校验和 (SEQ + LEN + CMD + DATA) */
    uint16_t crc_received = buffer[expected_len - 3] | (buffer[expected_len - 2] << 8);
    if (!crc16_verify(&buffer[1], 1 + data_len, crc_received))
    {
        return PARSE_ERROR_CHECKSUM;
    }
    
    /* 保存序列号 */
    out->seq = seq;
    
    /* 解析指令类型 */
    out->type = (CommandType)buffer[3];
    
    /* 根据指令类型解析数据 */
    const uint8_t* cmd_data = &buffer[4];
    
    switch (out->type)
    {
        case CMD_POSITION:
        case CMD_MOVE_ABSOLUTE:
            out->axis = cmd_data[0];
            out->value = (int32_t)(cmd_data[1] | (cmd_data[2] << 8) | 
                                   (cmd_data[3] << 16) | (cmd_data[4] << 24));
            break;
            
        case CMD_SET_VELOCITY:
            out->axis = cmd_data[0];
            out->value = (int32_t)(cmd_data[1] | (cmd_data[2] << 8) | 
                                   (cmd_data[3] << 16) | (cmd_data[4] << 24));
            break;
            
        case CMD_CONFIG:
            out->axis = cmd_data[0];
            out->value = (int32_t)(cmd_data[1] | (cmd_data[2] << 8) | 
                                   (cmd_data[3] << 16) | (cmd_data[4] << 24));
            break;
            
        case CMD_HOME:
            out->axis = cmd_data[0];
            out->value = 0;
            break;
            
        case CMD_STATUS:
        case CMD_ESTOP:
        case CMD_STOP:
            out->axis = AXIS_ALL;
            out->value = 0;
            break;
            
        default:
            return PARSE_ERROR_LENGTH;
    }
    
    return PARSE_OK;
}

/**
 * @brief 编码响应帧 v2.0（带序列号）
 * @param rsp 响应结构
 * @param buffer 输出缓冲区
 * @return 编码后的帧长度
 * 
 * 帧格式: [HEAD][SEQ][LEN][CMD][DATA][CRC16][TAIL]
 */
size_t cmd_encode(const Response* rsp, uint8_t* buffer)
{
    size_t data_len;
    uint8_t* data_ptr = &buffer[4];  /* 数据从第5字节开始 (HEAD + SEQ + LEN + CMD) */
    
    /* 根据响应类型构建数据 */
    switch (rsp->type)
    {
        case RSP_STATUS:
            /* STATUS 响应: status(1) + pan(4) + tilt(4) + rail(4) = 13 bytes */
            data_ptr[0] = rsp->status;
            data_ptr[1] = (rsp->pan_pos >> 0) & 0xFF;
            data_ptr[2] = (rsp->pan_pos >> 8) & 0xFF;
            data_ptr[3] = (rsp->pan_pos >> 16) & 0xFF;
            data_ptr[4] = (rsp->pan_pos >> 24) & 0xFF;
            data_ptr[5] = (rsp->tilt_pos >> 0) & 0xFF;
            data_ptr[6] = (rsp->tilt_pos >> 8) & 0xFF;
            data_ptr[7] = (rsp->tilt_pos >> 16) & 0xFF;
            data_ptr[8] = (rsp->tilt_pos >> 24) & 0xFF;
            data_ptr[9] = (rsp->rail_pos >> 0) & 0xFF;
            data_ptr[10] = (rsp->rail_pos >> 8) & 0xFF;
            data_ptr[11] = (rsp->rail_pos >> 16) & 0xFF;
            data_ptr[12] = (rsp->rail_pos >> 24) & 0xFF;
            data_len = 14;  /* type(1) + data(13) */
            break;
            
        default:
            /* 其他响应: 只有 status(1) */
            data_ptr[0] = rsp->status;
            data_len = 2;  /* type(1) + status(1) */
            break;
    }
    
    /* 构建帧头、序列号和长度 */
    buffer[0] = FRAME_HEAD;
    buffer[1] = rsp->seq;       /* 回显请求的序列号 */
    buffer[2] = data_len;
    buffer[3] = rsp->type;
    
    /* 计算校验和 (SEQ + LEN + TYPE + DATA) */
    uint16_t crc = crc16_calculate(&buffer[1], 1 + data_len);
    
    /* 添加校验和 (小端序) */
    size_t crc_pos = 2 + data_len;
    buffer[crc_pos] = crc & 0xFF;
    buffer[crc_pos + 1] = (crc >> 8) & 0xFF;
    
    /* 添加帧尾 */
    buffer[crc_pos + 2] = FRAME_TAIL;
    
    return crc_pos + 3;  /* 总长度 */
}
