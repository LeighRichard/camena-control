/**
 * @file uart_comm.c
 * @brief UART 通信模块实现
 */

#include "uart_comm.h"
#include "protocol.h"
#include "usart.h"
#include <string.h>

/* 外部 UART 句柄 */
extern UART_HandleTypeDef huart1;

/* 接收缓冲区 (环形) */
static uint8_t rx_buffer[UART_RX_BUFFER_SIZE];
static volatile uint16_t rx_head = 0;
static volatile uint16_t rx_tail = 0;

/* 发送缓冲区 */
static uint8_t tx_buffer[UART_TX_BUFFER_SIZE];
static volatile uint8_t tx_busy = 0;

/* 发送队列 (解决响应丢失问题) */
#define TX_QUEUE_SIZE 4
static uint8_t tx_queue[TX_QUEUE_SIZE][UART_TX_BUFFER_SIZE];
static volatile uint8_t tx_queue_len[TX_QUEUE_SIZE];
static volatile uint8_t tx_queue_head = 0;
static volatile uint8_t tx_queue_tail = 0;
static volatile uint8_t tx_queue_count = 0;

/* 单字节接收缓冲 */
static uint8_t rx_byte;

/* 帧解析状态
 * 帧格式: [HEAD][SEQ][LEN][CMD][DATA][CRC16(2)][TAIL]
 * 正确顺序: HEAD -> SEQ -> LEN -> DATA(包含CMD+DATA+CRC) -> TAIL
 */
typedef enum {
    STATE_WAIT_HEAD,
    STATE_WAIT_SEQ,   /* 修复: 增加SEQ状态，避免将SEQ字节误当LEN处理 */
    STATE_WAIT_LEN,
    STATE_WAIT_DATA,
    STATE_WAIT_TAIL
} UartParseState;

static UartParseState parse_state = STATE_WAIT_HEAD;
static uint8_t frame_buffer[64];
static uint8_t frame_len = 0;   /* 存储 LEN 字段值 = CMD+DATA 总字节数 */
static uint8_t frame_idx = 0;

/**
 * @brief 初始化 UART 模块
 */
void uart_comm_init(void)
{
    rx_head = 0;
    rx_tail = 0;
    tx_busy = 0;
    parse_state = STATE_WAIT_HEAD;
    frame_idx = 0;
    frame_len = 0;
    
    /* 初始化发送队列 */
    tx_queue_head = 0;
    tx_queue_tail = 0;
    tx_queue_count = 0;
    
    /* 启动中断接收 */
    HAL_UART_Receive_IT(&huart1, &rx_byte, 1);
}

/**
 * @brief 环形缓冲区写入
 * @note  此函数在中断上下文中调用，需要保证原子性
 */
static void rx_buffer_push(uint8_t data)
{
    uint16_t next = (rx_head + 1) % UART_RX_BUFFER_SIZE;
    if (next != rx_tail)
    {
        rx_buffer[rx_head] = data;
        rx_head = next;
    }
    /* 如果缓冲区满，丢弃新数据 (可以考虑添加溢出计数器) */
}

/**
 * @brief 环形缓冲区读取
 * @note  此函数在主循环中调用，需要禁用中断保护临界区
 */
static int rx_buffer_pop(uint8_t* data)
{
    if (rx_head == rx_tail) return 0;
    
    /* 禁用中断，保护临界区 */
    __disable_irq();
    *data = rx_buffer[rx_tail];
    rx_tail = (rx_tail + 1) % UART_RX_BUFFER_SIZE;
    __enable_irq();
    
    return 1;
}

/**
 * @brief UART 接收完成回调
 */
void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart)
{
    if (huart->Instance == USART1)
    {
        rx_buffer_push(rx_byte);
        HAL_UART_Receive_IT(&huart1, &rx_byte, 1);
    }
}

/**
 * @brief UART 发送完成回调
 */
void HAL_UART_TxCpltCallback(UART_HandleTypeDef *huart)
{
    if (huart->Instance == USART1)
    {
        /* 检查发送队列中是否有待发送的数据 */
        if (tx_queue_count > 0)
        {
            /* 从队列取出数据发送 */
            uint8_t len = tx_queue_len[tx_queue_tail];
            if (len > 0 && len <= UART_TX_BUFFER_SIZE)
            {
                memcpy(tx_buffer, tx_queue[tx_queue_tail], len);
                tx_queue_tail = (tx_queue_tail + 1) % TX_QUEUE_SIZE;
                tx_queue_count--;
                
                /* tx_busy 保持为 1，继续发送 */
                if (HAL_UART_Transmit_DMA(&huart1, tx_buffer, len) != HAL_OK)
                {
                    tx_busy = 0;
                }
                return;
            }
        }
        /* 队列为空，标记发送完成 */
        tx_busy = 0;
    }
}

/**
 * @brief 解析一个字节
 * @return 1 表示收到完整帧，0 表示继续等待
 *
 * 帧格式: [HEAD(1)][SEQ(1)][LEN(1)][CMD+DATA(LEN字节)][CRC16(2)][TAIL(1)]
 * 完整帧总字节数 = 1+1+1+LEN+2+1 = LEN+6
 */
