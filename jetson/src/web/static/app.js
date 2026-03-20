/**
 * 相机位置控制系统 - 前端应用
 */

// API 基础路径
const API_BASE = '';

// 状态
let currentMode = 'auto';
let isAutoCapturing = false;
let targets = [];
let selectedTargetId = null;

// DOM 元素
const elements = {
    connectionStatus: document.getElementById('connectionStatus'),
    videoStream: document.getElementById('videoStream'),
    videoFps: document.getElementById('videoFps'),
    videoResolution: document.getElementById('videoResolution'),
    panPosition: document.getElementById('panPosition'),
    tiltPosition: document.getElementById('tiltPosition'),
    railPosition: document.getElementById('railPosition'),
    targetList: document.getElementById('targetList'),
    captureProgress: document.getElementById('captureProgress'),
    captureStatus: document.getElementById('captureStatus'),
    logPanel: document.getElementById('logPanel'),
    modeAuto: document.getElementById('modeAuto'),
    modeManual: document.getElementById('modeManual'),
    modeFace: document.getElementById('modeFace'),
    faceCount: document.getElementById('faceCount'),
    faceList: document.getElementById('faceList'),
    faceName: document.getElementById('faceName'),
    currentFace: document.getElementById('currentFace'),
    currentFaceName: document.getElementById('currentFaceName')
};

// 日志
function log(message) {
    const time = new Date().toLocaleTimeString();
    const entry = document.createElement('div');
    entry.className = 'log-entry';
    entry.innerHTML = `<span class="log-time">${time}</span> ${message}`;
    elements.logPanel.insertBefore(entry, elements.logPanel.firstChild);
    
    // 限制日志数量
    while (elements.logPanel.children.length > 50) {
        elements.logPanel.removeChild(elements.logPanel.lastChild);
    }
}

// API 请求
async function api(endpoint, method = 'GET', data = null) {
    const options = {
        method,
        headers: {
            'Content-Type': 'application/json'
        }
    };
    
    if (data) {
        options.body = JSON.stringify(data);
    }
    
    try {
        const response = await fetch(`${API_BASE}${endpoint}`, options);
        const result = await response.json();
        
        if (!response.ok) {
            throw new Error(result.error || '请求失败');
        }
        
        return result;
    } catch (error) {
        log(`❌ ${error.message}`);
        throw error;
    }
}

// 更新连接状态
function updateConnectionStatus(connected) {
    elements.connectionStatus.textContent = connected ? '已连接' : '断开连接';
    elements.connectionStatus.className = connected ? 'status-badge' : 'status-badge error';
}

// 更新位置显示
function updatePosition(pan, tilt, rail) {
    elements.panPosition.textContent = pan?.toFixed(1) ?? '--';
    elements.tiltPosition.textContent = tilt?.toFixed(1) ?? '--';
    elements.railPosition.textContent = rail?.toFixed(1) ?? '--';
}

// 更新目标列表
function updateTargets(newTargets, selectedId) {
    targets = newTargets || [];
    selectedTargetId = selectedId;
    
    if (targets.length === 0) {
        elements.targetList.innerHTML = '<div class="target-item"><span style="color: #888">暂无检测目标</span></div>';
        return;
    }
    
    elements.targetList.innerHTML = targets.map(t => `
        <div class="target-item ${t.id === selectedId ? 'selected' : ''}" onclick="selectTarget(${t.id})">
            <div class="target-info">
                <span class="target-name">#${t.id} ${t.class_name}</span>
                <span class="target-meta">${(t.confidence * 100).toFixed(0)}% ${t.depth ? t.depth.toFixed(2) + 'm' : ''}</span>
            </div>
        </div>
    `).join('');
}

