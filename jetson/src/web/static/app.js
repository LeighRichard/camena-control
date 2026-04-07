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
let currentCommTraceSource = '';
let isFaceOverlayUpdating = false;

// DOM 元素
const elements = {
    connectionStatus: document.getElementById('connectionStatus'),
    videoContainer: document.getElementById('videoContainer'),
    videoStream: document.getElementById('videoStream'),
    videoOverlayCanvas: document.getElementById('videoOverlayCanvas'),
    videoFps: document.getElementById('videoFps'),
    videoResolution: document.getElementById('videoResolution'),
    panPosition: document.getElementById('panPosition'),
    tiltPosition: document.getElementById('tiltPosition'),
    railPosition: document.getElementById('railPosition'),
    detectorStatus: document.getElementById('detectorStatus'),
    detectorMeta: document.getElementById('detectorMeta'),
    targetList: document.getElementById('targetList'),
    captureProgress: document.getElementById('captureProgress'),
    captureStatus: document.getElementById('captureStatus'),
    logPanel: document.getElementById('logPanel'),
    commTraceMeta: document.getElementById('commTraceMeta'),
    commTraceCount: document.getElementById('commTraceCount'),
    commTraceList: document.getElementById('commTraceList'),
    commTraceSource: document.getElementById('commTraceSource'),
    modeAuto: document.getElementById('modeAuto'),
    modeManual: document.getElementById('modeManual'),
    modeFace: document.getElementById('modeFace'),
    faceCount: document.getElementById('faceCount'),
    faceList: document.getElementById('faceList'),
    faceName: document.getElementById('faceName'),
    currentFace: document.getElementById('currentFace'),
    currentFaceName: document.getElementById('currentFaceName')
};

const faceOverlayState = {
    faces: [],
    frameWidth: 0,
    frameHeight: 0,
    overlayRegion: null
};

// 日志
function log(message) {
    if (!elements.logPanel) {
        console.log(message);
        return;
    }

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

function clearFaceOverlay() {
    const canvas = elements.videoOverlayCanvas;
    if (!canvas) {
        return;
    }

    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);
}

function resizeFaceOverlayCanvas() {
    const canvas = elements.videoOverlayCanvas;
    const container = elements.videoContainer;
    if (!canvas || !container) {
        return;
    }

    const width = Math.max(1, Math.floor(container.clientWidth));
    const height = Math.max(1, Math.floor(container.clientHeight));

    if (canvas.width !== width || canvas.height !== height) {
        canvas.width = width;
        canvas.height = height;
    }
}

function getContainedRect(containerWidth, containerHeight, sourceWidth, sourceHeight) {
    if (!containerWidth || !containerHeight || !sourceWidth || !sourceHeight) {
        return null;
    }

    const scale = Math.min(containerWidth / sourceWidth, containerHeight / sourceHeight);
    const width = sourceWidth * scale;
    const height = sourceHeight * scale;

    return {
        x: (containerWidth - width) / 2,
        y: (containerHeight - height) / 2,
        width,
        height,
        scale
    };
}

function drawFaceOverlay() {
    const canvas = elements.videoOverlayCanvas;
    if (!canvas) {
        return;
    }

    resizeFaceOverlayCanvas();
    clearFaceOverlay();

    if (!faceOverlayState.faces.length || !faceOverlayState.frameWidth || !faceOverlayState.frameHeight) {
        return;
    }

    const ctx = canvas.getContext('2d');
    const frameRect = getContainedRect(
        canvas.width,
        canvas.height,
        faceOverlayState.frameWidth,
        faceOverlayState.frameHeight
    );

    if (!frameRect) {
        return;
    }

    const overlayRegion = faceOverlayState.overlayRegion || {
        x: 0,
        y: 0,
        width: faceOverlayState.frameWidth,
        height: faceOverlayState.frameHeight
    };

    faceOverlayState.faces.forEach((face) => {
        const [x, y, width, height] = face.bounding_box || [0, 0, 0, 0];
        const drawX = frameRect.x + (overlayRegion.x + x) * frameRect.scale;
        const drawY = frameRect.y + (overlayRegion.y + y) * frameRect.scale;
        const drawWidth = width * frameRect.scale;
        const drawHeight = height * frameRect.scale;
        const faceName = face.name || 'Unknown';
        const isKnown = faceName !== 'Unknown';
        const confidence = Number.isFinite(face.confidence) ? Math.round(face.confidence * 100) : 0;
        const label = `${faceName} ${confidence}%`;

        ctx.lineWidth = 3;
        ctx.strokeStyle = isKnown ? '#4ade80' : '#fbbf24';
        ctx.strokeRect(drawX, drawY, drawWidth, drawHeight);

        ctx.fillStyle = isKnown ? 'rgba(22, 163, 74, 0.88)' : 'rgba(217, 119, 6, 0.88)';
        ctx.font = '14px sans-serif';
        const textWidth = ctx.measureText(label).width;
        const textHeight = 22;
        const labelY = Math.max(0, drawY - textHeight - 4);
        ctx.fillRect(drawX, labelY, textWidth + 16, textHeight);

        ctx.fillStyle = '#ffffff';
        ctx.fillText(label, drawX + 8, labelY + 15);

        ctx.beginPath();
        ctx.arc(drawX + drawWidth / 2, drawY + drawHeight / 2, 4, 0, Math.PI * 2);
        ctx.fillStyle = isKnown ? '#4ade80' : '#fbbf24';
        ctx.fill();
    });
}

