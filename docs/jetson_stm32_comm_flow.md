# Jetson 与 STM32 串口联调链路

本文档用于说明当前仓库里 Jetson 到 STM32 的实际命令流、响应流，以及几个最容易在联调时混淆的行为差异。

## 总览

当前串口链路的核心路径如下：

```text
Jetson Web / 视觉伺服 / 心跳
    -> CommManager.send_command()
    -> protocol.encode_command()
    -> 串口 USART1
    -> STM32 uart_comm_process()
    -> protocol.cmd_parse()
    -> process_command()
    -> uart_comm_send_response()
    -> Jetson decode_response()
```

对应代码入口：

- Jetson 系统初始化与依赖注入：
  - `jetson/main.py`
  - `jetson/src/web/app.py`
- Jetson 串口发送与响应匹配：
  - `jetson/src/comm/manager.py`
  - `jetson/src/comm/protocol.py`
- STM32 收包、解析、执行与回包：
  - `stm32/CameraControl/Core/Src/uart_comm.c`
  - `stm32/CameraControl/Core/Src/protocol.c`
  - `stm32/CameraControl/Core/Src/main.c`

如果想直接观察链路细节，可在 `jetson/config/system_config.yaml` 中打开：

```yaml
comm:
  trace_protocol: true
  trace_frames_hex: true
  trace_history_size: 200
```

打开后，Jetson 会打印单行串口日志，重点包含：

- `TX`: `seq / cmd / axis / value / wait_response`
- `RX`: `seq / rsp / status`
- 对 `CONFIG` 命令会额外打印 `param / raw_value / signed_value`
- `TX-FRAME / RX-FRAME`: 原始协议帧十六进制内容，例如 `aa 07 01 02 ... 55`

如果想直接通过 Web 查看最近的串口历史，可使用：

- `GET /api/comm/diagnostics?limit=100`
- `POST /api/comm/diagnostics/clear`
- 当前默认前端页面右侧也已经挂出了“串口诊断”面板

## Jetson 侧入口

### 1. 系统启动时如何接上串口

`CameraControlSystem._init_comm()` 会创建并连接 `CommManager`：

- 文件：`jetson/main.py`
- 作用：读取配置里的串口端口和波特率，建立 Jetson 到 STM32 的串口连接

随后 `CameraControlSystem._init_web_server()` 会把 `comm_manager` 注入到 Web 层：

- 文件：`jetson/main.py`
- 作用：让 `/api/motion/*` 和 `/api/motion/config` 可以直接下发串口命令

### 2. Web 手动控制链路

当前 Web 侧和 STM32 通信最直接的几个接口：

- `/api/motion/move`
  - 文件：`jetson/src/web/app.py`
  - 命令：`CommandType.POSITION`
  - 行为：按轴逐条发送，默认每条都等待响应
  - 单位：`0.01 度 / 0.01 mm`

- `/api/motion/stop`
  - 文件：`jetson/src/web/app.py`
  - 命令：`CommandType.STOP`
  - 行为：等待响应
  - 说明：这是正常停止，不是急停

- `/api/motion/home`
  - 文件：`jetson/src/web/app.py`
  - 命令：`CommandType.HOME`
  - 行为：等待响应

- `/api/motion/config`
  - 文件：`jetson/src/web/app.py`
  - 命令：`CommandType.CONFIG`
  - 行为：逐项下发，每项等待响应
  - 说明：`CONFIG` 的 32 位负载由 `config_pack_value()` 统一打包

统一发送入口是 `app.py` 里的 `_send_comm_command()`：

- 它兼容旧版和新版 `send_command` 返回值
- 它最终都会走到 `CommManager.send_command()`

### 3. 视觉伺服链路

视觉伺服有三类典型命令：

- `_send_velocity_command()`
  - 文件：`jetson/src/vision/visual_servo/controller.py`
  - 命令：`SET_VELOCITY`
  - 行为：高频闭环控制，`wait_response=False`
  - 单位：`steps/s`

- `_send_stop_command()`
  - 文件：`jetson/src/vision/visual_servo/controller.py`
  - 命令：`STOP`
  - 行为：不等待响应

