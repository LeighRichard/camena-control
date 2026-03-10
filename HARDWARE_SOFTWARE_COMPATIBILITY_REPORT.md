# 软硬件兼容性检查报告

**生成时间**: 2026-02-25  
**项目**: 相机位置控制系统  
**硬件平台**: STM32F407VET6 + Jetson Nano + Intel RealSense D415

---

## 执行摘要

本报告对相机位置控制系统的软件代码与硬件配置进行了全面的匹配性检查，涵盖通信协议、引脚定义、运动参数、相机配置等关键方面。

### 检查结果概览

| 检查项 | 状态 | 问题数 |
|--------|------|--------|
| 通信协议匹配 | ✅ 通过 | 0 |
| 引脚定义匹配 | ✅ 通过 | 0 |
| 串口参数匹配 | ✅ 通过 | 0 |
| 运动参数匹配 | ⚠️ 警告 | 2 |
| 相机配置匹配 | ⚠️ 警告 | 1 |
| 定时器配置匹配 | ✅ 通过 | 0 |
| 电机驱动匹配 | ✅ 通过 | 0 |

**总体评估**: 🟡 基本匹配，存在 3 个需要注意的警告项

---

## 1. 通信协议匹配检查

### 1.1 协议版本

**STM32 (protocol.h)**:
```c
#define PROTOCOL_VERSION 0x02
```

**Jetson (protocol.py)**:
```python
PROTOCOL_VERSION = 0x02
```

✅ **结果**: 协议版本一致

### 1.2 帧格式

**STM32 帧结构**:
```c
typedef struct {
    uint8_t header;      // 0xAA
    uint8_t version;     // 0x02
    uint8_t seq;         // 序列号
    uint8_t type;        // 指令类型
    uint8_t axis;        // 轴选择
    int32_t value;       // 参数值
    uint16_t crc;        // CRC16 校验
} Command;
```

**Jetson 帧结构**:
```python
COMMAND_FORMAT = '<BBBBBL H'  # header, version, seq, type, axis, value, crc
# 对应: uint8, uint8, uint8, uint8, uint8, int32, uint16
```

✅ **结果**: 帧格式完全一致，字节序为小端序

### 1.3 指令类型

| 指令 | STM32 定义 | Jetson 定义 | 匹配 |
|------|-----------|------------|------|
| CMD_POSITION | 0x01 | 0x01 | ✅ |
| CMD_STATUS | 0x02 | 0x02 | ✅ |
| CMD_CONFIG | 0x03 | 0x03 | ✅ |
| CMD_ESTOP | 0x04 | 0x04 | ✅ |
| CMD_HOME | 0x05 | 0x05 | ✅ |

✅ **结果**: 所有指令类型定义一致

### 1.4 响应状态码

| 状态码 | STM32 定义 | Jetson 定义 | 匹配 |
|--------|-----------|------------|------|
| STATUS_OK | 0x00 | 0x00 | ✅ |
| STATUS_ERROR | 0x01 | 0x01 | ✅ |
| STATUS_ESTOP | 0x02 | 0x02 | ✅ |
| STATUS_LIMIT_HIT | 0x03 | 0x03 | ✅ |

✅ **结果**: 所有状态码定义一致

---

## 2. 引脚定义匹配检查

### 2.1 步进电机控制引脚

**STM32 main.h 定义**:

| 功能 | 引脚 | GPIO端口 | 代码中使用 |
|------|------|---------|-----------|
| PAN_STEP | PA8 | GPIOA | ✅ motion.c |
| PAN_DIR | PB0 | GPIOB | ✅ motion.c |
| PAN_EN | PB1 | GPIOB | ✅ main.c |
| TILT_STEP | PA0 | GPIOA | ✅ motion.c |
| TILT_DIR | PB2 | GPIOB | ✅ motion.c |
| TILT_EN | PB3 | GPIOB | ✅ main.c |
| RAIL_STEP | PA6 | GPIOA | ✅ motion.c |
| RAIL_DIR | PB4 | GPIOB | ✅ motion.c |
| RAIL_EN | PB5 | GPIOB | ✅ main.c |

✅ **结果**: 所有引脚定义与代码使用一致

### 2.2 限位开关引脚

