# 设计文档

## 概述

本系统采用双控制器架构：NVIDIA Jetson Nano 作为主控制器负责相机控制、深度学习推理和上位机逻辑，STM32F407 作为运动控制器负责电机驱动和实时运动控制。两者通过 UART 串口通信协调工作。系统使用 YOLOv5/YOLOv8 进行农作物目标检测，利用 Jetson Nano 的 GPU 加速实现实时推理。

## 硬件选型与电路设计

### 核心控制器

| 组件 | 型号 | 规格 | 选型理由 |
|------|------|------|----------|
| 主控制器 | **NVIDIA Jetson Nano Developer Kit B01** | ARM Cortex-A57 四核 1.43GHz, 4GB RAM, 128核 Maxwell GPU | GPU 加速深度学习推理，支持 YOLO 等模型实时检测农作物 |
| 运动控制器 | **STM32F407VET6** | ARM Cortex-M4 168MHz, 512KB Flash, 192KB RAM | 多路高级定时器，支持编码器接口，浮点运算单元适合 PID 计算 |

### 相机模块

| 组件 | 型号 | 规格 |
|------|------|------|
| 深度相机 | **Intel RealSense D415** | RGB 1920×1080@30fps, 深度 1280×720@90fps, USB 3.0 |

### 运动机构

| 组件 | 推荐型号 | 规格 | 说明 |
|------|----------|------|------|
| 云台电机 (Pan) | **42 步进电机 (NEMA 17)** | 1.8°步距角, 1.5A, 0.4N·m | 配合 16 细分可达 0.1125° 精度 |
| 云台电机 (Tilt) | **42 步进电机 (NEMA 17)** | 1.8°步距角, 1.5A, 0.4N·m | 同上 |
| 滑轨电机 | **42 步进电机 + T8 丝杆** | 导程 2mm, 行程 300mm | 16 细分下精度 0.00625mm |
| 电机驱动 | **TMC2209** × 3 | 静音驱动, 最高 256 细分, 2A 峰值电流 | StealthChop 静音模式，支持 UART 配置 |
| 限位开关 | **机械微动开关** × 6 | 常开触点, 5A 250VAC | 每轴正负限位各 1 个 |
| 急停按钮 | **蘑菇头急停开关** × 1 | 常闭触点, 自锁式 | 硬件级急停 |

### 电源系统

| 组件 | 规格 | 用途 |
|------|------|------|
| 主电源 | **24V 5A 开关电源** (120W) | 步进电机供电 |
| Jetson Nano 电源 | **5V 4A DC 电源** (5.5×2.1mm 桶形接口) | Jetson Nano 独立供电，必须使用桶形接口 |
| STM32 供电 | **3.3V LDO** (AMS1117-3.3) | 从 5V 降压，板载 |

### 电路框图

```
                         ┌─────────────────────────────────────────────────────┐
                         │                   AC 220V 输入                       │
                         └──────────────────────┬──────────────────────────────┘
                                                │
                    ┌───────────────────────────┼───────────────────────────┐
                    │                           │                           │
         ┌──────────▼──────────┐     ┌──────────▼──────────┐               │
         │  24V 5A 开关电源     │     │  5V 4A DC 电源      │               │
         │  (电机供电)          │     │  (Jetson 供电)      │               │
         └──────────┬──────────┘     └──────────┬──────────┘               │
                    │                           │                           │
                    │                ┌──────────▼──────────┐               │
                    │                │  Jetson Nano B01    │               │
┌────────────────┐  │                │  4GB RAM, 128 CUDA  │               │
│  Intel D415   │◄─┼────────────────►│                     │               │
│  深度相机      │  │     USB 3.0    │  GPIO: UART TX/RX   │               │
└────────────────┘  │                └──────────┬──────────┘               │
                    │                           │ UART                      │
                    │                ┌──────────▼──────────┐               │
                    │                │  STM32F407VET6      │◄──────────────┘
                    │                │                     │    (5V→3.3V LDO)
                    │                │  TIM1: Pan PWM      │
                    │                │  TIM2: Tilt PWM     │
                    │                │  TIM3: Rail PWM     │
                    │                │  GPIO: 限位开关输入  │
                    │                │  GPIO: 急停按钮      │
                    │                └──┬─────┬─────┬──────┘
                    │                   │     │     │
                    │          ┌────────▼─┐ ┌─▼───┐ ┌▼────────┐
                    │          │ TMC2209  │ │TMC  │ │ TMC2209 │
                    │          │ (Pan)    │ │2209 │ │ (Rail)  │
                    │          └────┬─────┘ └──┬──┘ └────┬────┘
                    │               │          │         │
                    └───────────────┼──────────┼─────────┘
                         24V 电机供电│          │
                    ┌───────────────▼──────────▼─────────┐
                    │           步进电机 × 3              │
                    │     (Pan)    (Tilt)    (Rail)      │
                    └────────────────────────────────────┘
```

