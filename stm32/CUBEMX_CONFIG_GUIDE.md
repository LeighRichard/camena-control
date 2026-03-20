# STM32CubeMX 配置指南

本文档详细说明如何使用 STM32CubeMX 为相机位置控制系统配置 STM32F407VET6。

---

## 第一步：创建新项目

1. 打开 STM32CubeMX
2. 点击 **ACCESS TO MCU SELECTOR**
3. 在搜索框输入 `STM32F407VET6`
4. 双击选择该芯片，创建新项目

---

## 第二步：配置时钟源 (RCC)

在左侧 **Pinout & Configuration** 面板：

1. 展开 **System Core** → 点击 **RCC**
2. 配置：
   - **High Speed Clock (HSE)**: `Crystal/Ceramic Resonator`
   - **Low Speed Clock (LSE)**: 可选，不需要可保持 Disable

---

## 第三步：配置时钟树 (Clock Configuration)

点击顶部 **Clock Configuration** 标签页：

```
时钟配置目标：SYSCLK = 168MHz

配置步骤：
1. Input frequency: 8 (假设外部晶振 8MHz)
2. 选择 HSE 作为 PLL Source Mux 输入
3. PLL 参数：
   - PLLM: /8  (8MHz ÷ 8 = 1MHz)
   - PLLN: ×336 (1MHz × 336 = 336MHz)
   - PLLP: /2  (336MHz ÷ 2 = 168MHz)
   - PLLQ: /7  (336MHz ÷ 7 = 48MHz，用于 USB)
4. System Clock Mux: 选择 PLLCLK
5. AHB Prescaler: /1 → HCLK = 168MHz
6. APB1 Prescaler: /4 → APB1 = 42MHz, APB1 Timer = 84MHz
7. APB2 Prescaler: /2 → APB2 = 84MHz, APB2 Timer = 168MHz
```

配置完成后，确认：
- SYSCLK = 168 MHz
- HCLK = 168 MHz
- APB1 Timer clocks = 84 MHz
- APB2 Timer clocks = 168 MHz

---

## 第四步：配置 USART1 (与 Jetson Nano 通信)

在左侧面板：

1. 展开 **Connectivity** → 点击 **USART1**
2. Mode: `Asynchronous`
3. 参数配置 (Parameter Settings)：
   - Baud Rate: `115200`
   - Word Length: `8 Bits`
   - Parity: `None`
   - Stop Bits: `1`
4. DMA Settings (可选，用于高效发送)：
   - 点击 **Add**
   - Select: `USART1_TX`
   - Direction: `Memory To Peripheral`
   - Priority: `Low`
5. NVIC Settings：
   - ☑️ USART1 global interrupt: `Enabled`

引脚自动分配：
- PA9 → USART1_TX
- PA10 → USART1_RX

---

## 第五步：配置 TIM1 (Pan 轴步进脉冲)

1. 展开 **Timers** → 点击 **TIM1**
2. Clock Source: `Internal Clock`
3. Channel1: `PWM Generation CH1`
4. 参数配置 (Parameter Settings → Counter Settings)：
   - Prescaler: `167` (168MHz ÷ 168 = 1MHz 计数频率)
   - Counter Period: `999` (1MHz ÷ 1000 = 1kHz 默认 PWM 频率)
   - auto-reload preload: `Enable`
5. PWM Generation Channel 1：
   - Mode: `PWM mode 1`
   - Pulse: `500` (50% 占空比)
   - CH Polarity: `High`
6. NVIC Settings：
   - ☑️ TIM1 update interrupt: `Enabled` (用于步数计数)

引脚：PA8 → TIM1_CH1 (PAN_STEP)

---

## 第六步：配置 TIM2 (Tilt 轴步进脉冲)

1. 点击 **TIM2**
2. Clock Source: `Internal Clock`
3. Channel1: `PWM Generation CH1`
4. 参数配置：
   - Prescaler: `83` (84MHz ÷ 84 = 1MHz)
   - Counter Period: `999`
   - auto-reload preload: `Enable`
5. PWM Generation Channel 1：
   - Mode: `PWM mode 1`
   - Pulse: `500`
