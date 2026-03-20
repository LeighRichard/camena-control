# Desktop App Implementation Plan

## 已完成：任务 15.1 - Electron 项目结构

### ✅ 完成内容

1. **项目基础架构**
   - Electron + React 技术栈
   - 主进程（main.js）和渲染进程分离
   - Preload 脚本实现安全的 IPC 通信
   - Electron Store 用于持久化存储

2. **React 应用结构**
   - Context API 状态管理（ConnectionContext, CameraContext）
   - 组件化架构
   - 基础 UI 组件（ConnectionManager, VideoPreview, Sidebar, StatusBar, ControlPanel）

3. **核心功能**
   - 连接管理（本地 WiFi 和远程 4G）
   - 实时视频流显示
   - WebSocket 实时状态更新
   - 应用菜单和快捷键框架

## 待实现任务概览

### 任务 15.2 - 高分辨率预览

**目标**: 实现高质量视频预览，支持全屏和多窗口

**实现要点**:
```javascript
// components/HighResPreview.js
- 使用 Canvas 或 WebGL 渲染高分辨率视频
- 实现缩放和平移功能
- 支持全屏模式（F11）
- 多窗口支持（Electron BrowserWindow）
- 目标检测结果叠加显示
- 性能优化（帧率控制、内存管理）
```

**关键代码**:
```javascript
// 创建新窗口
const previewWindow = new BrowserWindow({
  width: 1920,
  height: 1080,
  fullscreen: true
});

// Canvas 渲染
const canvas = document.getElementById('preview-canvas');
const ctx = canvas.getContext('2d');
// 绘制视频帧和检测框
```

### 任务 15.3 - 键盘控制

**目标**: 实现完整的键盘快捷键控制系统

**实现要点**:
```javascript
// hooks/useKeyboardControls.js
- 方向键控制相机位置（↑↓←→）
- 数字键快速定位
- 空格键拍摄
- Ctrl+方向键精细调整
- 可自定义快捷键绑定
- 快捷键冲突检测
```

**快捷键映射**:
```javascript
const keyMap = {
  'ArrowUp': () => adjustPosition({ tilt: 1 }),
  'ArrowDown': () => adjustPosition({ tilt: -1 }),
  'ArrowLeft': () => adjustPosition({ pan: -1 }),
  'ArrowRight': () => adjustPosition({ pan: 1 }),
  'Space': () => capture(),
  'KeyH': () => homePosition(),
  // ... 更多快捷键
};
```

### 任务 15.4 - 高级配置面板

**目标**: 提供详细的系统参数配置界面和路径编辑器

**实现要点**:
```javascript
// components/AdvancedConfig/
├── ConfigPanel.js          # 主配置面板
├── CameraSettings.js       # 相机参数配置
├── MotionSettings.js       # 运动控制参数
├── DetectionSettings.js    # 目标检测配置
└── PathEditor.js           # 路径编辑器

// 路径编辑器功能
- 可视化路径点编辑
- 拖拽添加/删除路径点
- 路径预览和验证
- 导入/导出路径配置
- 3D 路径可视化
```

**路径编辑器示例**:
```javascript
// PathEditor.js
const PathEditor = () => {
  const [pathPoints, setPathPoints] = useState([]);
  
  const addPoint = (position) => {
    setPathPoints([...pathPoints, {
      pan: position.pan,
      tilt: position.tilt,
      rail: position.rail,
      settleTime: 0.5,
      captureFrames: 5
    }]);
  };
  
  return (
    <div className="path-editor">
      <Canvas3D points={pathPoints} />
      <PointList points={pathPoints} onEdit={editPoint} />
      <Controls onAdd={addPoint} onSave={savePath} />
    </div>
  );
};
```

### 任务 15.5 - 数据管理

**目标**: 实现批量导出和日志查看功能

**实现要点**:
```javascript
// components/DataManager/
├── ImageGallery.js         # 图像浏览器
├── BatchExport.js          # 批量导出
├── MetadataViewer.js       # 元数据查看
└── LogViewer.js            # 日志查看器

// 批量导出功能
- 选择导出范围（日期、标签）
- 导出格式选择（ZIP、文件夹）
- 包含元数据（JSON、CSV）
- 进度显示和取消
- 导出历史记录
```

**批量导出实现**:
```javascript
const BatchExport = () => {
  const exportImages = async (selection) => {
    const { dialog } = require('electron').remote;
    const savePath = await dialog.showSaveDialog({
      title: 'Export Images',
      defaultPath: 'captures.zip'
    });
    
    // 创建 ZIP 文件
    const zip = new JSZip();
    for (const item of selection) {
      const imageData = await fetchImage(item.imagePath);
      zip.file(`${item.id}.jpg`, imageData);
      zip.file(`${item.id}.json`, JSON.stringify(item.metadata));
    }
    
    const content = await zip.generateAsync({ type: 'nodebuffer' });
    await fs.writeFile(savePath.filePath, content);
  };
};
```