### 关键接线表

#### Jetson Nano ↔ STM32 (UART 通信)

| Jetson Nano GPIO | STM32 引脚 | 功能 |
|------------------|------------|------|
| Pin 8 (TXD1) | PA10 (USART1_RX) | Jetson 发送 → STM32 接收 |
| Pin 10 (RXD1) | PA9 (USART1_TX) | STM32 发送 → Jetson 接收 |
| Pin 6 (GND) | GND | 共地 |

#### STM32 ↔ TMC2209 电机驱动

| 轴 | STEP 引脚 | DIR 引脚 | EN 引脚 | 定时器 |
|----|-----------|----------|---------|--------|
| Pan | PA8 (TIM1_CH1) | PB0 | PB1 | TIM1 |
| Tilt | PA0 (TIM2_CH1) | PB2 | PB3 | TIM2 |
| Rail | PA6 (TIM3_CH1) | PB4 | PB5 | TIM3 |

#### 限位开关与急停

| 功能 | STM32 引脚 | 说明 |
|------|------------|------|
| Pan 正限位 | PC0 | 上拉输入，触发低电平 |
| Pan 负限位 | PC1 | 上拉输入，触发低电平 |
| Tilt 正限位 | PC2 | 上拉输入，触发低电平 |
| Tilt 负限位 | PC3 | 上拉输入，触发低电平 |
| Rail 正限位 | PC4 | 上拉输入，触发低电平 |
| Rail 负限位 | PC5 | 上拉输入，触发低电平 |
| 急停按钮 | PC6 | 上拉输入，常闭触点，断开触发急停 |

### 物料清单 (BOM)

| 序号 | 名称 | 型号/规格 | 数量 | 备注 |
|------|------|-----------|------|------|
| 1 | Jetson Nano | Developer Kit B01 4GB | 1 | 含载板 |
| 2 | Jetson 散热风扇 | 4010 5V 风扇 | 1 | 必备，防止降频 |
| 3 | Jetson 电源 | 5V 4A DC (5.5×2.1mm) | 1 | 必须桶形接口供电 |
| 4 | microSD 卡 | SanDisk 64GB UHS-I U3 | 1 | 系统存储 |
| 5 | STM32 开发板 | STM32F407VET6 核心板 | 1 | 建议带底板 |
| 6 | 深度相机 | Intel RealSense D415 | 1 | 已有 |
| 7 | 步进电机 | NEMA 17 42 步进电机 | 3 | 1.5A, 0.4N·m |
| 8 | 电机驱动 | TMC2209 静音驱动模块 | 3 | |
| 9 | 开关电源 | 24V 5A 开关电源 | 1 | |
| 10 | 限位开关 | 机械微动开关 | 6 | |
| 11 | 急停按钮 | 蘑菇头急停开关 | 1 | 自锁式 |
| 12 | T8 丝杆滑台 | 行程 300mm | 1 | 含步进电机座 |
| 13 | 云台支架 | 二轴云台机械结构 | 1 | 可 3D 打印或购买 |
| 14 | 杜邦线/端子线 | 若干 | - | |
| 15 | PCB 转接板 | 可选 | 1 | 整合接线 |

### 深度学习推理配置

| 项目 | 推荐配置 |
|------|----------|
| 推理框架 | **TensorRT** (NVIDIA 优化) |
| 检测模型 | **YOLOv5s / YOLOv8n** (轻量版) |
| 输入分辨率 | 640×480 或 416×416 |
| 预期帧率 | 15-25 FPS |
| 训练平台 | PC (GPU) 训练，导出 ONNX → TensorRT |