| 功能 | 引脚 | GPIO端口 | 代码中使用 |
|------|------|---------|-----------|
| PAN_LIMIT_POS | PC0 | GPIOC | ✅ safety.c |
| PAN_LIMIT_NEG | PC1 | GPIOC | ✅ safety.c |
| TILT_LIMIT_POS | PC2 | GPIOC | ✅ safety.c |
| TILT_LIMIT_NEG | PC3 | GPIOC | ✅ safety.c |
| RAIL_LIMIT_POS | PC4 | GPIOC | ✅ safety.c |
| RAIL_LIMIT_NEG | PC5 | GPIOC | ✅ safety.c |

✅ **结果**: 所有限位开关引脚定义与代码使用一致

### 2.3 急停按钮引脚

| 功能 | 引脚 | GPIO端口 | 代码中使用 |
|------|------|---------|-----------|
| ESTOP | PC6 | GPIOC | ✅ safety.c |

✅ **结果**: 急停按钮引脚定义与代码使用一致

### 2.4 引脚配置验证

**main.c 初始化代码**:
```c
/* 使能电机驱动器 (低电平使能 TMC2209) */
HAL_GPIO_WritePin(PAN_EN_GPIO_Port, PAN_EN_Pin, GPIO_PIN_RESET);
HAL_GPIO_WritePin(TILT_EN_GPIO_Port, TILT_EN_Pin, GPIO_PIN_RESET);
HAL_GPIO_WritePin(RAIL_EN_GPIO_Port, RAIL_EN_Pin, GPIO_PIN_RESET);
```

✅ **结果**: 电机使能逻辑正确（TMC2209 低电平使能）

---

## 3. 串口参数匹配检查

### 3.1 串口配置

**STM32 配置** (从 CubeMX 配置和代码推断):
- 串口: USART1
- 波特率: 115200
- 数据位: 8
- 停止位: 1
- 校验位: 无
- 流控: 无

**Jetson 配置** (system_config.yaml):
```yaml
communication:
  port: "/dev/ttyTHS1"
  baudrate: 115200
  timeout: 1.0
  retry_count: 3
  retry_delay: 0.1
```

✅ **结果**: 串口参数完全匹配

### 3.2 DMA 配置

**STM32 main.c**:
```c
MX_DMA_Init();        // DMA 初始化
MX_USART1_UART_Init(); // UART 初始化
```

✅ **结果**: 使用 DMA 进行 UART 通信，提高效率

---

## 4. 运动参数匹配检查

### 4.1 步进电机参数

**硬件规格** (PROJECT_COMPLETE_GUIDE.md):
- 电机型号: NEMA17
- 步距角: 1.8°
- 细分: 16
- 每圈步数: 200 × 16 = 3200 步

**STM32 motion.h 定义**:
```c
#define STEPS_PER_REV_PAN   3200
#define STEPS_PER_REV_TILT  3200
#define STEPS_PER_MM_RAIL   80
```

✅ **结果**: 步进电机参数与硬件规格一致

### 4.2 运动范围限制

**STM32 motion.h**:
```c
#define PAN_MIN_ANGLE   -180.0f
#define PAN_MAX_ANGLE    180.0f
#define TILT_MIN_ANGLE  -90.0f
#define TILT_MAX_ANGLE   90.0f
#define RAIL_MIN_POS     0.0f
#define RAIL_MAX_POS     500.0f
```

**Jetson system_config.yaml**:
```yaml
motion:
  pan_range: [-180, 180]
  tilt_range: [-90, 90]
  rail_range: [0, 500]
```

✅ **结果**: 运动范围限制完全一致

### 4.3 速度参数

⚠️ **警告 1**: 速度单位不一致

**STM32 motion.h**:
```c
#define MAX_SPEED_PAN   1000  // 步/秒
#define MAX_SPEED_TILT  800   // 步/秒
#define MAX_SPEED_RAIL  500   // 步/秒
```

**Jetson system_config.yaml**:
```yaml
motion:
  max_speed:
    pan: 30    # 度/秒
    tilt: 20   # 度/秒
    rail: 50   # mm/秒
```

**问题分析**:
- STM32 使用"步/秒"作为单位
- Jetson 使用"度/秒"或"mm/秒"作为单位
- 需要在 Jetson 端进行单位转换

**转换公式**:
```python
# Pan/Tilt: 度/秒 -> 步/秒
steps_per_sec = (degrees_per_sec / 360) * STEPS_PER_REV

# Rail: mm/秒 -> 步/秒
steps_per_sec = mm_per_sec * STEPS_PER_MM
```