6. NVIC Settings：
   - ☑️ TIM2 global interrupt: `Enabled`

引脚：PA0 → TIM2_CH1 (TILT_STEP)

---

## 第七步：配置 TIM3 (Rail 轴步进脉冲)

1. 点击 **TIM3**
2. Clock Source: `Internal Clock`
3. Channel1: `PWM Generation CH1`
4. 参数配置：
   - Prescaler: `83`
   - Counter Period: `999`
   - auto-reload preload: `Enable`
5. PWM Generation Channel 1：
   - Mode: `PWM mode 1`
   - Pulse: `500`
6. NVIC Settings：
   - ☑️ TIM3 global interrupt: `Enabled`

引脚：PA6 → TIM3_CH1 (RAIL_STEP)

---

## 第八步：配置 GPIO - 电机方向和使能

在芯片引脚图上直接点击配置，或在 **System Core** → **GPIO** 中配置：

### 电机方向引脚 (输出)

| 引脚 | 标签 | 模式 | 初始状态 |
|------|------|------|----------|
| PB0 | PAN_DIR | GPIO_Output | Low |
| PB1 | PAN_EN | GPIO_Output | High (禁用) |
| PB2 | TILT_DIR | GPIO_Output | Low |
| PB3 | TILT_EN | GPIO_Output | High (禁用) |
| PB4 | RAIL_DIR | GPIO_Output | Low |
| PB5 | RAIL_EN | GPIO_Output | High (禁用) |

配置方法：
1. 在芯片图上点击 PB0
2. 选择 `GPIO_Output`
3. 在右侧 GPIO 配置中：
   - User Label: `PAN_DIR`
   - GPIO output level: `Low`
   - GPIO mode: `Output Push Pull`
   - GPIO Pull-up/Pull-down: `No pull-up and no pull-down`
   - Maximum output speed: `Low`

对 PB1-PB5 重复上述步骤。

**注意**：EN 引脚初始状态设为 High，因为 TMC2209 驱动器高电平禁用。

---

## 第九步：配置 GPIO - 限位开关和急停

### 限位开关引脚 (输入上拉)

| 引脚 | 标签 | 模式 |
|------|------|------|
| PC0 | PAN_LIMIT_POS | GPIO_Input (Pull-up) |
| PC1 | PAN_LIMIT_NEG | GPIO_Input (Pull-up) |
| PC2 | TILT_LIMIT_POS | GPIO_Input (Pull-up) |
| PC3 | TILT_LIMIT_NEG | GPIO_Input (Pull-up) |
| PC4 | RAIL_LIMIT_POS | GPIO_Input (Pull-up) |
| PC5 | RAIL_LIMIT_NEG | GPIO_Input (Pull-up) |
| PC6 | ESTOP | GPIO_Input (Pull-up) |

配置方法：
1. 在芯片图上点击 PC0
2. 选择 `GPIO_Input`
3. 在右侧 GPIO 配置中：
   - User Label: `PAN_LIMIT_POS`
   - GPIO mode: `Input mode`
   - GPIO Pull-up/Pull-down: `Pull-up`

对 PC1-PC6 重复上述步骤。

---

## 第十步：配置 SYS (调试接口)

1. 展开 **System Core** → 点击 **SYS**
2. Debug: `Serial Wire` (使用 SWD 调试)
3. Timebase Source: `SysTick`

---

## 第十一步：配置 NVIC (中断优先级)

1. 展开 **System Core** → 点击 **NVIC**
2. 确认以下中断已启用：
   - ☑️ USART1 global interrupt
   - ☑️ DMA2 stream7 global interrupt (如果配置了 DMA)
   - ☑️ TIM1 update interrupt
   - ☑️ TIM2 global interrupt
   - ☑️ TIM3 global interrupt
3. 优先级设置 (建议)：
   - USART1: Preemption Priority = 0
   - DMA2_Stream7: Preemption Priority = 0
   - TIM1/TIM2/TIM3: Preemption Priority = 1

---

## 第十二步：项目设置 (Project Manager)

点击顶部 **Project Manager** 标签页：