## 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        用户层                                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │  Web 界面   │  │  REST API   │  │  配置文件   │              │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘              │
└─────────┼────────────────┼────────────────┼─────────────────────┘
          │                │                │
┌─────────▼────────────────▼────────────────▼─────────────────────┐
│                    主控制器 (Jetson Nano B01)                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │ 相机控制器  │  │ 任务调度器  │  │ 状态管理器  │              │
│  │ CameraCtrl  │  │ TaskScheduler│ │ StateManager│              │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘              │
│         │                │                │                      │
│  ┌──────▼────────────────▼────────────────▼──────┐              │
│  │              通信管理器 (CommManager)          │              │
│  └──────────────────────┬────────────────────────┘              │
└─────────────────────────┼───────────────────────────────────────┘
                          │ UART (115200 bps)
┌─────────────────────────▼───────────────────────────────────────┐
│                   运动控制器 (STM32F4)                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │ 指令解析器  │  │ 运动规划器  │  │ 安全监控器  │              │
│  │ CmdParser   │  │ MotionPlanner│ │ SafetyMonitor│             │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘              │
│         │                │                │                      │
│  ┌──────▼────────────────▼────────────────▼──────┐              │
│  │              电机驱动层 (MotorDriver)          │              │
│  └──────────────────────┬────────────────────────┘              │
└─────────────────────────┼───────────────────────────────────────┘
                          │ PWM / 步进脉冲
┌─────────────────────────▼───────────────────────────────────────┐
│                       执行机构                                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │  云台电机   │  │  滑轨电机   │  │  限位开关   │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
└─────────────────────────────────────────────────────────────────┘
```

## 组件与接口

### 主控制器组件 (Jetson Nano - Python)

#### CameraController
负责 D415 相机的控制和图像采集，处理滚动快门特性。

```python
class CameraController:
    def initialize() -> Result[CameraStatus, Error]
    def capture(wait_frames: int = 5) -> Result[ImagePair, Error]  # 等待多帧稳定
    def configure(config: CameraConfig) -> Result[None, Error]
    def get_status() -> CameraStatus
    def auto_exposure_adjust() -> Result[CameraConfig, Error]  # 自动调整曝光
    def is_motion_stable() -> bool  # 检查是否可以拍摄
```

#### ImageProcessor
负责图像质量评估和目标识别。

```python
class ImageProcessor:
    def detect_target(image: np.ndarray, config: DetectionConfig) -> Result[TargetInfo, Error]
    def calculate_position_adjustment(target: TargetInfo, current_pos: Position) -> PositionAdjustment
    def evaluate_image_quality(image: np.ndarray) -> QualityMetrics
    def suggest_exposure_params(metrics: QualityMetrics) -> CameraConfig
```

#### TaskScheduler
负责自动拍摄任务的调度和执行。

```python
class TaskScheduler:
    def load_path(path_config: PathConfig) -> Result[None, Error]
    def start_auto_capture() -> Result[TaskId, Error]
    def pause() -> Result[None, Error]
    def resume() -> Result[None, Error]
    def get_progress() -> TaskProgress
```

#### CommManager
负责与 STM32 的通信。

```python
class CommManager:
    def send_command(cmd: Command) -> Result[Response, Error]
    def get_position() -> Position
    def set_position(target: Position) -> Result[None, Error]
    def emergency_stop() -> Result[None, Error]
```

### 运动控制器组件 (STM32 - C)

#### CmdParser
解析来自主控制器的指令。

```c
typedef struct {
    CommandType type;
    uint8_t axis;
    int32_t value;
    uint16_t checksum;
} Command;

ParseResult cmd_parse(uint8_t* buffer, size_t len, Command* out);
size_t cmd_encode(Command* cmd, uint8_t* buffer);
```

#### MotionPlanner
规划和执行运动轨迹，使用 PID 控制和 S 曲线速度规划。

```c
typedef struct {
    int32_t pan_angle;    // 0.01度为单位
    int32_t tilt_angle;   // 0.01度为单位
    int32_t rail_pos;     // 0.01mm为单位
} Position;

typedef struct {
    float kp;             // 比例系数
    float ki;             // 积分系数
    float kd;             // 微分系数
} PIDParams;

