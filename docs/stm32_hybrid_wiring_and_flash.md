# STM32 混合三轴接线与烧录指南

本文档对应当前最新控制方案：

- `pan / tilt`：PWM 舵机二维云台
- `rail`：步进滑轨
- `STM32`：`STM32F407VET6`
- `Jetson`：作为上位机，通过串口协议控制 STM32

当前版本不接入限位和急停。

## 1. 控制架构

```text
Jetson
  -> 串口 / USB-UART
STM32F407VET6
  -> PA8  -> pan servo signal
  -> PA0  -> tilt servo signal
  -> PA6  -> rail STEP
  -> PD3  -> rail DIR
  -> PD4  -> rail EN
  -> PA9  -> USART1_TX
  -> PA10 -> USART1_RX
```

## 2. 核心引脚对应

### 2.1 云台舵机

| 功能 | STM32 引脚 | 外设 | 说明 |
| --- | --- | --- | --- |
| pan 舵机信号 | `PA8` | `TIM1_CH1` | 50Hz PWM |
| tilt 舵机信号 | `PA0` | `TIM2_CH1` | 50Hz PWM |

### 2.2 滑轨步进轴

| 功能 | STM32 引脚 | 外设 | 说明 |
| --- | --- | --- | --- |
| rail STEP | `PA6` | `TIM3_CH1` | 步进脉冲 |
| rail DIR | `PD3` | GPIO | 方向控制 |
| rail EN | `PD4` | GPIO | 使能控制 |

### 2.3 Jetson 串口通信

| 功能 | STM32 引脚 | 说明 |
| --- | --- | --- |
| USART1_TX | `PA9` | 接 Jetson 侧 RX |
| USART1_RX | `PA10` | 接 Jetson 侧 TX |
| GND | 任一系统地 | 必须与 Jetson 共地 |

## 3. 云台舵机接线

二维云台为 PWM 舵机方案，通常每个舵机是三根线：

- `V+`：舵机电源正极
- `GND`：舵机电源负极
- `SIG`：控制信号

建议接线如下：

### 3.1 pan 舵机

- 舵机 `SIG` -> STM32 `PA8`
- 舵机 `V+` -> 外部舵机电源正极
- 舵机 `GND` -> 外部舵机电源负极

### 3.2 tilt 舵机

- 舵机 `SIG` -> STM32 `PA0`
- 舵机 `V+` -> 外部舵机电源正极
- 舵机 `GND` -> 外部舵机电源负极

### 3.3 舵机电源要求

- 电压：`5V ~ 8.4V`
- 电流能力：建议 `3A` 以上
- 不建议直接从 STM32 板载 5V 给云台舵机供电

### 3.4 地线要求

以下地线必须共地：

- 舵机电源负极
- STM32 GND
- Jetson GND
- rail 驱动器控制地

如果不共地，舵机 PWM 和串口信号都可能异常。

## 4. rail 轴步进驱动接线

当前 `rail` 轴仍按步进驱动方式控制。你之前确认驱动器为 `TB6600`，因此按典型 `TB6600` 接法说明。

### 4.1 STM32 -> TB6600 控制侧

| STM32 | TB6600 | 说明 |
| --- | --- | --- |
| `PA6` | `PUL+` 或 `PUL-` 对应信号侧 | STEP 脉冲 |
| `PD3` | `DIR+` 或 `DIR-` 对应信号侧 | 方向 |
| `PD4` | `ENA+` 或 `ENA-` 对应信号侧 | 使能 |
| `GND` | 控制侧地 | 共地 |

TB6600 输入有两种常见接法，现场请按你手上驱动的标识选择其一：

#### 接法 A：共阳接法

- `PUL+ / DIR+ / ENA+` -> `+5V`
- `PUL-` -> `PA6`
- `DIR-` -> `PD3`
- `ENA-` -> `PD4`
- STM32 GND 与驱动控制地共地

#### 接法 B：共阴接法

- `PUL- / DIR- / ENA-` -> `GND`
- `PUL+` -> `PA6`
- `DIR+` -> `PD3`
- `ENA+` -> `PD4`

如果驱动板说明书明确要求光耦电流方向，请优先按驱动板手册。

### 4.2 TB6600 -> 电机 / 电源