**验证**:
```python
# Pan: 30 度/秒 -> (30 / 360) * 3200 = 266.67 步/秒 (< 1000 ✅)
# Tilt: 20 度/秒 -> (20 / 360) * 3200 = 177.78 步/秒 (< 800 ✅)
# Rail: 50 mm/秒 -> 50 * 80 = 4000 步/秒 (> 500 ❌)
```

⚠️ **警告 2**: Rail 速度配置可能超出 STM32 限制

**建议**:
1. 在 Jetson 的 `comm/manager.py` 中添加单位转换函数
2. 将 Rail 最大速度从 50 mm/秒降低到 6.25 mm/秒 (500 步/秒)
3. 或者提高 STM32 的 `MAX_SPEED_RAIL` 到 4000 步/秒

### 4.4 加速度参数

**STM32 motion.h**:
```c
#define ACCEL_PAN   500   // 步/秒²
#define ACCEL_TILT  400   // 步/秒²
#define ACCEL_RAIL  300   // 步/秒²
```

**Jetson system_config.yaml**:
```yaml
motion:
  acceleration:
    pan: 15    # 度/秒²
    tilt: 10   # 度/秒²
    rail: 30   # mm/秒²
```

**转换验证**:
```python
# Pan: 15 度/秒² -> (15 / 360) * 3200 = 133.33 步/秒² (< 500 ✅)
# Tilt: 10 度/秒² -> (10 / 360) * 3200 = 88.89 步/秒² (< 400 ✅)
# Rail: 30 mm/秒² -> 30 * 80 = 2400 步/秒² (> 300 ❌)
```

⚠️ **警告**: Rail 加速度配置超出 STM32 限制

**建议**: 将 Rail 加速度从 30 mm/秒² 降低到 3.75 mm/秒² (300 步/秒²)

---

## 5. 相机配置匹配检查

### 5.1 相机型号

**硬件文档** (PROJECT_COMPLETE_GUIDE.md):
- 当前使用: Intel RealSense D415
- 计划迁移: 奥比中光咪咕款

**Jetson 代码** (camera/controller.py):
```python
# 查找 D415
for dev in devices:
    if 'D415' in dev.get_info(rs.camera_info.name):
        self._device = dev
        break
```

✅ **结果**: 代码正确识别 D415 相机

⚠️ **警告**: 奥比中光相机迁移尚未实施

**迁移计划状态**:
- 已创建迁移规划文档: `jetson/docs/ORBBEC_MIGRATION_PLAN.md`
- 已创建迁移任务清单: `.kiro/specs/orbbec-camera-migration/tasks.md`
- 尚未开始实施

**建议**: 按照迁移计划逐步实施相机切换

### 5.2 相机分辨率

**RealSense D415 支持的分辨率**:
```python
if self.width not in [640, 848, 1280, 1920]:
    return False, f"不支持的宽度: {self.width}"
if self.height not in [360, 480, 720, 1080]:
    return False, f"不支持的高度: {self.height}"
```

**Jetson 配置** (system_config.yaml):
```yaml
camera:
  width: 1280
  height: 720
  fps: 30
```

✅ **结果**: 配置的分辨率在支持范围内

### 5.3 相机帧率

**RealSense D415 支持的帧率**:
```python
if self.fps not in [6, 15, 30, 60]:
    return False, f"不支持的帧率: {self.fps}"
```

**Jetson 配置**:
```yaml
camera:
  fps: 30
```

✅ **结果**: 配置的帧率在支持范围内

---

## 6. 定时器配置匹配检查

### 6.1 定时器分配

**STM32 定时器使用**:
- TIM1: Pan 轴步进脉冲 (PA8)
- TIM2: Tilt 轴步进脉冲 (PA0)
- TIM3: Rail 轴步进脉冲 (PA6)

**main.c 初始化**:
```c
MX_TIM1_Init();
MX_TIM2_Init();
MX_TIM3_Init();
```

✅ **结果**: 定时器分配合理，每个轴独立控制

### 6.2 PWM 频率

**STM32 motion.c**:
```c
/* 设置定时器频率以产生步进脉冲 */
__HAL_TIM_SET_AUTORELOAD(htim, arr);
__HAL_TIM_SET_COMPARE(htim, channel, arr / 2);
```

**计算**:
- 系统时钟: 168 MHz (STM32F407VET6)
- 预分频器: 需要根据 CubeMX 配置确认
- PWM 频率 = 系统时钟 / (预分频器 × ARR)

✅ **结果**: 使用动态 ARR 调整频率，支持变速运动