- `_move_to_position()`
  - 文件：`jetson/src/vision/visual_servo/controller.py`
  - 命令：`MOVE_ABSOLUTE`
  - 行为：逐轴发送，但只等待最后一条响应，减少阻塞
  - 单位：`0.01 度 / 0.01 mm`

这里有一个很关键的现状差异：

- Web 手动移动接口目前发的是 `POSITION`
- 视觉伺服移动接口目前发的是 `MOVE_ABSOLUTE`

STM32 两边都落到 `motion_move_to()`，当前行为上是一致的，但联调时要注意日志里会看到两个不同命令字。

### 4. 心跳与状态探测链路

`CommManager._heartbeat_loop()` 会周期性发送：

- 命令：`STATUS`
- 行为：等待响应
- 目的：在链路长时间空闲时主动探测 STM32 是否还在线

如果超时或收不到匹配响应，会触发连接丢失处理和自动重连逻辑。

## Jetson 侧协议与响应匹配

### 1. 命令编码

`jetson/src/comm/protocol.py` 中的 `encode_command()` 负责将命令编码成：

```text
[HEAD][SEQ][LEN][CMD][DATA][CRC16][TAIL]
```

关键规则：

- `POSITION / CONFIG / SET_VELOCITY / MOVE_ABSOLUTE`
  - 负载格式：`axis(1) + value(4)`
- `HOME`
  - 负载格式：`axis(1)`
- `STOP`
  - 全轴停止：不带负载
  - 单轴停止：带 `axis(1)`
- `STATUS / ESTOP`
  - 无负载

### 2. 同步响应等待

`CommManager.send_command()` 的同步行为：

1. 调用 `encode_command()` 生成帧
2. 分配序列号 `seq`
3. 串口写出整帧
4. 如果 `wait_response=True`，则在 `_read_response_with_seq()` 中等待
5. 只有收到相同 `seq` 的响应才算本次命令成功

这意味着：

- Web 手动控制更偏向“请求-确认”模式
- 视觉伺服速度控制更偏向“尽力发送”模式

### 3. 异步接收现状

`CommManager` 提供了 `start_async_receive()`，但当前主流程并没有主动启动它。

因此当前工程的主要串口交互模式是：

- 以同步 `send_command()` 为主
- 高频视觉伺服命令通常不等响应
- 没有一个默认常驻的“响应订阅器”去消费所有后台响应

这点在联调时很重要，因为它意味着：

- 某些不等待响应的命令，即使 STM32 真的回了 ACK，Jetson 侧默认也不会专门处理那条 ACK
- 如果以后要做更强的在线状态同步，可以考虑显式启用异步接收
- 若已开启 `comm.trace_protocol`，同步等待路径和异步接收路径都会打印 `RX` 日志

## STM32 侧收包与执行

### 1. UART 接收

`stm32/CameraControl/Core/Src/uart_comm.c` 的工作方式：

- `uart_comm_init()` 启动单字节中断接收
- `HAL_UART_RxCpltCallback()` 把字节推入环形缓冲区
- `uart_comm_process()` 在主循环中持续取字节、组帧、解析

### 2. 帧解析

`stm32/CameraControl/Core/Src/protocol.c` 中的 `cmd_parse()` 负责：

- 校验帧头和帧尾
- 校验长度
- 校验 CRC16
- 按命令类型拆出 `axis` 和 `value`

当前解析约定与 Jetson 保持一致：

- `POSITION / MOVE_ABSOLUTE / SET_VELOCITY / CONFIG`
  - `axis(1) + value(4)`
- `HOME`
  - `axis(1)`
- `STOP`
  - 可不带轴；不带时默认 `AXIS_ALL`

### 3. 主循环执行

`stm32/CameraControl/Core/Src/main.c` 中的主链路是：

1. 主循环调用 `uart_comm_process(process_command)`
2. 一旦完整帧解析成功，就进入 `process_command()`
3. `process_command()` 先执行安全检查
4. 再根据命令类型分发到运动控制或配置处理
5. 最后统一调用 `uart_comm_send_response()`

当前主要命令落点如下：

