# STM32 运动控制固件

## 概述

本目录包含相机位姿控制系统的 STM32F407VET6 固件工程。它负责三轴步进电机控制、安全监控，以及与 Jetson Nano 的串口通信。

当前工程已经对齐以下联调约定：

- 串口协议使用 `v2.0` 帧格式：`[HEAD][SEQ][LEN][CMD][DATA][CRC16][TAIL]`
- `MOVE_ABSOLUTE` / `POSITION` 的位置单位为 `0.01 度 / 0.01 mm`
- `SET_VELOCITY` 的速度单位为 `steps/s`
- `STOP` 支持“单轴停止”与“全轴停止”
- 构建产物可直接生成 `elf / hex / bin`

## 硬件配置

- MCU: `STM32F407VET6`
- 主频: `168MHz`
- 通信: `USART1 @ 115200`
- 电机输出: `TIM1 / TIM2 / TIM3 PWM`
- 驱动器: `TMC2209`
- 支持接口: `Pan / Tilt / Rail / ESTOP / Limit Switch`

## 目录结构

- `CameraControl/CameraControl.ioc`: CubeMX 工程
- `CameraControl/CMakeLists.txt`: CMake 构建入口
- `CameraControl/CMakePresets.json`: 预设构建与烧录目标
- `CameraControl/Core/Inc`: 业务头文件
- `CameraControl/Core/Src`: 业务源码
- `CameraControl/Drivers`: HAL / CMSIS 驱动

## 通信协议

### 帧格式

协议帧格式如下：

```text
[HEAD][SEQ][LEN][CMD][DATA][CRC16][TAIL]
```

- `HEAD`: 固定为 `0xAA`
- `SEQ`: 1 字节序列号，由 Jetson 生成，STM32 在响应中回显
- `LEN`: `CMD + DATA` 的总字节数
- `CMD`: 命令字
- `DATA`: 命令负载
- `CRC16`: 对 `SEQ + LEN + CMD + DATA` 做 CRC16-CCITT
- `TAIL`: 固定为 `0x55`

### 主要命令

| 命令 | 值 | 数据格式 | 说明 |
| --- | --- | --- | --- |
| `CMD_POSITION` | `0x01` | `axis(1) + value(4)` | 位置控制，单位 `0.01 度 / 0.01 mm` |
| `CMD_STATUS` | `0x02` | 无 | 查询当前状态与位置 |
| `CMD_CONFIG` | `0x03` | `axis(1) + packed_value(4)` | 参数配置 |
| `CMD_ESTOP` | `0x04` | 无 | 急停 |
| `CMD_HOME` | `0x05` | `axis(1)` | 回零 |
| `CMD_SET_VELOCITY` | `0x06` | `axis(1) + value(4)` | 速度控制，单位 `steps/s` |
| `CMD_STOP` | `0x07` | 可选 `axis(1)` | 停止一个轴，或不带参数时停止全部 |
| `CMD_MOVE_ABSOLUTE` | `0x08` | `axis(1) + value(4)` | 绝对位置移动 |

## CONFIG 参数编码

`CMD_CONFIG` 的 `value` 字段使用 32 位打包格式：

```text
high 16 bits = 参数 ID
low 16 bits  = 参数值
```

STM32 侧对应定义见 `ConfigParamId`，目前支持如下参数：

| 参数 ID | 名称 | 低 16 位含义 | 轴字段是否生效 |
| --- | --- | --- | --- |
| `0x0001` | `CONFIG_MAX_VELOCITY` | 全局运动速度上限 | 否 |
| `0x0002` | `CONFIG_MAX_ACCEL` | 全局运动加速度上限 | 否 |
| `0x0003` | `CONFIG_PID_P` | `P * 100` | 是 |
| `0x0004` | `CONFIG_PID_I` | `I * 100` | 是 |
| `0x0005` | `CONFIG_PID_D` | `D * 100` | 是 |
| `0x0010` | `CONFIG_WATCHDOG_TIMEOUT_MS` | 看门狗超时，单位 `ms` | 否 |
| `0x0011` | `CONFIG_WATCHDOG_ENABLE` | `0=关闭`，非 `0=开启` | 否 |
| `0x0020` | `CONFIG_PAN_MIN_LIMIT` | `Pan` 最小位置，`int16` | 否 |
| `0x0021` | `CONFIG_PAN_MAX_LIMIT` | `Pan` 最大位置，`int16` | 否 |
| `0x0022` | `CONFIG_TILT_MIN_LIMIT` | `Tilt` 最小位置，`int16` | 否 |
| `0x0023` | `CONFIG_TILT_MAX_LIMIT` | `Tilt` 最大位置，`int16` | 否 |
| `0x0024` | `CONFIG_RAIL_MIN_LIMIT` | `Rail` 最小位置，`uint16` | 否 |
| `0x0025` | `CONFIG_RAIL_MAX_LIMIT` | `Rail` 最大位置，`uint16` | 否 |