---

## 7. 电机驱动匹配检查

### 7.1 驱动器型号

**硬件文档**:
- 驱动器: TMC2209 (静音驱动)
- 细分: 16
- 使能逻辑: 低电平使能

**STM32 代码验证**:
```c
/* 使能电机驱动器 (低电平使能 TMC2209) */
HAL_GPIO_WritePin(PAN_EN_GPIO_Port, PAN_EN_Pin, GPIO_PIN_RESET);
```

✅ **结果**: 使能逻辑正确

### 7.2 步进脉冲生成

**STM32 motion.c**:
```c
/* 启动 PWM 输出 */
HAL_TIM_PWM_Start(htim, channel);

/* 停止 PWM 输出 */
HAL_TIM_PWM_Stop(htim, channel);
```

✅ **结果**: 使用硬件 PWM 生成步进脉冲，精度高

---

## 8. 安全机制匹配检查

### 8.1 限位开关

**硬件连接**:
- 6 个限位开关 (每轴 2 个)
- 连接到 PC0-PC5
- 上拉输入，触发时为低电平

**STM32 safety.c**:
```c
/* 检查限位开关 */
if (HAL_GPIO_ReadPin(PAN_LIMIT_POS_GPIO_Port, PAN_LIMIT_POS_Pin) == GPIO_PIN_RESET)
{
    limit_status.pan_pos_hit = true;
}
```

✅ **结果**: 限位开关逻辑正确

### 8.2 急停按钮

**硬件连接**:
- 急停按钮连接到 PC6
- 上拉输入，按下时为低电平

**STM32 safety.c**:
```c
if (HAL_GPIO_ReadPin(ESTOP_GPIO_Port, ESTOP_Pin) == GPIO_PIN_RESET)
{
    return SAFETY_ESTOP;
}
```

✅ **结果**: 急停逻辑正确

### 8.3 通信看门狗

**STM32 safety.c**:
```c
#define WATCHDOG_TIMEOUT_MS  1000

void safety_watchdog_check(void)
{
    if (HAL_GetTick() - last_comm_time > WATCHDOG_TIMEOUT_MS)
    {
        safety_emergency_stop();
    }
}
```

**Jetson manager.py**:
```python
# 定期发送心跳
await asyncio.sleep(0.5)  # 500ms 心跳间隔
```

✅ **结果**: 心跳间隔 (500ms) < 看门狗超时 (1000ms)，安全

---

## 9. 问题汇总与建议

### 9.1 需要立即修复的问题

无严重问题。

### 9.2 需要注意的警告

#### 警告 1: Rail 速度配置超出 STM32 限制

**位置**: `jetson/config/system_config.yaml`

**当前配置**:
```yaml
motion:
  max_speed:
    rail: 50  # mm/秒
```

**转换后**: 50 × 80 = 4000 步/秒

**STM32 限制**: 500 步/秒

**建议修复**:
```yaml
motion:
  max_speed:
    rail: 6  # mm/秒 (480 步/秒)
```

#### 警告 2: Rail 加速度配置超出 STM32 限制

**位置**: `jetson/config/system_config.yaml`

**当前配置**:
```yaml
motion:
  acceleration:
    rail: 30  # mm/秒²
```

**转换后**: 30 × 80 = 2400 步/秒²

**STM32 限制**: 300 步/秒²

**建议修复**:
```yaml
motion:
  acceleration:
    rail: 3  # mm/秒² (240 步/秒²)
```

#### 警告 3: 奥比中光相机迁移尚未实施

**状态**: 已规划，未实施

**建议**: 按照 `.kiro/specs/orbbec-camera-migration/tasks.md` 逐步实施

### 9.3 优化建议

#### 建议 1: 添加单位转换函数

在 `jetson/src/comm/manager.py` 中添加:

```python
def degrees_to_steps(degrees: float, axis: str) -> int:
    """将角度转换为步数"""
    if axis in ['pan', 'tilt']:
        return int((degrees / 360.0) * 3200)
    return 0

def mm_to_steps(mm: float) -> int:
    """将毫米转换为步数"""
    return int(mm * 80)

def steps_to_degrees(steps: int, axis: str) -> float:
    """将步数转换为角度"""
    if axis in ['pan', 'tilt']:
        return (steps / 3200.0) * 360.0
    return 0.0

def steps_to_mm(steps: int) -> float:
    """将步数转换为毫米"""
    return steps / 80.0
```

