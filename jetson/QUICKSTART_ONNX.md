# ONNX Runtime 快速开始指南

## 5分钟快速上手

### 第一步：安装依赖（2分钟）

```bash
# 进入项目目录
cd jetson

# 安装ONNX Runtime（GPU版本，推荐）
pip install onnxruntime-gpu

# 或安装CPU版本
pip install onnxruntime

# 安装模型转换工具
pip install onnx onnx-simplifier
```

### 第二步：转换模型（2分钟）

```bash
# 将PyTorch模型转换为ONNX格式
python scripts/convert_to_onnx.py \
    --model models/yolov5s.pt \
    --output models/yolov5s.onnx
```

**预期输出**:
```
✅ ONNX模型已保存: models/yolov5s.onnx
✅ ONNX模型格式正确
✅ 输出一致性验证通过
🎉 模型转换成功！
```

### 第三步：验证安装（1分钟）

```bash
# 运行集成测试
python scripts/test_onnx_support.py
```

**预期输出**:
```
✅ 所有测试通过！
   - ONNX Runtime: 可用 ✅
   - 模拟模式: 正常工作 ✅
   - 推理引擎选择: 正常工作 ✅
```

## 使用示例

### 基本使用

```python
from src.vision.detector import ObjectDetector, DetectionConfig
import numpy as np

# 1. 创建配置
config = DetectionConfig(
    model_path="models/yolov5s.onnx",
    threshold=0.5
)

# 2. 创建检测器
detector = ObjectDetector(config)

# 3. 加载模型
success, msg = detector.load_model()
print(f"使用引擎: {detector.get_inference_engine()}")

# 4. 执行检测
image = np.random.randint(0, 255, (720, 1280, 3), dtype=np.uint8)
result = detector.detect(image)

print(f"检测到 {result.target_count} 个目标")
print(f"FPS: {1000/result.total_time:.2f}")
```

### 性能测试

```bash
# 测试模型性能
python scripts/benchmark_detector.py --model models/yolov5s.onnx
```

**预期输出**:
```
平均总延迟: 25.34 ms
FPS: 39.47
性能评级: 良好 ⭐⭐⭐⭐
```

## 常见问题快速解决

### Q: ONNX Runtime找不到CUDA？

```bash
# 解决方案：安装GPU版本
pip uninstall onnxruntime
pip install onnxruntime-gpu
```

### Q: 模型转换失败？

```bash
# 检查PyTorch版本
python -c "import torch; print(torch.__version__)"

# 需要PyTorch 1.10+
pip install torch>=1.10.0
```

### Q: 如何确认使用GPU？

```python
import onnxruntime as ort
print(ort.get_available_providers())
# 应该看到: ['CUDAExecutionProvider', 'CPUExecutionProvider']
```

## 下一步

1. **阅读详细文档**
   - [ONNX Runtime使用指南](docs/ONNX_RUNTIME_USAGE_GUIDE.md)
   - [性能优化建议](docs/TENSORRT_PYTHON_COMPATIBILITY_SOLUTION.md)

2. **部署到Jetson Nano**
   ```bash
   # 在Jetson Nano上
   pip install onnxruntime-gpu
   python main.py
   ```

3. **性能调优**
   - 调整输入尺寸
   - 启用FP16量化
   - 优化批处理

## 获取帮助

- 查看文档: `jetson/docs/`
- 运行测试: `python scripts/test_onnx_support.py`
- 性能测试: `python scripts/benchmark_detector.py`

---

**恭喜！你已成功集成ONNX Runtime，现在可以在Python 3.6-3.11环境下运行高性能目标检测了！** 🎉