// 更新自动拍摄状态
function updateAutoCaptureStatus(progress) {
    if (!progress) return;
    
    const percent = progress.total_points > 0 
        ? (progress.current_point / progress.total_points * 100) 
        : 0;
    
    elements.captureProgress.style.width = `${percent}%`;
    
    let statusText = '就绪';
    if (progress.state === 'running') {
        statusText = `拍摄中 ${progress.current_point}/${progress.total_points}`;
        isAutoCapturing = true;
    } else if (progress.state === 'paused') {
        statusText = '已暂停';
    } else if (progress.state === 'completed') {
        statusText = `完成 (${progress.captured_count} 张)`;
        isAutoCapturing = false;
    } else {
        isAutoCapturing = false;
    }
    
    elements.captureStatus.textContent = statusText;
}

// 轮询状态
async function pollStatus() {
    try {
        // 获取系统状态
        const status = await api('/api/status');
        updateConnectionStatus(true);
        
        // 更新位置
        if (status.motion) {
            updatePosition(
                status.motion.pan_position,
                status.motion.tilt_position,
                status.motion.rail_position
            );
        }
        
        // 更新目标
        if (status.detection) {
            updateTargets(status.detection.targets, status.detection.selected_target_id);
        }
        
        // 更新自动拍摄
        const autoStatus = await api('/api/auto/status');
        updateAutoCaptureStatus(autoStatus);
        
    } catch (error) {
        updateConnectionStatus(false);
    }
}

// 拍摄
async function capture() {
    try {
        log('📸 拍摄中...');
        const result = await api('/api/camera/capture', 'POST');
        log(`✅ 拍摄成功`);
    } catch (error) {
        // 错误已在 api 函数中记录
    }
}

// 切换自动拍摄
async function toggleAutoCapture() {
    try {
        if (isAutoCapturing) {
            await api('/api/auto/pause', 'POST');
            log('⏸ 自动拍摄已暂停');
        } else {
            await api('/api/auto/start', 'POST');
            log('▶️ 自动拍摄已开始');
        }
    } catch (error) {
        // 错误已在 api 函数中记录
    }
}

// 停止运动
async function stopMotion() {
    try {
        await api('/api/motion/stop', 'POST');
        log('⏹ 运动已停止');
    } catch (error) {
        // 错误已在 api 函数中记录
    }
}

// 归零
async function homeAxis() {
    try {
        await api('/api/motion/home', 'POST');
        log('🏠 开始归零');
    } catch (error) {
        // 错误已在 api 函数中记录
    }
}

// 运动控制
async function move(direction) {
    const step = 5.0;
    let pan = 0, tilt = 0, rail = 0;
    
    switch (direction) {
        case 'up': tilt = step; break;
        case 'down': tilt = -step; break;
        case 'left': pan = -step; break;
        case 'right': pan = step; break;
        case 'center': break;
    }
    
    try {
        // 获取当前位置
        const pos = await api('/api/motion/position');
        
        // 计算新位置
        await api('/api/motion/move', 'POST', {
            pan: (pos.pan || 0) + pan,
            tilt: (pos.tilt || 0) + tilt,
            rail: (pos.rail || 0) + rail
        });
    } catch (error) {
        // 错误已在 api 函数中记录
    }
}

// 设置检测模式
async function setMode(mode) {
    try {
        if (mode === 'face') {
            // 人脸跟踪模式
            await startFaceTracking();
            currentMode = 'face';
        } else {
            await api('/api/detection/mode', 'POST', { mode });
            currentMode = mode;
        }
        
        elements.modeAuto.className = mode === 'auto' ? 'active' : '';
        elements.modeManual.className = mode === 'manual' ? 'active' : '';
        if (elements.modeFace) {
            elements.modeFace.className = mode === 'face' ? 'active' : '';
        }
        
        const modeNames = { auto: '自动', manual: '手动', face: '人脸跟踪' };
        log(`🎯 切换到${modeNames[mode] || mode}模式`);
    } catch (error) {
        // 错误已在 api 函数中记录
    }
}

// 选择目标
async function selectTarget(targetId) {
    if (currentMode !== 'manual') {
        log('⚠️ 请先切换到手动模式');
        return;
    }
    
    try {
        await api('/api/detection/select', 'POST', { target_id: targetId });
        log(`🎯 已选择目标 #${targetId}`);
    } catch (error) {
        // 错误已在 api 函数中记录
    }
}