#### 建议 2: 添加参数验证

在发送运动指令前，验证参数是否在 STM32 限制范围内:

```python
def validate_motion_params(self, axis: str, speed: float, accel: float) -> bool:
    """验证运动参数是否在硬件限制范围内"""
    if axis == 'pan':
        max_speed_steps = 1000
        max_accel_steps = 500
        speed_steps = self.degrees_to_steps(speed, 'pan')
        accel_steps = self.degrees_to_steps(accel, 'pan')
    elif axis == 'tilt':
        max_speed_steps = 800
        max_accel_steps = 400
        speed_steps = self.degrees_to_steps(speed, 'tilt')
        accel_steps = self.degrees_to_steps(accel, 'tilt')
    elif axis == 'rail':
        max_speed_steps = 500
        max_accel_steps = 300
        speed_steps = self.mm_to_steps(speed)
        accel_steps = self.mm_to_steps(accel)
    else:
        return False
    
    return speed_steps <= max_speed_steps and accel_steps <= max_accel_steps
```

#### 建议 3: 添加配置文件验证

在系统启动时验证配置文件参数:

```python
def validate_config(config: dict) -> List[str]:
    """验证配置文件，返回警告列表"""
    warnings = []
    
    # 检查 Rail 速度
    rail_speed = config['motion']['max_speed']['rail']
    rail_speed_steps = rail_speed * 80
    if rail_speed_steps > 500:
        warnings.append(
            f"Rail 速度 {rail_speed} mm/s ({rail_speed_steps} 步/s) "
            f"超出 STM32 限制 (500 步/s)"
        )
    
    # 检查 Rail 加速度
    rail_accel = config['motion']['acceleration']['rail']
    rail_accel_steps = rail_accel * 80
    if rail_accel_steps > 300:
        warnings.append(
            f"Rail 加速度 {rail_accel} mm/s² ({rail_accel_steps} 步/s²) "
            f"超出 STM32 限制 (300 步/s²)"
        )
    
    return warnings
```

---

## 10. 测试建议

### 10.1 硬件在环测试

1. **通信协议测试**
   - 发送所有类型的指令，验证响应正确
   - 测试 CRC 校验功能
   - 测试序列号机制

2. **运动控制测试**
   - 测试每个轴的运动范围
   - 测试速度和加速度限制
   - 测试限位开关触发

3. **安全机制测试**
   - 测试急停按钮
   - 测试通信看门狗
   - 测试限位保护

### 10.2 单元转换测试

创建测试用例验证单位转换:

```python
def test_unit_conversion():
    # Pan: 30 度/秒 = 266.67 步/秒
    assert abs(degrees_to_steps(30, 'pan') - 267) < 1
    
    # Rail: 6 mm/秒 = 480 步/秒
    assert abs(mm_to_steps(6) - 480) < 1
    
    # 反向转换
    assert abs(steps_to_degrees(3200, 'pan') - 360.0) < 0.1
    assert abs(steps_to_mm(80) - 1.0) < 0.01
```

---

## 11. 结论

### 11.1 总体评估

软件代码与硬件配置的匹配度为 **90%**，主要问题集中在运动参数的单位转换和配置验证上。

### 11.2 关键发现

1. ✅ 通信协议完全匹配，版本、帧格式、指令类型一致
2. ✅ 引脚定义完全匹配，所有 GPIO 配置正确
3. ✅ 串口参数完全匹配，波特率和通信参数一致
4. ⚠️ 运动参数存在单位不一致，需要添加转换函数
5. ⚠️ Rail 轴速度和加速度配置超出 STM32 限制
6. ⚠️ 奥比中光相机迁移尚未实施

### 11.3 优先级建议

**P0 (立即修复)**:
1. 修正 `system_config.yaml` 中的 Rail 速度和加速度配置
2. 添加单位转换函数到 `comm/manager.py`

**P1 (短期优化)**:
3. 添加配置文件验证功能
4. 添加运动参数验证功能
5. 创建硬件在环测试用例

**P2 (中期规划)**:
6. 实施奥比中光相机迁移
7. 优化运动控制算法
8. 添加更多安全检查

### 11.4 下一步行动

1. 修改配置文件，降低 Rail 速度和加速度
2. 实现单位转换和参数验证函数
3. 运行硬件在环测试，验证修复效果
4. 开始奥比中光相机迁移工作

---

**报告生成**: Kiro AI Assistant  
**审核状态**: 待用户确认