static int parse_byte(uint8_t byte)
{
    switch (parse_state)
    {
        case STATE_WAIT_HEAD:
            if (byte == FRAME_HEAD)
            {
                frame_idx = 0;
                frame_buffer[frame_idx++] = byte;  /* [0]=HEAD */
                parse_state = STATE_WAIT_SEQ;
            }
            break;

        case STATE_WAIT_SEQ:
            /* 接收 SEQ 字节，0-255 均合法，直接存储 */
            if (frame_idx < sizeof(frame_buffer))
            {
                frame_buffer[frame_idx++] = byte;  /* [1]=SEQ */
                parse_state = STATE_WAIT_LEN;
            }
            else
            {
                parse_state = STATE_WAIT_HEAD;
                frame_idx = 0;
            }
            break;

        case STATE_WAIT_LEN:
            /* 接收 LEN 字节，表示后续 CMD+DATA 的字节数 */
            frame_len = byte;
            if (frame_idx < sizeof(frame_buffer) &&
                frame_len > 0 &&
                frame_len <= (FRAME_MAX_DATA_LEN + 1))
            {
                frame_buffer[frame_idx++] = byte;  /* [2]=LEN */
                parse_state = STATE_WAIT_DATA;
            }
            else
            {
                /* 长度无效，重置状态机 */
                parse_state = STATE_WAIT_HEAD;
                frame_idx = 0;
            }
            break;

        case STATE_WAIT_DATA:
            /* 接收 CMD+DATA+CRC16 共 frame_len+2 字节
             * 已写入 HEAD(1)+SEQ(1)+LEN(1)=3 字节
             * 目标总字节数(不含TAIL): 3 + frame_len + 2 = frame_len+5 */
            if (frame_idx < sizeof(frame_buffer))
            {
                frame_buffer[frame_idx++] = byte;
                if (frame_idx >= (uint8_t)(frame_len + 5))
                {
                    parse_state = STATE_WAIT_TAIL;
                }
            }
            else
            {
                /* 缓冲区溢出，重置状态机 */
                parse_state = STATE_WAIT_HEAD;
                frame_idx = 0;
            }
            break;

        case STATE_WAIT_TAIL:
            /* 接收 TAIL 字节 */
            if (frame_idx < sizeof(frame_buffer))
            {
                frame_buffer[frame_idx++] = byte;
            }
            parse_state = STATE_WAIT_HEAD;
            if (byte == FRAME_TAIL)
            {
                return 1;  /* 完整帧 */
            }
            /* 帧尾错误，丢弃此帧 */
            frame_idx = 0;
            break;

        default:
            /* 未知状态，重置 */
            parse_state = STATE_WAIT_HEAD;
            frame_idx = 0;
            break;
    }
    return 0;
}

/**
 * @brief 处理接收到的数据
 */
void uart_comm_process(CommandCallback callback)
{
    uint8_t byte;
    Command cmd;
    
    while (rx_buffer_pop(&byte))
    {
        if (parse_byte(byte))
        {
            if (cmd_parse(frame_buffer, frame_idx, &cmd) == PARSE_OK)
            {
                if (callback)
                {
                    callback(&cmd);
                }
            }
        }
    }
}

/**
 * @brief 发送响应
 * @note  使用关中断保护临界区，防止与 TxCpltCallback 竞态
 *        使用临时缓冲区编码，避免直接操作共享的 tx_buffer
 */
void uart_comm_send_response(const Response* rsp)
{
    /* 编码到临时缓冲区，避免直接操作共享的 tx_buffer */
    uint8_t tmp_buf[UART_TX_BUFFER_SIZE];
    size_t len = cmd_encode(rsp, tmp_buf);
    if (len == 0 || len > UART_TX_BUFFER_SIZE) return;

    /* 关中断保护临界区：检查 tx_busy、拷贝数据、启动 DMA 必须原子执行
     * 防止 TxCpltCallback 在 if(!tx_busy) 与 tx_busy=1 之间插入 */
    __disable_irq();

    if (!tx_busy)
    {
        /* 当前空闲，直接启动 DMA 发送 */
        memcpy(tx_buffer, tmp_buf, len);
        tx_busy = 1;
        __enable_irq();

        if (HAL_UART_Transmit_DMA(&huart1, tx_buffer, (uint16_t)len) != HAL_OK)
        {
            __disable_irq();
            tx_busy = 0;
            __enable_irq();
        }
        return;
    }

    /* 正在发送，加入队列 */
    if (tx_queue_count < TX_QUEUE_SIZE)
    {
        memcpy(tx_queue[tx_queue_head], tmp_buf, len);
        tx_queue_len[tx_queue_head] = (uint8_t)len;
        tx_queue_head = (tx_queue_head + 1) % TX_QUEUE_SIZE;
        tx_queue_count++;
    }
    /* 队列满时丢弃 */

    __enable_irq();
}
