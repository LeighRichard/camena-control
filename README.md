# camena-control

基于 Jetson Nano + STM32 的相机位置控制与自动拍摄系统。

这个仓库把上位视觉、串口协议、三轴运动控制和多端界面放在同一个工程里，目标是支持相机自动定位、目标检测、人脸识别/注册、人脸跟踪视觉伺服，以及后续的自动拍摄任务编排。

## 当前版本

- 当前标签：`v0.1.0`
- 发布说明：[`docs/releases/v0.1.0.md`](docs/releases/v0.1.0.md)

## 仓库结构

| 目录 | 说明 |
| --- | --- |
| `jetson/` | Jetson Nano 主控端，负责相机、视觉推理、人脸识别、视觉伺服、Web API/Web UI、串口通信 |
| `stm32/` | STM32F407 运动控制固件，负责三轴电机控制、协议解析、看门狗与底层执行 |
| `desktop_app/` | Electron 桌面端 |
| `mobile_app/` | 移动端工程骨架与资源 |
| `docs/` | 联调与发布文档 |
| `main.py` | 仓库根入口脚本 |

## 核心能力

- 三轴运动控制：支持 `POSITION`、`MOVE_ABSOLUTE`、`SET_VELOCITY`、`STOP`、`HOME`
- STM32/Jetson 串口协议：统一 `SEQ + LEN + CMD + DATA + CRC16` 帧格式
- Jetson 视觉链路：目标检测、人脸识别、人脸注册、视觉伺服、人脸跟踪
- TensorRT 检测接入：Jetson 启动时自动尝试加载 `.engine/.trt` 模型，并在 Web 状态中暴露当前推理引擎
- Web API 与 Web UI：支持运动控制、相机预览、检测状态、人脸注册/跟踪、串口诊断
- 串口联调工具：支持协议语义日志、原始十六进制帧日志、最近 N 条通信历史查看与清空

## 推荐入口

- Jetson 主程序推荐使用：`jetson/main.py`
- STM32 工程入口：`stm32/CameraControl/`

## 快速开始

### 1. Jetson 端

1. 检查 `jetson/config/system_config.yaml`
2. 准备相机、串口和模型文件
3. 启动：

```bash
cd jetson
python main.py --config config/system_config.yaml
```

说明：

- 当前默认检测模型路径是 `models/yolov5s.engine`
- 启动时会尝试加载 TensorRT 检测模型
- Web 状态接口和前端页面会显示检测器是否已加载、是否处于模拟模式、当前推理引擎以及错误原因

### 2. STM32 固件

推荐直接使用仓库里已经整理好的脚本：

```powershell
cd stm32/CameraControl
.\build_firmware.ps1 -Preset Debug
.\flash_firmware.ps1 -Preset Debug -DryRun
```

构建完成后会生成：

- `CameraControl.elf`
- `CameraControl.hex`
- `CameraControl.bin`

更详细的固件说明见：[`stm32/README.md`](stm32/README.md)

## 关键文档

- STM32 固件说明：[`stm32/README.md`](stm32/README.md)
- Jetson 与 STM32 通信链路：[`docs/jetson_stm32_comm_flow.md`](docs/jetson_stm32_comm_flow.md)
- `v0.1.0` 发布说明：[`docs/releases/v0.1.0.md`](docs/releases/v0.1.0.md)

## 当前状态

这个版本已经补齐了几块关键能力：

- STM32 端协议参数、注释和构建/烧录流程更适合联调
- Jetson 端 `CONFIG` 下发链路已经接通
- Web 端已经能查看串口诊断和检测器 TensorRT 运行状态
- 目标检测启动时会主动加载模型，而不是只实例化检测器对象

## 已知说明

- 硬件限位开关和硬件急停输入当前默认未启用，但串口急停、看门狗和软限位仍然有效
- 目标检测需要实际模型文件和 TensorRT 运行环境
- 人脸识别能运行到什么后端，取决于 `insightface` / `face_recognition` 等依赖是否可用

## 适合谁用

- 想在 Jetson Nano 上做带运动控制的视觉项目
- 需要把 STM32 固件和上位视觉控制放在一个仓库里联调
- 需要人脸注册、视觉伺服和串口诊断能力的相机控制系统
