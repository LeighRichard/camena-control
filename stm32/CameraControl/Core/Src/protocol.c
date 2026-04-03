/**
 * @file protocol.c
 * @brief STM32 <-> Jetson frame encoding and decoding (v2.0)
 */

#include "protocol.h"
#include <string.h>

static int32_t read_int32_le(const uint8_t* data);
static void write_int32_le(uint8_t* data, int32_t value);

uint16_t crc16_calculate(const uint8_t* data, size_t len)
{
    uint16_t crc = 0xFFFF;

    for (size_t i = 0; i < len; i++)
    {
        crc ^= (uint16_t)data[i] << 8;
        for (int bit = 0; bit < 8; bit++)
        {
            if ((crc & 0x8000u) != 0u)
            {
                crc = (uint16_t)((crc << 1) ^ 0x1021u);
            }
            else
            {
                crc <<= 1;
            }
        }
    }

    return crc;
}

bool crc16_verify(const uint8_t* data, size_t len, uint16_t expected)
{
    return crc16_calculate(data, len) == expected;
}

ParseResult cmd_parse(const uint8_t* buffer, size_t len, Command* out)
{
    uint8_t data_len;
    uint8_t payload_len;
    uint16_t crc_received;
    size_t expected_len;
    const uint8_t* cmd_data;

    if (len < FRAME_MIN_LEN)
    {
        return PARSE_INCOMPLETE;
    }

    if (buffer[0] != FRAME_HEAD)
    {
        return PARSE_ERROR_HEAD;
    }

    data_len = buffer[2];
    if (data_len < 1u || data_len > (FRAME_MAX_DATA_LEN + 1u))
    {
        return PARSE_ERROR_LENGTH;
    }

    expected_len = 1u + 1u + 1u + data_len + 2u + 1u;
    if (len < expected_len)
    {
        return PARSE_INCOMPLETE;
    }

    if (buffer[expected_len - 1u] != FRAME_TAIL)
    {
        return PARSE_ERROR_TAIL;
    }

    /* CRC covers SEQ + LEN + CMD + DATA. */
    crc_received = (uint16_t)(buffer[expected_len - 3u] |
                              ((uint16_t)buffer[expected_len - 2u] << 8));
    if (!crc16_verify(&buffer[1], 2u + data_len, crc_received))
    {
        return PARSE_ERROR_CHECKSUM;
    }

    out->seq = buffer[1];
    out->type = (CommandType)buffer[3];
    payload_len = (uint8_t)(data_len - 1u);
    cmd_data = &buffer[4];

    switch (out->type)
    {
        case CMD_POSITION:
        case CMD_MOVE_ABSOLUTE:
        case CMD_SET_VELOCITY:
        case CMD_CONFIG:
            if (payload_len != 5u)
            {
                return PARSE_ERROR_LENGTH;
            }
            out->axis = cmd_data[0];
            out->value = read_int32_le(&cmd_data[1]);
            break;

        case CMD_HOME:
            if (payload_len != 1u)
            {
                return PARSE_ERROR_LENGTH;
            }
            out->axis = cmd_data[0];
            out->value = 0;
            break;

        case CMD_STATUS:
        case CMD_ESTOP:
            if (payload_len != 0u)
            {
                return PARSE_ERROR_LENGTH;
            }
            out->axis = AXIS_ALL;
            out->value = 0;
            break;

        case CMD_STOP:
            if (payload_len > 1u)
            {
                return PARSE_ERROR_LENGTH;
            }
            out->axis = (payload_len == 1u) ? cmd_data[0] : AXIS_ALL;
            out->value = 0;
            break;

        default:
            return PARSE_ERROR_LENGTH;
    }

    return PARSE_OK;
}

size_t cmd_encode(const Response* rsp, uint8_t* buffer)
{
    size_t data_len;
    size_t crc_pos;
    uint16_t crc;
    uint8_t* data_ptr = &buffer[4];

    switch (rsp->type)
    {
        case RSP_STATUS:
            /*
             * STATUS payload:
             *   status(1) + pan_pos(4) + tilt_pos(4) + rail_pos(4)
             */
            data_ptr[0] = (uint8_t)rsp->status;
            write_int32_le(&data_ptr[1], rsp->pan_pos);
            write_int32_le(&data_ptr[5], rsp->tilt_pos);
            write_int32_le(&data_ptr[9], rsp->rail_pos);
            data_len = 14u;
            break;

        default:
            data_ptr[0] = (uint8_t)rsp->status;
            data_len = 2u;
            break;
    }

    buffer[0] = FRAME_HEAD;
    buffer[1] = rsp->seq;
    buffer[2] = (uint8_t)data_len;
    buffer[3] = (uint8_t)rsp->type;

    crc = crc16_calculate(&buffer[1], 2u + data_len);
    crc_pos = 3u + data_len;

    buffer[crc_pos] = (uint8_t)(crc & 0xFFu);
    buffer[crc_pos + 1u] = (uint8_t)((crc >> 8) & 0xFFu);
    buffer[crc_pos + 2u] = FRAME_TAIL;

    return crc_pos + 3u;
}

static int32_t read_int32_le(const uint8_t* data)
{
    return (int32_t)((uint32_t)data[0] |
                     ((uint32_t)data[1] << 8) |
                     ((uint32_t)data[2] << 16) |
                     ((uint32_t)data[3] << 24));
}

static void write_int32_le(uint8_t* data, int32_t value)
{
    data[0] = (uint8_t)(value & 0xFF);
    data[1] = (uint8_t)((value >> 8) & 0xFF);
    data[2] = (uint8_t)((value >> 16) & 0xFF);
    data[3] = (uint8_t)((value >> 24) & 0xFF);
}
