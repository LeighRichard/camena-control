/**
 * @file uart_comm.h
 * @brief UART 通信模块头文件
 */

#ifndef __UART_COMM_H
#define __UART_COMM_H

#ifdef __cplusplus
extern "C" {
#endif

#include "main.h"
#include "protocol.h"

/* 缓冲区大小 */
#define UART_RX_BUFFER_SIZE     256
#define UART_TX_BUFFER_SIZE     256

/* 回调函数类型 */
typedef void (*CommandCallback)(const Command* cmd);

/**
 * @brief 初始化 UART 模块
 */
void uart_comm_init(void);

/**
 * @brief 处理接收到的数据
 * @param callback 指令处理回调函数
 */
void uart_comm_process(CommandCallback callback);

/**
 * @brief 发送响应
 * @param rsp 响应结构指针
 */
void uart_comm_send_response(const Response* rsp);

#ifdef __cplusplus
}
#endif

#endif /* __UART_COMM_H */