| TB6600 端子 | 连接对象 |
| --- | --- |
| `A+ A- B+ B-` | 步进电机四线 |
| `V+` / `DC+` | 滑轨电源正极 |
| `V-` / `DC-` | 滑轨电源负极 |

注意：

- 电机电源和逻辑控制信号不是一回事
- 驱动器主电源正负极一定不能接反
- `PWR / ALARM` 之类端子通常不是电机供电主端子，现场按驱动器丝印和说明书接

## 5. Jetson 与 STM32 串口连接

推荐两种方式。

### 方式 A：USB-UART 模块

```text
Jetson USB
  -> USB-UART 模块
  -> TX -> STM32 PA10
  -> RX -> STM32 PA9
  -> GND -> STM32 GND
```

即：

- USB-UART `TX` -> STM32 `PA10 (USART1_RX)`
- USB-UART `RX` -> STM32 `PA9 (USART1_TX)`
- USB-UART `GND` -> STM32 `GND`

### 方式 B：Jetson 硬件串口直连

如果直接使用 Jetson UART：

- Jetson `TX` -> STM32 `PA10`
- Jetson `RX` -> STM32 `PA9`
- Jetson `GND` -> STM32 `GND`

串口参数：

- 波特率：`115200`
- 数据位：`8`
- 停止位：`1`
- 校验：`None`

## 6. 整体接线总览

```text
外部舵机电源 +
  -> pan servo V+
  -> tilt servo V+

外部舵机电源 -
  -> pan servo GND
  -> tilt servo GND
  -> STM32 GND
  -> Jetson GND
  -> rail driver control GND

STM32 PA8
  -> pan servo SIG

STM32 PA0
  -> tilt servo SIG

STM32 PA6
  -> rail driver STEP

STM32 PD3
  -> rail driver DIR

STM32 PD4
  -> rail driver EN

Jetson TX
  -> STM32 PA10

Jetson RX
  -> STM32 PA9
```

## 7. 固件文件位置

当前已构建好的固件文件在：

- `stm32/CameraControl/build/Release/CameraControl.hex`
- `stm32/CameraControl/build/Release/CameraControl.bin`
- `stm32/CameraControl/build/Release/CameraControl.elf`

绝对路径：

- `D:\毕设\camena-control new\stm32\CameraControl\build\Release\CameraControl.hex`
- `D:\毕设\camena-control new\stm32\CameraControl\build\Release\CameraControl.bin`
- `D:\毕设\camena-control new\stm32\CameraControl\build\Release\CameraControl.elf`

## 8. 烧录方式

### 8.1 使用 STM32CubeProgrammer 图形界面

推荐方式：

1. 用 ST-Link 连接 STM32
2. 打开 STM32CubeProgrammer
3. 连接方式选择 `SWD`
4. 选择固件文件：
   - 优先用 `CameraControl.hex`
   - 或使用 `CameraControl.bin` 并把起始地址设为 `0x08000000`
5. 执行烧录
6. 复位验证

### 8.2 使用仓库脚本

构建：

```powershell
powershell -ExecutionPolicy Bypass -File "D:\毕设\camena-control new\stm32\CameraControl\build_firmware.ps1" -Preset Release
```

烧录：

```powershell
powershell -ExecutionPolicy Bypass -File "D:\毕设\camena-control new\stm32\CameraControl\flash_firmware.ps1" -Preset Release
```

如果只想查看命令而不实际烧录：

```powershell
powershell -ExecutionPolicy Bypass -File "D:\毕设\camena-control new\stm32\CameraControl\flash_firmware.ps1" -Preset Release -DryRun
```

## 9. 上电检查顺序

推荐按下面顺序联调：

1. 只接 STM32 和 ST-Link，先烧录固件
2. 接上舵机电源，但先不装机械负载
3. 确认 pan / tilt 上电居中，舵机不抖动异常
4. 再接 rail 驱动与电机
5. 最后接 Jetson 串口
6. 启动 Jetson 主程序，确认串口联通

## 10. 当前版本说明

- 当前版本没有接限位和急停输入
- `pan / tilt` 为舵机估计位置，不是编码器闭环位置
- 如果现场发现某轴方向相反：
  - 舵机轴优先在机械装配或角度映射中修正
  - rail 轴优先通过 `DIR` 方向或软件方向定义修正