### 任务 15.6 - 模型管理

**目标**: 实现深度学习模型的上传和切换功能

**实现要点**:
```javascript
// components/ModelManager/
├── ModelList.js            # 模型列表
├── ModelUpload.js          # 模型上传
├── ModelInfo.js            # 模型信息
└── ModelSwitch.js          # 模型切换

// 模型管理功能
- 显示已安装模型列表
- 上传新模型（ONNX、TensorRT）
- 模型信息查看（大小、精度、速度）
- 一键切换模型
- 模型性能测试
- 模型删除和备份
```

**模型上传实现**:
```javascript
const ModelUpload = () => {
  const uploadModel = async (file) => {
    const formData = new FormData();
    formData.append('model', file);
    formData.append('name', file.name);
    formData.append('type', detectModelType(file));
    
    const response = await axios.post(
      `${serverUrl}/api/model/upload`,
      formData,
      {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (progressEvent) => {
          const progress = (progressEvent.loaded / progressEvent.total) * 100;
          setUploadProgress(progress);
        }
      }
    );
    
    return response.data;
  };
  
  return (
    <div className="model-upload">
      <input type="file" accept=".onnx,.trt,.engine" onChange={handleFileSelect} />
      {uploading && <ProgressBar value={uploadProgress} />}
    </div>
  );
};
```

## 技术栈详细说明

### 前端技术
- **Electron**: 跨平台桌面应用框架
- **React**: UI 组件库
- **Socket.IO**: WebSocket 实时通信
- **Axios**: HTTP 客户端
- **Canvas/WebGL**: 高性能视频渲染
- **JSZip**: ZIP 文件处理
- **Chart.js**: 数据可视化

### 状态管理
- **React Context API**: 全局状态管理
- **Electron Store**: 持久化存储
- **Custom Hooks**: 业务逻辑封装

### IPC 通信
- **Main Process**: 系统级操作（文件、窗口）
- **Renderer Process**: UI 渲染
- **Preload Script**: 安全的 IPC 桥接

## 开发建议

### 1. 组件开发顺序
1. 先完成基础 UI 组件
2. 实现核心功能（视频预览、控制）
3. 添加高级功能（路径编辑、数据管理）
4. 优化性能和用户体验

### 2. 测试策略
- 单元测试：Jest + React Testing Library
- 集成测试：Electron 应用测试
- E2E 测试：Spectron
- 性能测试：Chrome DevTools

### 3. 性能优化
- 使用 React.memo 避免不必要的重渲染
- 虚拟滚动处理大量数据
- Web Worker 处理计算密集任务
- 图像懒加载和缓存

### 4. 打包和分发
```bash
# Windows
npm run package -- --win

# macOS
npm run package -- --mac

# Linux
npm run package -- --linux
```

## API 端点需求

桌面应用需要后端提供以下额外的 API 端点：

```javascript
// 模型管理
POST   /api/model/upload          # 上传模型
GET    /api/model/list            # 获取模型列表
POST   /api/model/switch          # 切换模型
DELETE /api/model/:id             # 删除模型

// 数据导出
GET    /api/export/images         # 批量导出图像
GET    /api/export/metadata       # 导出元数据
GET    /api/logs                  # 获取系统日志

// 路径管理
GET    /api/path/list             # 获取路径列表
POST   /api/path/save             # 保存路径
DELETE /api/path/:id              # 删除路径
GET    /api/path/:id/preview      # 路径预览
```

## 需求验证清单

- [ ] **11.1** - Windows 和 macOS 支持 ✅ (Electron 跨平台)
- [ ] **11.2** - 高分辨率预览和全屏支持
- [ ] **11.3** - 键盘快捷键控制
- [ ] **11.4** - 详细参数配置界面
- [ ] **11.5** - 批量导出和日志查看
- [ ] **11.6** - 路径编辑和可视化
- [ ] **11.7** - 系统日志查看
- [ ] **11.8** - 模型管理功能

## 下一步行动

1. **立即可做**:
   - 完善现有组件的功能
   - 添加错误处理和加载状态
   - 实现键盘控制 hook

2. **短期目标**:
   - 实现高分辨率预览组件
   - 开发路径编辑器
   - 添加数据导出功能

3. **长期目标**:
   - 完整的模型管理系统
   - 高级数据分析功能
   - 性能监控和优化

## 总结

任务 15.1 已经建立了坚实的基础架构，包括：
- ✅ Electron + React 项目结构
- ✅ 连接管理和状态管理
- ✅ 基础 UI 组件
- ✅ 菜单和快捷键框架
- ✅ WebSocket 实时通信

剩余任务（15.2-15.6）主要是在这个基础上添加更多专业功能和优化用户体验。所有组件都遵循相同的架构模式，可以逐步实现。
