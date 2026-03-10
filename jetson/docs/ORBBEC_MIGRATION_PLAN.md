# 奥比中光咪咕款深度相机迁移方案

**文档版本**: 1.0  
**创建日期**: 2026-01-15  
**目标相机**: 奥比中光咪咕款 (Orbbec Astra Mini / Gemini 系列)  
**原相机**: Intel RealSense D415

---

## 📋 目录

1. [相机对比分析](#相机对比分析)
2. [迁移策略](#迁移策略)
3. [技术实施方案](#技术实施方案)
4. [迁移任务清单](#迁移任务清单)
5. [测试验证计划](#测试验证计划)
6. [风险评估](#风险评估)

---

## 相机对比分析

### 奥比中光咪咕款技术规格

| 参数 | 奥比中光咪咕款 | Intel RealSense D415 | 备注 |
|------|---------------|---------------------|------|
| **深度技术** | 结构光 | 主动立体视觉 | 技术原理不同 |
| **深度分辨率** | 640×480 @ 30fps | 1280×720 @ 30fps | 分辨率降低 |
| **彩色分辨率** | 1920×1080 @ 30fps | 1920×1080 @ 30fps | 相同 |
| **深度范围** | 0.6m - 8m | 0.3m - 10m | 最小距离增加 |
| **深度精度** | ±2mm @ 1m | ±2mm @ 1m | 相近 |
| **视场角 (FOV)** | H: 60°, V: 49.5° | H: 65°, V: 40° | 略有差异 |
| **接口** | USB 2.0/3.0 | USB 3.0 | 兼容性更好 |
| **功耗** | ~2W | ~3.5W | 更低功耗 |
| **SDK** | Orbbec SDK / OpenNI2 | librealsense2 | SDK 不同 |
| **价格** | ~¥500-800 | ~¥1500-2000 | 更经济 |

### 优势分析

**奥比中光咪咕款优势**:
1. ✅ **成本更低** - 价格约为 D415 的 1/3
2. ✅ **功耗更低** - 适合移动应用
3. ✅ **国产化** - 供应链更稳定，技术支持更便捷
4. ✅ **USB 2.0 兼容** - 对硬件要求更低
5. ✅ **结构光技术** - 室内环境下更稳定

**需要注意的差异**:
1. ⚠️ **深度分辨率降低** - 从 1280×720 降至 640×480
2. ⚠️ **最小工作距离增加** - 从 0.3m 增至 0.6m
3. ⚠️ **SDK 不同** - 需要适配 Orbbec SDK
4. ⚠️ **室外性能** - 结构光在强光下性能下降

---

## 迁移策略

### 总体策略

采用**渐进式迁移**策略，分三个阶段实施：

```
阶段 1: 驱动适配层 (1-2 天)
  └─ 创建统一相机接口
  └─ 实现 Orbbec 驱动适配器
  └─ 保持 RealSense 兼容性

阶段 2: 参数调优 (2-3 天)
  └─ 调整深度处理参数
  └─ 优化视觉伺服算法
  └─ 更新配置文件

阶段 3: 测试验证 (1-2 天)
  └─ 功能测试
  └─ 性能测试
  └─ 集成测试
```

### 设计原则

1. **抽象化设计** - 创建统一的相机接口，支持多种相机
2. **向后兼容** - 保留 RealSense 支持，允许用户选择
3. **配置驱动** - 通过配置文件切换相机类型
4. **最小改动** - 尽量减少对现有代码的修改

---

## 技术实施方案

### 1. 架构设计

#### 1.1 统一相机接口

创建抽象基类 `BaseCameraController`，定义统一接口：

```python
# jetson/src/camera/base_controller.py

from abc import ABC, abstractmethod
from typing import Optional, Tuple
from dataclasses import dataclass
import numpy as np

class BaseCameraController(ABC):
    """相机控制器抽象基类"""
    
    @abstractmethod
    def initialize(self) -> Tuple[bool, str]:
        """初始化相机"""
        pass
    
    @abstractmethod
    def capture(self, wait_frames: int = None, 
                position: Tuple[float, float, float] = None) -> Tuple[Optional[ImagePair], str]:
        """采集图像"""
        pass
    
    @abstractmethod
    def configure(self, config: CameraConfig) -> Tuple[bool, str]:
        """配置相机参数"""
        pass
    
    @abstractmethod
    def get_intrinsics(self) -> Optional[dict]:
        """获取相机内参"""
        pass
    
    @abstractmethod
    def close(self):
        """关闭相机"""
        pass
```

#### 1.2 Orbbec 适配器实现

```python
# jetson/src/camera/orbbec_controller.py

from pyorbbecsdk import Pipeline, Config, OBSensorType, OBFormat
from .base_controller import BaseCameraController

class OrbbecController(BaseCameraController):
    """奥比中光相机控制器"""
    
    def __init__(self):
        self._pipeline = None
        self._config = None
        self._device = None
        # ... 初始化代码
    
    def initialize(self) -> Tuple[bool, str]:
        """初始化奥比中光相机"""
        try:
            # 创建 Pipeline
            self._pipeline = Pipeline()
            
            # 获取设备
            device_list = self._pipeline.get_device_list()
            if device_list.get_count() == 0:
                return False, "未找到奥比中光设备"
            
            self._device = device_list.get_device(0)
            
            # 配置流
            self._config = Config()
            
            # 彩色流: 1920×1080 @ 30fps
            color_profile = self._pipeline.get_stream_profile_list(
                OBSensorType.COLOR_SENSOR
            ).get_video_stream_profile(1920, 1080, OBFormat.RGB, 30)
            self._config.enable_stream(color_profile)
            
            # 深度流: 640×480 @ 30fps
            depth_profile = self._pipeline.get_stream_profile_list(
                OBSensorType.DEPTH_SENSOR
            ).get_video_stream_profile(640, 480, OBFormat.Y16, 30)
            self._config.enable_stream(depth_profile)
            
            # 启用对齐（深度对齐到彩色）
            self._config.set_align_mode(AlignMode.ALIGN_D2C_HW_MODE)
            
            # 启动 Pipeline
            self._pipeline.start(self._config)
            
            return True, ""
            
        except Exception as e:
            return False, str(e)
```

#### 1.3 工厂模式创建相机

```python
# jetson/src/camera/factory.py

from typing import Optional
from .base_controller import BaseCameraController
from .controller import CameraController  # RealSense
from .orbbec_controller import OrbbecController

class CameraFactory:
    """相机工厂类"""
    
    @staticmethod
    def create_camera(camera_type: str = "auto") -> Optional[BaseCameraController]:
        """
        创建相机控制器
        
        Args:
            camera_type: 相机类型 ("realsense", "orbbec", "auto")
            
        Returns:
            相机控制器实例
        """
        if camera_type == "realsense":
            return CameraController()
        
        elif camera_type == "orbbec":
            return OrbbecController()
        
        elif camera_type == "auto":
            # 自动检测
            # 优先尝试 Orbbec
            try:
                controller = OrbbecController()
                success, _ = controller.initialize()
                if success:
                    return controller
                controller.close()
            except:
                pass
            
            # 尝试 RealSense
            try:
                controller = CameraController()
                success, _ = controller.initialize()
                if success:
                    return controller
                controller.close()
            except:
                pass
            
            return None
        
        else:
            raise ValueError(f"不支持的相机类型: {camera_type}")
```

### 2. SDK 依赖管理

#### 2.1 安装 Orbbec SDK

```bash
# 方式 1: 使用 pip 安装 (推荐)
pip install pyorbbecsdk

# 方式 2: 从源码编译
git clone https://github.com/orbbec/pyorbbecsdk.git
cd pyorbbecsdk
pip install .
```

#### 2.2 更新 requirements.txt

```txt
# jetson/requirements.txt

# 相机驱动 (二选一或都安装)
pyrealsense2>=2.50.0  # Intel RealSense
pyorbbecsdk>=1.5.0    # 奥比中光

# 或使用可选依赖
# pyrealsense2>=2.50.0; extra == 'realsense'
# pyorbbecsdk>=1.5.0; extra == 'orbbec'
```

### 3. 配置文件更新

#### 3.1 相机配置

```yaml
# jetson/config/system_config.yaml

camera:
  # 相机类型: "realsense", "orbbec", "auto"
  type: "orbbec"
  
  # 奥比中光配置
  orbbec:
    # 彩色流配置
    color:
      width: 1920
      height: 1080
      fps: 30
      format: "RGB"
    
    # 深度流配置
    depth:
      width: 640
      height: 480
      fps: 30
      format: "Y16"
    
    # 对齐模式
    align_mode: "D2C_HW"  # 深度对齐到彩色（硬件）
    
    # 深度范围 (毫米)
    depth_range:
      min: 600   # 0.6m
      max: 8000  # 8m
    
    # 曝光设置
    exposure:
      auto: true
      value: 10000  # 手动曝光值 (微秒)
    
    # 增益设置
    gain:
      auto: true
      value: 128
    
    # 白平衡
    white_balance:
      auto: true
      value: 4600
  
  # RealSense 配置 (保留兼容)
  realsense:
    width: 1280
    height: 720
    fps: 30
    # ... 其他配置
```

### 4. 深度处理适配

#### 4.1 分辨率差异处理

由于 Orbbec 深度分辨率为 640×480，而 RealSense 为 1280×720，需要调整深度查询逻辑：

```python
# jetson/src/camera/depth_processor.py

class DepthProcessor:
    """深度处理器 - 处理不同分辨率的深度图"""
    
    def __init__(self, color_size: Tuple[int, int], depth_size: Tuple[int, int]):
        self.color_w, self.color_h = color_size
        self.depth_w, self.depth_h = depth_size
        
        # 计算缩放比例
        self.scale_x = self.depth_w / self.color_w
        self.scale_y = self.depth_h / self.color_h
    
    def get_depth_at_color_point(self, x: int, y: int, depth_image: np.ndarray) -> float:
        """
        根据彩色图坐标获取深度值
        
        自动处理分辨率差异
        """
        # 转换到深度图坐标
        depth_x = int(x * self.scale_x)
        depth_y = int(y * self.scale_y)
        
        # 边界检查
        if 0 <= depth_x < self.depth_w and 0 <= depth_y < self.depth_h:
            return depth_image[depth_y, depth_x] / 1000.0
        return 0.0
    
    def get_depth_at_color_region(
        self, 
        x: int, y: int, 
        width: int, height: int, 
        depth_image: np.ndarray
    ) -> float:
        """根据彩色图区域获取深度值（带插值）"""
        # 转换区域到深度图坐标
        depth_x1 = int(x * self.scale_x)
        depth_y1 = int(y * self.scale_y)
        depth_x2 = int((x + width) * self.scale_x)
        depth_y2 = int((y + height) * self.scale_y)
        
        # 提取区域并计算中值
        region = depth_image[depth_y1:depth_y2, depth_x1:depth_x2]
        valid_depths = region[region > 0]
        
        if len(valid_depths) > 0:
            return np.median(valid_depths) / 1000.0
        return 0.0
```

#### 4.2 视觉伺服参数调整

```python
# jetson/src/vision/visual_servo/controller.py

# 根据相机类型调整参数
if camera_type == "orbbec":
    # 奥比中光参数
    self.depth_confidence_threshold = 0.7  # 降低置信度阈值
    self.min_working_distance = 0.6        # 最小工作距离 0.6m
    self.max_working_distance = 6.0        # 实际有效范围约 6m
    self.depth_filter_size = 5             # 增加滤波窗口
else:
    # RealSense 参数
    self.depth_confidence_threshold = 0.8
    self.min_working_distance = 0.3
    self.max_working_distance = 8.0
    self.depth_filter_size = 3
```

### 5. 性能优化

#### 5.1 深度图上采样（可选）

如果需要更高分辨率的深度图，可以使用插值上采样：

```python
import cv2

def upsample_depth(depth_image: np.ndarray, target_size: Tuple[int, int]) -> np.ndarray:
    """
    深度图上采样
    
    使用双线性插值将 640×480 上采样到 1280×720
    """
    return cv2.resize(
        depth_image, 
        target_size, 
        interpolation=cv2.INTER_LINEAR
    )
```

#### 5.2 深度滤波优化

结构光深度图可能有更多噪点，增强滤波：

```python
def filter_depth_orbbec(depth_image: np.ndarray) -> np.ndarray:
    """奥比中光深度图滤波"""
    # 1. 中值滤波去除噪点
    filtered = cv2.medianBlur(depth_image, 5)
    
    # 2. 双边滤波保留边缘
    filtered = cv2.bilateralFilter(
        filtered.astype(np.float32), 
        d=9, 
        sigmaColor=75, 
        sigmaSpace=75
    ).astype(np.uint16)
    
    return filtered
```

---

## 迁移任务清单

### 阶段 1: 驱动适配层 (预计 1-2 天)

- [ ] **TASK-M1: 创建统一相机接口**
  - [ ] 创建 `base_controller.py` 抽象基类
  - [ ] 定义统一的接口方法
  - [ ] 创建共享数据结构 (ImagePair, CameraConfig 等)
  - 预计工时: 2 小时

- [ ] **TASK-M2: 实现 Orbbec 控制器**
  - [ ] 创建 `orbbec_controller.py`
  - [ ] 实现初始化和配置方法
  - [ ] 实现图像采集方法
  - [ ] 实现深度对齐功能
  - [ ] 实现参数调节 (曝光、增益、白平衡)
  - 预计工时: 6 小时

- [ ] **TASK-M3: 重构 RealSense 控制器**
  - [ ] 修改 `controller.py` 继承 `BaseCameraController`
  - [ ] 确保接口一致性
  - [ ] 保持现有功能不变
  - 预计工时: 2 小时

- [ ] **TASK-M4: 实现相机工厂**
  - [ ] 创建 `factory.py`
  - [ ] 实现自动检测逻辑
  - [ ] 实现配置驱动的相机创建
  - 预计工时: 2 小时

- [ ] **TASK-M5: 更新依赖和配置**
  - [ ] 更新 `requirements.txt`
  - [ ] 更新 `system_config.yaml`
  - [ ] 创建 Orbbec 专用配置模板
  - 预计工时: 1 小时

### 阶段 2: 参数调优 (预计 2-3 天)

- [ ] **TASK-M6: 深度处理适配**
  - [ ] 创建 `depth_processor.py`
  - [ ] 实现分辨率转换逻辑
  - [ ] 实现深度滤波优化
  - [ ] 可选: 实现深度上采样
  - 预计工时: 4 小时

- [ ] **TASK-M7: 视觉伺服参数调整**
  - [ ] 调整工作距离参数
  - [ ] 调整深度置信度阈值
  - [ ] 调整滤波参数
  - [ ] 更新 PID 参数（如需要）
  - 预计工时: 3 小时

- [ ] **TASK-M8: 目标检测适配**
  - [ ] 验证检测器在新分辨率下的性能
  - [ ] 调整检测阈值（如需要）
  - [ ] 优化深度查询逻辑
  - 预计工时: 2 小时

- [ ] **TASK-M9: 相机标定**
  - [ ] 获取 Orbbec 相机内参
  - [ ] 验证深度精度
  - [ ] 如需要，进行手动标定
  - 预计工时: 3 小时

- [ ] **TASK-M10: 更新主程序**
  - [ ] 修改 `main.py` 使用工厂模式
  - [ ] 更新初始化流程
  - [ ] 添加相机类型日志
  - 预计工时: 1 小时

### 阶段 3: 测试验证 (预计 1-2 天)

- [ ] **TASK-M11: 单元测试**
  - [ ] 创建 `test_orbbec_controller.py`
  - [ ] 测试初始化和配置
  - [ ] 测试图像采集
  - [ ] 测试深度查询
  - 预计工时: 3 小时

- [ ] **TASK-M12: 集成测试**
  - [ ] 测试相机工厂自动检测
  - [ ] 测试与视觉伺服集成
  - [ ] 测试与目标检测集成
  - [ ] 测试完整工作流程
  - 预计工时: 3 小时

- [ ] **TASK-M13: 性能测试**
  - [ ] 测试帧率和延迟
  - [ ] 测试深度精度
  - [ ] 测试不同距离下的性能
  - [ ] 对比 RealSense 性能
  - 预计工时: 2 小时

- [ ] **TASK-M14: 文档更新**
  - [ ] 更新 README.md
  - [ ] 创建 Orbbec 使用指南
  - [ ] 更新配置文档
  - [ ] 记录已知问题和限制
  - 预计工时: 2 小时

---

## 测试验证计划

### 1. 功能测试

| 测试项 | 测试内容 | 预期结果 | 优先级 |
|--------|---------|---------|--------|
| 相机初始化 | 检测和初始化 Orbbec 相机 | 成功初始化，获取设备信息 | P0 |
| 图像采集 | 采集彩色和深度图像 | 获取有效的图像对 | P0 |
| 深度对齐 | 深度图对齐到彩色图 | 深度和彩色像素对应 | P0 |
| 参数配置 | 调整曝光、增益等参数 | 参数生效，图像质量改善 | P1 |
| 深度查询 | 查询指定点的深度值 | 返回准确的深度值 | P0 |
| 内参获取 | 获取相机内参矩阵 | 返回正确的内参 | P1 |
| 自动检测 | 工厂模式自动检测相机 | 正确识别相机类型 | P1 |

### 2. 性能测试

| 指标 | 目标值 | 测试方法 |
|------|--------|---------|
| 帧率 | ≥ 25 fps | 连续采集 100 帧，计算平均帧率 |
| 采集延迟 | ≤ 50ms | 测量 capture() 方法执行时间 |
| 深度精度 | ±5mm @ 1m | 使用标准物体测量 |
| CPU 占用 | ≤ 30% | 监控采集过程中的 CPU 使用率 |
| 内存占用 | ≤ 500MB | 监控内存使用 |

### 3. 兼容性测试

- [ ] 测试 RealSense 相机仍可正常工作
- [ ] 测试配置文件切换相机类型
- [ ] 测试自动检测在两种相机都存在时的行为
- [ ] 测试在没有相机时的错误处理

### 4. 边界条件测试

- [ ] 最小工作距离 (0.6m) 测试
- [ ] 最大工作距离 (8m) 测试
- [ ] 强光环境测试
- [ ] 低光环境测试
- [ ] 快速运动场景测试

---

## 风险评估

### 高风险项

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|---------|
| SDK 兼容性问题 | 高 | 中 | 提前测试 SDK，准备降级方案 |
| 深度精度不足 | 高 | 低 | 增强滤波算法，调整工作距离 |
| 性能下降 | 中 | 中 | 优化算法，降低处理负载 |

### 中风险项

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|---------|
| 分辨率降低影响检测 | 中 | 中 | 调整检测阈值，优化模型 |
| 最小距离限制 | 中 | 低 | 调整工作流程，避免近距离操作 |
| 室外性能下降 | 中 | 高 | 添加环境光检测，提示用户 |

### 低风险项

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|---------|
| 配置迁移问题 | 低 | 低 | 提供配置迁移工具 |
| 文档不完整 | 低 | 中 | 补充文档和示例 |

---

## 实施时间表

```
Week 1:
  Day 1-2: 阶段 1 - 驱动适配层
    - TASK-M1 ~ TASK-M5
  
  Day 3-5: 阶段 2 - 参数调优
    - TASK-M6 ~ TASK-M10

Week 2:
  Day 1-2: 阶段 3 - 测试验证
    - TASK-M11 ~ TASK-M14
  
  Day 3: 缓冲时间和问题修复
```

**总预计工时**: 40-50 小时  
**建议实施周期**: 1-2 周

---

## 后续优化建议

1. **深度图增强**
   - 实现时域滤波（多帧平均）
   - 实现空洞填充算法
   - 优化边缘保持滤波

2. **多相机支持**
   - 支持同时使用多个 Orbbec 相机
   - 实现相机阵列标定
   - 实现深度融合

3. **性能优化**
   - 使用 GPU 加速深度处理
   - 优化内存使用
   - 实现异步采集

4. **功能扩展**
   - 支持 Orbbec 的骨骼跟踪功能
   - 支持手势识别
   - 支持 3D 重建

---

## 参考资料

1. **Orbbec SDK 文档**
   - GitHub: https://github.com/orbbec/pyorbbecsdk
   - 官方文档: https://www.orbbec.com.cn/developers/

2. **技术对比**
   - 结构光 vs 主动立体视觉原理
   - 深度相机选型指南

3. **相关工具**
   - Orbbec Viewer (相机测试工具)
   - OpenNI2 (备选 SDK)

---

**文档维护**: 请在实施过程中及时更新本文档，记录遇到的问题和解决方案。