说明：

- `PID_*` 配置会使用命令里的 `axis`
- 限位类参数由参数 ID 本身决定轴，因此 `axis` 字段目前不会参与分发
- `Pan / Tilt` 限位按有符号 `int16` 解释，`Rail` 限位按无符号 `uint16` 解释
- 限位位置单位仍为 `0.01 度 / 0.01 mm`
- `CONFIG_MAX_VELOCITY` 和 `CONFIG_MAX_ACCEL` 是全局 S 曲线参数，最终仍会被各轴安全上限再次限幅

## 当前联调约束

### 行程范围

| 轴 | 范围 | 单位 |
| --- | --- | --- |
| `Pan` | `-18000 ~ 18000` | `0.01 度` |
| `Tilt` | `-9000 ~ 9000` | `0.01 度` |
| `Rail` | `0 ~ 50000` | `0.01 mm` |

### 速度上限

| 轴 | STM32 限制 | Jetson 发送单位 |
| --- | --- | --- |
| `Pan` | `1000 steps/s` | `steps/s` |
| `Tilt` | `800 steps/s` | `steps/s` |
| `Rail` | `16000 steps/s` | `steps/s` |

### 控制层内部可读上限

这些值是 STM32 运动控制内部用于 PID / S 曲线限幅的“人类可读单位”：

- `Pan`: `3000`，即 `30.00 度/s`
- `Tilt`: `2000`，即 `20.00 度/s`
- `Rail`: `600`，即 `6.00 mm/s`

## 构建

推荐直接使用 CMake Presets：

```bash
cd stm32/CameraControl
cmake --preset Debug
cmake --build --preset Debug
```

构建完成后会生成：

- `stm32/CameraControl/build/Debug/CameraControl.elf`
- `stm32/CameraControl/build/Debug/CameraControl.hex`
- `stm32/CameraControl/build/Debug/CameraControl.bin`

如果当前终端环境里 `cmake --build` / `ninja` 在收尾阶段容易挂住，推荐直接使用仓库内脚本：

```powershell
cd stm32/CameraControl
powershell -ExecutionPolicy Bypass -File .\build_firmware.ps1
```

可选参数示例：

```powershell
# 使用 Release 目录构建
powershell -ExecutionPolicy Bypass -File .\build_firmware.ps1 -Preset Release

# 调长主构建和手动链接超时
powershell -ExecutionPolicy Bypass -File .\build_firmware.ps1 -BuildTimeoutSeconds 90 -LinkTimeoutSeconds 90
```

脚本内部流程为：

1. 必要时自动执行 `cmake --preset <Preset>`
2. 先尝试正常 `cmake --build`
3. 如果构建进程挂住或 `elf` 未更新，则自动提取 `ninja` 链接命令并手动链接
4. 使用 `objcopy` 重新生成 `hex / bin`

## 直接烧录

如果本机已安装 `STM32CubeProgrammer`，可以直接使用：

```bash
cd stm32/CameraControl
cmake --build --preset Debug-Flash
```

或者直接使用仓库脚本：

```powershell
cd stm32/CameraControl
powershell -ExecutionPolicy Bypass -File .\flash_firmware.ps1
```

脚本默认会先调用 `build_firmware.ps1`，再执行烧录。若只想检查命令而不真正烧录，可使用：

```powershell
powershell -ExecutionPolicy Bypass -File .\flash_firmware.ps1 -DryRun
```

如果只需要擦除芯片：

```bash
cd stm32/CameraControl
cmake --build build/Debug --target erase
```

默认烧录方式为：

- 接口: `SWD`
- 连接模式: `UR`
- 复位方式: `HWrst`
- 烧录地址: `0x08000000`

## 联调建议

- 端到端命令链路说明见 `docs/jetson_stm32_comm_flow.md`
- Jetson 发送 `SET_VELOCITY` 时请直接发送 `steps/s`
- Jetson 发送 `MOVE_ABSOLUTE` 时请使用 `0.01 度 / 0.01 mm`
- 若需要单轴停止，请发送 `CMD_STOP + axis`
- 若需要全轴停止，请发送不带轴负载的 `CMD_STOP`
- 如果重新生成 CubeMX 代码，请保留 `Core/Src` 与 `Core/Inc` 中的业务逻辑改动

## 备注

- `flash` 目标会自动依赖固件构建，因此无需手动先构建一次
- 即使找不到 `STM32_Programmer_CLI`，仍然可以正常生成 `elf / hex / bin`
- 当前仓库中的构建脚本已经将 `hex / bin` 生成从链接后处理里拆出，以减少 Windows 路径含空格时的构建卡住问题
- `build_firmware.ps1` 会把主构建、手动链接和产物生成日志写到 `stm32/CameraControl/logs/`
