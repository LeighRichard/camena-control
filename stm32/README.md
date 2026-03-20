# STM32 运动控制器固件

## 概述

本目录包含相机位置控制系统的 STM32F407VET6 运动控制器固件。

## 硬件配置

- **MCU**: STM32F407VET6 (168MHz, 512KB Flash, 192KB RAM)
- **系统时钟**: 168MHz (HSE 8MHz + PLL)
- **定时器**: TIM1/TIM2/TIM3 用于步进电机 PWM 脉冲
- **串口**: USART1 (115200 bps) 与 Jetson Nano 通信

## 引脚分配

### 电机控制
| 功能 | 引脚 | 说明 |
|------|------|------|
| PAN_STEP | PA8 (TIM1_CH1) | Pan 轴步进脉冲 |
| PAN_DIR | PB0 | Pan 轴方向 |
| PAN_EN | PB1 | Pan 轴使能 |
| TILT_STEP | PA0 (TIM2_CH1) | Tilt 轴步进脉冲 |
| TILT_DIR | PB2 | Tilt 轴方向 |
| TILT_EN | PB3 | Tilt 轴使能 |
| RAIL_STEP | PA6 (TIM3_CH1) | Rail 轴步进脉冲 |
| RAIL_DIR | PB4 | Rail 轴方向 |
| RAIL_EN | PB5 | Rail 轴使能 |

### 限位开关
| 功能 | 引脚 | 说明 |
|------|------|------|
| PAN_LIMIT_POS | PC0 | Pan 正限位 |
| PAN_LIMIT_NEG | PC1 | Pan 负限位 |
| TILT_LIMIT_POS | PC2 | Tilt 正限位 |
| TILT_LIMIT_NEG | PC3 | Tilt 负限位 |
| RAIL_LIMIT_POS | PC4 | Rail 正限位 |
| RAIL_LIMIT_NEG | PC5 | Rail 负限位 |
| ESTOP | PC6 | 急停按钮 |

### 串口通信
| 功能 | 引脚 |
|------|------|
| USART1_TX | PA9 |
| USART1_RX | PA10 |

## CubeMX 项目

`CameraControl.ioc` 是 STM32CubeMX 项目文件，包含完整的硬件配置。

### 使用方法

1. 安装 [STM32CubeMX](https://www.st.com/en/development-tools/stm32cubemx.html)
2. 打开 `CameraControl.ioc`
3. 点击 "Generate Code" 生成 HAL 库代码
4. 将生成的代码与本项目的业务逻辑代码合并

### 配置摘要

- **时钟**: HSE 8MHz → PLL → SYSCLK 168MHz
- **USART1**: 115200 bps, 8N1, DMA TX
- **TIM1**: PWM CH1 (PA8), 1MHz 计数频率
- **TIM2**: PWM CH1 (PA0), 1MHz 计数频率
- **TIM3**: PWM CH1 (PA6), 1MHz 计数频率
- **GPIO**: 电机控制 (PB0-PB5), 限位开关 (PC0-PC6)

## 编译

### 使用 Makefile (推荐)

```bash
# 需要 arm-none-eabi-gcc 工具链
make
```

### 使用 CMake

```bash
mkdir build && cd build
cmake -DCMAKE_TOOLCHAIN_FILE=../arm-gcc-toolchain.cmake ..
make
```

## 文件结构

```
stm32/
├── CameraControl.ioc      # CubeMX 项目文件
├── CMakeLists.txt         # CMake 构建配置
├── README.md              # 本文件
├── inc/                   # 头文件
│   ├── main.h             # 主程序头文件 (引脚定义)
│   ├── motion.h           # 运动控制模块
│   ├── protocol.h         # 通信协议
│   ├── safety.h           # 安全监控模块
│   ├── uart.h             # UART 通信模块
│   └── stm32f4xx_it.h     # 中断处理
└── src/                   # 源文件
    ├── main.c             # 主程序 (含硬件初始化)
    ├── motion.c           # 运动控制实现
    ├── protocol.c         # 协议解析实现
    ├── safety.c           # 安全监控实现
    ├── uart.c             # UART 通信实现
    ├── stm32f4xx_hal_msp.c # HAL MSP 初始化
    └── stm32f4xx_it.c     # 中断服务程序
```

## 功能模块

### 运动控制 (motion.c)
- S 曲线速度规划
- PID 位置控制
- 步进电机脉冲输出
- 位置反馈 (步数计数)

### 安全监控 (safety.c)
- 限位开关检测
- 急停按钮处理
- 通信看门狗
- 过流/过热保护 (预留)

### 通信协议 (protocol.c)
- 帧格式: [HEAD][LEN][CMD][DATA][CRC16][TAIL]
- 支持位置控制、状态查询、急停等指令

### UART 通信 (uart.c)
- 环形缓冲区接收
- DMA 发送
- 帧解析状态机

## 烧录

使用 ST-Link 或 J-Link 烧录生成的 `.hex` 或 `.bin` 文件。