### Project 设置
- Project Name: `CameraControl`
- Project Location: 选择保存路径
- Toolchain / IDE: `Makefile` 或 `STM32CubeIDE`

### Code Generator 设置
- ☑️ Generate peripheral initialization as a pair of '.c/.h' files per peripheral
- ☑️ Keep User Code when re-generating
- ☑️ Set all free pins as analog (to optimize power consumption)

---

## 第十三步：生成代码

1. 点击右上角 **GENERATE CODE**
2. 等待代码生成完成
3. 点击 **Open Project** 或手动打开生成的项目

---

## 生成的文件结构

```
CameraControl/
├── Core/
│   ├── Inc/
│   │   ├── main.h
│   │   ├── stm32f4xx_hal_conf.h
│   │   ├── stm32f4xx_it.h
│   │   └── gpio.h, tim.h, usart.h, dma.h
│   └── Src/
│       ├── main.c
│       ├── stm32f4xx_hal_msp.c
│       ├── stm32f4xx_it.c
│       └── gpio.c, tim.c, usart.c, dma.c
├── Drivers/
│   ├── CMSIS/
│   └── STM32F4xx_HAL_Driver/
├── Makefile
└── CameraControl.ioc
```

---

## 第十四步：集成业务逻辑代码

将以下文件复制到生成的项目中：

1. 复制头文件到 `Core/Inc/`：
   - `protocol.h`
   - `motion.h`
   - `safety.h`
   - `uart.h`

2. 复制源文件到 `Core/Src/`：
   - `protocol.c`
   - `motion.c`
   - `safety.c`
   - `uart.c`

3. 修改 `main.c`：
   - 在 `/* USER CODE BEGIN Includes */` 区域添加：
     ```c
     #include "protocol.h"
     #include "motion.h"
     #include "safety.h"
     #include "uart.h"
     ```
   - 在 `/* USER CODE BEGIN 2 */` 区域添加模块初始化：
     ```c
     uart_init();
     motion_init();
     safety_init();
     ```
   - 在 `/* USER CODE BEGIN 3 */` (while 循环内) 添加主循环逻辑

---

## 引脚总结

| 功能 | 引脚 | 模式 |
|------|------|------|
| PAN_STEP | PA8 | TIM1_CH1 PWM |
| TILT_STEP | PA0 | TIM2_CH1 PWM |
| RAIL_STEP | PA6 | TIM3_CH1 PWM |
| PAN_DIR | PB0 | GPIO Output |
| PAN_EN | PB1 | GPIO Output |
| TILT_DIR | PB2 | GPIO Output |
| TILT_EN | PB3 | GPIO Output |
| RAIL_DIR | PB4 | GPIO Output |
| RAIL_EN | PB5 | GPIO Output |
| PAN_LIMIT_POS | PC0 | GPIO Input Pull-up |
| PAN_LIMIT_NEG | PC1 | GPIO Input Pull-up |
| TILT_LIMIT_POS | PC2 | GPIO Input Pull-up |
| TILT_LIMIT_NEG | PC3 | GPIO Input Pull-up |
| RAIL_LIMIT_POS | PC4 | GPIO Input Pull-up |
| RAIL_LIMIT_NEG | PC5 | GPIO Input Pull-up |
| ESTOP | PC6 | GPIO Input Pull-up |
| USART1_TX | PA9 | USART1 TX |
| USART1_RX | PA10 | USART1 RX |
| SWDIO | PA13 | SYS Debug |
| SWCLK | PA14 | SYS Debug |
| HSE_IN | PH0 | RCC HSE |
| HSE_OUT | PH1 | RCC HSE |

---

## 常见问题

### Q: 时钟配置报错？
A: 检查 HSE 频率是否与实际晶振匹配。常见值：8MHz、12MHz、25MHz。

### Q: 定时器频率不对？
A: 检查 APB1/APB2 分频器设置。TIM2/TIM3 在 APB1 (84MHz)，TIM1 在 APB2 (168MHz)。

### Q: GPIO 初始状态不对？
A: 在 GPIO 配置中设置 "GPIO output level"。

### Q: 中断不触发？
A: 确认 NVIC 中对应中断已启用，并且优先级配置正确。