typedef struct {
    float max_velocity;   // 最大速度
    float max_accel;      // 最大加速度
    float jerk;           // 加加速度（S曲线参数）
} MotionProfile;

// PID 控制器
float pid_compute(PIDParams* pid, float setpoint, float current, float dt);
void pid_reset(PIDParams* pid);

// S曲线速度规划
void motion_plan_s_curve(Position* start, Position* end, MotionProfile* profile);
void motion_move_to(Position* target);
void motion_stop(void);
Position motion_get_current(void);
bool motion_is_complete(void);
bool motion_is_stable(void);  // 检查振动是否衰减
```

#### SafetyMonitor
监控安全状态和处理异常。

```c
typedef enum {
    SAFETY_OK,
    SAFETY_LIMIT_HIT,
    SAFETY_OVERCURRENT,
    SAFETY_OVERHEAT,
    SAFETY_COMM_LOST
} SafetyStatus;

SafetyStatus safety_check(void);
void safety_emergency_stop(void);
```

## 数据模型

### 通信协议帧格式

```
┌──────┬──────┬──────┬──────────┬──────────┬──────┐
│ HEAD │ LEN  │ CMD  │  DATA    │ CHECKSUM │ TAIL │
│ 0xAA │ 1B   │ 1B   │  N Bytes │   2B     │ 0x55 │
└──────┴──────┴──────┴──────────┴──────────┴──────┘
```

### 指令类型定义

| CMD  | 名称           | DATA 格式                    |
|------|----------------|------------------------------|
| 0x01 | 位置控制       | axis(1B) + target(4B)        |
| 0x02 | 状态查询       | 无                           |
| 0x03 | 参数配置       | param_id(1B) + value(4B)     |
| 0x04 | 急停           | 无                           |
| 0x05 | 归零           | axis(1B)                     |

### 响应类型定义

| CMD  | 名称           | DATA 格式                    |
|------|----------------|------------------------------|
| 0x81 | 位置响应       | status(1B)                   |
| 0x82 | 状态响应       | pan(4B)+tilt(4B)+rail(4B)+status(1B) |
| 0x83 | 配置响应       | status(1B)                   |
| 0x84 | 急停响应       | status(1B)                   |
| 0x85 | 归零响应       | status(1B)                   |

### 图像数据结构

```python
@dataclass
class ImagePair:
    rgb: np.ndarray          # RGB 图像 (H, W, 3)
    depth: np.ndarray        # 深度图像 (H, W)
    timestamp: float         # 采集时间戳
    position: Position       # 采集时的相机位置

@dataclass
class CameraConfig:
    width: int = 1280
    height: int = 720
    fps: int = 30
    exposure: int = -1       # -1 表示自动曝光
    brightness: int = 0      # 亮度调节 (-64 to 64)
    contrast: int = 50       # 对比度 (0 to 100)
    gain: int = 16           # 增益 (0 to 128)
    white_balance: int = -1  # -1 表示自动白平衡
    auto_exposure: bool = True
    
@dataclass
class QualityMetrics:
    brightness_score: float  # 亮度评分 (0-1)
    contrast_score: float    # 对比度评分 (0-1)
    sharpness_score: float   # 清晰度评分 (0-1)
    is_acceptable: bool      # 是否达到可接受质量

@dataclass
class TargetInfo:
    center_x: float          # 目标中心 X (像素)
    center_y: float          # 目标中心 Y (像素)
    distance: float          # 目标距离 (mm，来自深度图)
    bounding_box: Tuple[int, int, int, int]  # (x, y, w, h)
    confidence: float        # 检测置信度

@dataclass
class DetectionConfig:
    target_type: str         # 目标类型 (e.g., "aruco", "object", "face")
    threshold: float = 0.5   # 检测阈值
    roi: Optional[Tuple[int, int, int, int]] = None  # 感兴趣区域
```

### 路径配置

```python
@dataclass
class PathPoint:
    pan: float               # 水平角度 (度)
    tilt: float              # 俯仰角度 (度)
    rail: float              # 滑轨位置 (mm)
    settle_time: float = 0.5 # 振动衰减等待时间 (秒)
    capture_frames: int = 5  # 滚动快门稳定帧数

@dataclass
class PathConfig:
    points: List[PathPoint]
    name: str
    description: str = ""

