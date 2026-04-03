/**
 * @file uart_comm.h
 * @brief UART communication helpers for the Jetson <-> STM32 link
 */

#ifndef __UART_COMM_H
#define __UART_COMM_H

#ifdef __cplusplus
extern "C" {
#endif

#include "main.h"
#include "protocol.h"

/* Ring-buffer sizes for the serial RX/TX path. */
#define UART_RX_BUFFER_SIZE     256
#define UART_TX_BUFFER_SIZE     256

typedef void (*CommandCallback)(const Command* cmd);

/* Start interrupt-driven reception and reset parser state. */
void uart_comm_init(void);

/* Drain the RX ring buffer, parse complete frames, and invoke callback. */
void uart_comm_process(CommandCallback callback);

/* Encode a response frame and send it by DMA, queueing when TX is busy. */
void uart_comm_send_response(const Response* rsp);

#ifdef __cplusplus
}
#endif

#endif /* __UART_COMM_H */