// 键盘控制
document.addEventListener('keydown', (e) => {
    switch (e.key) {
        case 'ArrowUp': move('up'); break;
        case 'ArrowDown': move('down'); break;
        case 'ArrowLeft': move('left'); break;
        case 'ArrowRight': move('right'); break;
        case ' ': capture(); e.preventDefault(); break;
        case 'Escape': stopMotion(); break;
    }
});

// 视频流错误处理
elements.videoStream.onerror = () => {
    log('⚠️ 视频流连接失败，尝试重连...');
    setTimeout(() => {
        elements.videoStream.src = `/api/video/stream?t=${Date.now()}`;
    }, 2000);
};

// 初始化
log('🚀 系统启动');
pollStatus();
loadRegisteredFaces();
setInterval(pollStatus, 1000);
setInterval(updateFaceTrackingStatus, 500);

// ==================== 人脸识别功能 ====================

// 加载已注册人脸
async function loadRegisteredFaces() {
    try {
        const result = await api('/api/face/registered');
        updateFaceList(result.names || []);
        if (elements.faceCount) {
            elements.faceCount.textContent = result.count || 0;
        }
    } catch (error) {
        // 人脸识别可能未启用
    }
}

// 更新人脸列表
function updateFaceList(names) {
    if (!elements.faceList) return;
    
    if (names.length === 0) {
        elements.faceList.innerHTML = '<div style="color: #888; font-size: 0.85rem;">暂无注册人脸</div>';
        return;
    }
    
    elements.faceList.innerHTML = names.map(name => `
        <div class="face-item">
            <span class="name">👤 ${name}</span>
            <button class="delete-btn" onclick="deleteFace('${name}')">删除</button>
        </div>
    `).join('');
}

// 注册人脸
async function registerFace() {
    const name = elements.faceName?.value?.trim();
    if (!name) {
        log('⚠️ 请输入姓名');
        return;
    }
    
    try {
        log(`📷 正在注册人脸: ${name}...`);
        const result = await api('/api/face/register', 'POST', { name });
        
        if (result.success) {
            log(`✅ ${result.message}`);
            elements.faceName.value = '';
            loadRegisteredFaces();
        } else {
            log(`❌ ${result.message}`);
        }
    } catch (error) {
        // 错误已记录
    }
}

// 删除人脸
async function deleteFace(name) {
    if (!confirm(`确定要删除 "${name}" 的人脸数据吗？`)) {
        return;
    }
    
    try {
        const result = await api('/api/face/unregister', 'POST', { name });
        if (result.success) {
            log(`✅ ${result.message}`);
            loadRegisteredFaces();
        } else {
            log(`❌ ${result.message}`);
        }
    } catch (error) {
        // 错误已记录
    }
}

// 开始人脸跟踪
async function startFaceTracking() {
    try {
        await api('/api/face/tracking/start', 'POST');
        log('🎯 开始人脸跟踪');
    } catch (error) {
        // 错误已记录
    }
}

// 停止人脸跟踪
async function stopFaceTracking() {
    try {
        await api('/api/face/tracking/stop', 'POST');
        log('⏹ 停止人脸跟踪');
        if (elements.currentFace) {
            elements.currentFace.style.display = 'none';
        }
    } catch (error) {
        // 错误已记录
    }
}

// 更新人脸跟踪状态
async function updateFaceTrackingStatus() {
    try {
        const status = await api('/api/face/tracking/status');
        
        if (status.is_face_tracking && status.current_face) {
            if (elements.currentFace) {
                elements.currentFace.style.display = 'block';
            }
            if (elements.currentFaceName) {
                elements.currentFaceName.textContent = status.current_face.name;
            }
        } else {
            if (elements.currentFace) {
                elements.currentFace.style.display = 'none';
            }
        }
    } catch (error) {
        // 静默失败
    }
}