@dataclass 
class MotionConfig:
    pid_pan: Tuple[float, float, float]   # (Kp, Ki, Kd) for pan
    pid_tilt: Tuple[float, float, float]  # (Kp, Ki, Kd) for tilt
    pid_rail: Tuple[float, float, float]  # (Kp, Ki, Kd) for rail
    max_velocity: float = 30.0            # 度/秒 或 mm/秒
    max_acceleration: float = 50.0        # 度/秒² 或 mm/秒²
    jerk_limit: float = 100.0             # S曲线加加速度限制
```

## 正确性属性

*正确性属性是指在系统所有有效执行中都应该保持为真的特征或行为。属性作为人类可读规范和机器可验证正确性保证之间的桥梁。*

### Property 1: 通信协议编解码往返一致性
*对于任意* 有效的 Command 对象，编码后再解码应该得到等价的 Command 对象。
**验证需求: 3.3, 3.5**

### Property 2: 校验和完整性验证
*对于任意* 通信帧数据，如果数据被篡改，校验和验证应该失败。
**验证需求: 3.3**

### Property 3: 位置指令边界检查
*对于任意* 位置指令，如果目标位置超出限位范围，系统应该拒绝执行并返回错误。
**验证需求: 2.6**

### Property 4: 路径配置解析一致性
*对于任意* 有效的路径配置，解析后再序列化应该得到等价的配置。
**验证需求: 4.1**

### Property 5: 自动拍摄路径执行顺序
*对于任意* 包含 N 个路径点的自动拍摄任务，系统应该按顺序访问所有 N 个点，且每个点只访问一次。
**验证需求: 4.2, 4.6**

### Property 6: 状态变化传播完整性
*对于任意* 系统状态变化事件，状态管理器应该记录该变化并通知所有订阅者。
**验证需求: 5.2, 5.5**

### Property 7: 通信超时看门狗
*对于任意* 通信中断场景，如果中断时间超过 1 秒，运动控制器应该自动停止所有运动。
**验证需求: 6.5**

### Property 8: 相机配置持久化一致性
*对于任意* 有效的相机配置，设置后再获取应该得到相同的配置值。
**验证需求: 1.6**

### Property 9: PID 控制输出有界性
*对于任意* PID 控制器状态和输入误差，输出值应该在预设的安全范围内。
**验证需求: 2.1, 2.2**

### Property 10: S曲线速度规划连续性
*对于任意* 起点和终点位置，S曲线规划生成的速度曲线应该是连续的，且加速度变化平滑。
**验证需求: 2.3**

### Property 11: 拍摄时序约束
*对于任意* 自动拍摄序列，每次拍摄必须在运动完全停止且振动衰减后才能开始，拍摄完成后才能开始下一次运动。
**验证需求: 4.3, 4.4, 4.5**

### Property 12: 目标位置计算一致性
*对于任意* 目标检测结果和当前相机位置，计算的位置调整量应该使目标更接近画面中心。
**验证需求: 7.2, 7.3**

## 错误处理

### 错误分类

| 错误级别 | 描述 | 处理方式 |
|----------|------|----------|
| FATAL | 系统无法继续运行 | 停止所有操作，等待重启 |
| ERROR | 当前操作失败 | 停止当前操作，等待用户处理 |
| WARNING | 可能影响结果 | 记录日志，继续执行 |
| INFO | 一般信息 | 仅记录日志 |

### 错误恢复策略

1. **相机连接失败**: 重试 3 次，每次间隔 1 秒，失败后报告错误
2. **通信超时**: 重试 3 次，失败后触发急停
3. **限位触发**: 立即停止，等待用户手动复位
4. **过流/过热**: 停止运动，等待冷却后可恢复

## 测试策略

### 单元测试
- 通信协议编解码测试
- 路径配置解析测试
- 状态机转换测试
- 边界条件测试

### 属性测试
使用 Hypothesis (Python) 和自定义测试框架 (C) 进行属性测试：
- 每个属性测试运行至少 100 次迭代
- 测试标注格式: **Feature: camera-position-control, Property N: [属性描述]**

### 集成测试
- Jetson Nano 与 STM32 通信测试
- 相机采集流程测试
- 自动拍摄完整流程测试

### 硬件在环测试
- 电机运动精度测试
- 限位开关响应测试
- 急停功能测试