| 命令 | STM32 落点 | 备注 |
| --- | --- | --- |
| `POSITION` | `motion_move_to()` | 位置单位是 `0.01 度 / 0.01 mm` |
| `MOVE_ABSOLUTE` | `motion_move_to()` | 当前与 `POSITION` 共用同一落点 |
| `SET_VELOCITY` | `motion_set_velocity()` | 数值按 `steps/s` 解释 |
| `STOP` | `motion_stop_all()` / `motion_stop_axis()` | 支持全轴或单轴 |
| `HOME` | `motion_home()` | 由轴字段决定归零对象 |
| `CONFIG` | `handle_config_command()` | 先解包参数 ID，再写入配置 |
| `STATUS` | `motion_get_current()` | 回当前三轴位置 |

### 4. 响应发送

`uart_comm_send_response()` 的行为：

- 先把响应帧编码到临时缓冲区
- 如果 DMA 空闲，立即启动发送
- 如果 DMA 正忙，则进入软件队列
- 如果软件队列也满了，当前响应会被丢弃

因此在极高频联调场景下，需要特别注意 ACK 并不是无限排队的。

## 当前命令语义对照

### Web 手动接口

| 来源 | 命令 | 是否等待响应 | 单位 |
| --- | --- | --- | --- |
| `/api/motion/move` | `POSITION` | 是 | `0.01 度 / 0.01 mm` |
| `/api/motion/stop` | `STOP` | 是 | 无 |
| `/api/motion/home` | `HOME` | 是 | 轴编号 |
| `/api/motion/config` | `CONFIG` | 是 | `packed_value` |

### 视觉伺服

| 来源 | 命令 | 是否等待响应 | 单位 |
| --- | --- | --- | --- |
| `_send_velocity_command()` | `SET_VELOCITY` | 否 | `steps/s` |
| `_send_stop_command()` | `STOP` | 否 | 无 |
| `_move_to_position()` | `MOVE_ABSOLUTE` | 仅最后一条等待 | `0.01 度 / 0.01 mm` |

### 通信保活

| 来源 | 命令 | 是否等待响应 | 目的 |
| --- | --- | --- | --- |
| `_heartbeat_loop()` | `STATUS` | 是 | 探测链路是否健康 |

## 最值得注意的联调点

### 1. `POSITION` 与 `MOVE_ABSOLUTE` 同时存在

当前 Jetson 侧会同时使用这两个命令字：

- Web 手动控制发 `POSITION`
- 视觉伺服定位发 `MOVE_ABSOLUTE`

STM32 当前对二者都调用 `motion_move_to()`，所以功能层面没有冲突，但抓包或看日志时要知道这不是重复实现，而是上层来源不同。

### 2. 不是所有命令都会等待 ACK

尤其是视觉伺服速度控制：

- Jetson 侧发送后默认不阻塞
- STM32 仍然会回响应
- 但 Jetson 默认不会专门消费这类后台 ACK

如果后续出现“板子确实动了，但上位机没有显示响应”的现象，这通常不是协议错误，而是当前调用方本来就没等响应。

### 3. `STOP` 与 `ESTOP` 语义不同

- `STOP`: 正常停止当前运动
- `ESTOP`: 进入安全急停状态

现在 Web 的 `/api/motion/stop` 已经改成发送 `STOP`，这与联调预期更一致。

### 4. Rail 限位要按无符号值看

`CONFIG_RAIL_MIN_LIMIT` 和 `CONFIG_RAIL_MAX_LIMIT` 当前按 `uint16` 解释，和 `Pan / Tilt` 的 `int16` 不同。

如果 Jetson 下发 `50000` 这类 `Rail` 限位，STM32 现在会正确按无符号值处理，不会被误判为负数。

## 推荐联调顺序

1. 先用 `flash_firmware.ps1 -DryRun` 或 `build_firmware.ps1` 确认固件产物正常
2. 启动 Jetson 主程序，确认 `CommManager.connect()` 成功
3. 先走 `/api/motion/home` 和 `/api/motion/stop`，确认基础命令与 ACK 正常
4. 再走 `/api/motion/move`，确认位置单位与方向无误
5. 最后再验证视觉伺服的 `SET_VELOCITY` 高频链路

## 若后续还要继续优化

下一步最值得继续做的两件事：

1. 给 Jetson 增加一个显式串口抓包/调试日志开关，把发出的 `seq/cmd/axis/value` 和收到的 `rsp/status/seq` 记录下来
2. 评估是否在主流程里启用 `start_async_receive()`，把“不等待响应但仍然需要观测状态”的场景补完整