// API 请求
async function api(endpoint, method = 'GET', data = null) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000);

    const options = {
        method,
        signal: controller.signal,
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
        if (error && error.name === 'AbortError') {
            log('❌ 请求超时，请检查相机/后端状态');
            throw new Error('请求超时，请检查相机/后端状态');
        }
        log(`❌ ${error.message}`);
        throw error;
    } finally {
        clearTimeout(timeout);
    }
}

async function apiSilent(endpoint, method = 'GET', data = null) {
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
            return null;
        }
        return result;
    } catch (error) {
        return null;
    }
}

// 更新连接状态
function updateConnectionStatus(connected) {
    elements.connectionStatus.textContent = connected ? '已连接' : '断开连接';
    elements.connectionStatus.className = connected ? 'status-badge' : 'status-badge error';
}

function updateDetectorRuntime(detectorState) {
    if (!elements.detectorStatus || !elements.detectorMeta) {
        return;
    }

    if (!detectorState || detectorState.enabled === false) {
        elements.detectorStatus.textContent = '检测器未初始化';
        elements.detectorMeta.textContent = '模型: --';
        return;
    }

    if (detectorState.loaded) {
        if (detectorState.simulation_mode) {
            elements.detectorStatus.textContent = '检测器已加载（模拟模式）';
        } else if (detectorState.inference_engine === 'tensorrt') {
            elements.detectorStatus.textContent = 'TensorRT 推理已启用';
        } else {
            const engineName = detectorState.inference_engine || 'unknown';
            elements.detectorStatus.textContent = `检测器已加载（${engineName}）`;
        }
    } else {
        elements.detectorStatus.textContent = '检测模型未加载';
    }

    const metaParts = [];
    if (detectorState.model_path) {
        metaParts.push(`模型: ${detectorState.model_path}`);
    }

    if (detectorState.loaded) {
        const engineName = detectorState.inference_engine || 'unknown';
        metaParts.push(`引擎: ${engineName}`);
    }

    if (detectorState.tensorrt_available !== null && detectorState.tensorrt_available !== undefined) {
        metaParts.push(`TensorRT: ${detectorState.tensorrt_available ? '可用' : '不可用'}`);
    }

    if (detectorState.last_error) {
        metaParts.push(`错误: ${detectorState.last_error}`);
    }

    elements.detectorMeta.textContent = metaParts.join(' | ') || '模型: --';
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

function formatTraceTimestamp(timestamp) {
    if (!timestamp) return '--:--:--';
    return new Date(timestamp * 1000).toLocaleTimeString();
}

function renderTraceDetails(record) {
    const parts = [];

    if (record.seq !== undefined) {
        parts.push(`seq=${record.seq}`);
    }
    if (record.command) {
        parts.push(`cmd=${record.command}`);
    }
    if (record.response) {
        parts.push(`rsp=${record.response}`);
    }
    if (record.axis) {
        parts.push(`axis=${record.axis}`);
    }
    if (record.status) {
        parts.push(`status=${record.status}`);
    }
    if (record.param) {
        parts.push(`param=${record.param}`);
    }
    if (record.value !== undefined) {
        parts.push(`value=${record.value}`);
    }
    if (record.raw_value !== undefined) {
        parts.push(`raw=${record.raw_value}`);
    }
    if (record.expected_seq !== undefined) {
        parts.push(`expected=${record.expected_seq}`);
    }
    if (record.error) {
        parts.push(`error=${record.error}`);
    }

    return parts.join('  ');
}

function updateCommDiagnosticsPanel(data) {
    if (!elements.commTraceList || !elements.commTraceMeta || !elements.commTraceCount) {
        return;
    }

    if (!data) {
        elements.commTraceMeta.textContent = '诊断接口不可用';
        elements.commTraceCount.textContent = '--';
        elements.commTraceList.innerHTML = '<div class="trace-empty">当前无法获取串口诊断信息</div>';
        return;
    }

    const metaParts = [
        `状态: ${data.state || 'unknown'}`,
        `协议日志: ${data.trace_protocol ? '开' : '关'}`,
        `帧日志: ${data.trace_frames_hex ? '开' : '关'}`
    ];
    elements.commTraceMeta.textContent = metaParts.join(' · ');
    elements.commTraceCount.textContent = `${data.returned_count ?? 0} / ${data.history_count ?? 0}`;

    const records = data.records || [];
    if (records.length === 0) {
        elements.commTraceList.innerHTML = '<div class="trace-empty">暂无串口诊断记录</div>';
        return;
    }

    elements.commTraceList.innerHTML = records.map(record => {
        const source = String(record.source || '').toLowerCase();
        const title = record.command || record.response || record.event || 'trace';
        const details = renderTraceDetails(record);
        const frameHex = record.frame_hex
            ? (record.frame_hex.length > 96 ? `${record.frame_hex.slice(0, 96)}...` : record.frame_hex)
            : '';

        return `
            <div class="trace-item ${source}">
                <div class="trace-head">
                    <div class="trace-title">
                        <span class="trace-badge">${record.source || 'TRACE'}</span>
                        <span class="trace-name">${title}</span>
                    </div>
                    <span class="trace-time">${formatTraceTimestamp(record.timestamp)}</span>
                </div>
                <div class="trace-details">${details || '无附加字段'}</div>
                ${frameHex ? `<div class="trace-frame" title="${record.frame_hex}">${frameHex}</div>` : ''}
            </div>
        `;
    }).join('');
}

async function refreshCommDiagnostics() {
    const params = new URLSearchParams();
    params.set('limit', '8');
    if (currentCommTraceSource) {
        params.set('source', currentCommTraceSource);
    }

    const result = await apiSilent(`/api/comm/diagnostics?${params.toString()}`);
    updateCommDiagnosticsPanel(result);
}

async function clearCommDiagnostics() {
    try {
        const result = await api('/api/comm/diagnostics/clear', 'POST');
        log(`🧹 已清空 ${result.cleared ?? 0} 条串口诊断记录`);
        refreshCommDiagnostics();
    } catch (error) {
        // 错误已在 api 函数中记录
    }
}

function setCommTraceSource(source) {
    currentCommTraceSource = source || '';
    refreshCommDiagnostics();
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

        updateDetectorRuntime(status.runtime ? status.runtime.detector : null);
        
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

        updateFaceOverlay();
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
refreshCommDiagnostics();
loadRegisteredFaces();
updateFaceOverlay();
setInterval(pollStatus, 1500);
setInterval(refreshCommDiagnostics, 5000);
setInterval(updateFaceTrackingStatus, 1200);
setInterval(updateFaceOverlay, 2500);

window.addEventListener('resize', drawFaceOverlay);
elements.videoStream?.addEventListener('load', drawFaceOverlay);

// ==================== 人脸识别功能 ====================

async function updateFaceOverlay() {
    if (document.hidden || isFaceOverlayUpdating) {
        return;
    }

    isFaceOverlayUpdating = true;
    try {
        const result = await apiSilent('/api/face/detect');
        if (!result) {
            faceOverlayState.faces = [];
            drawFaceOverlay();
            return;
        }

        faceOverlayState.faces = result.faces || [];
        faceOverlayState.frameWidth = result.frame_width || 0;
        faceOverlayState.frameHeight = result.frame_height || 0;
        faceOverlayState.overlayRegion = result.overlay_region || null;
        drawFaceOverlay();
    } finally {
        isFaceOverlayUpdating = false;
    }
}

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
        log(`❌ 注册失败: ${error.message || error}`);
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
        const status = await apiSilent('/api/face/tracking/status');
        if (!status) {
            if (elements.currentFace) {
                elements.currentFace.style.display = 'none';
            }
            return;
        }
        
        if (status.is_face_tracking && status.current_face) {
            if (elements.currentFace) {
                elements.currentFace.style.display = 'block';
            }
            if (elements.currentFaceName) {
                elements.currentFaceName.textContent = status.current_face.name;
            }
            drawFaceOverlay();
        } else {
            if (elements.currentFace) {
                elements.currentFace.style.display = 'none';
            }
        }
    } catch (error) {
        // 静默失败
    }
}
