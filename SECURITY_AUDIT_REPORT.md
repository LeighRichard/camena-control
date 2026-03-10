# 相机位置控制系统 - 安全审计报告

**生成时间**: 2026-02-25  
**审计范围**: 全系统安全漏洞和问题检查  
**严重程度分级**: 🔴 严重 | 🟠 高危 | 🟡 中危 | 🔵 低危 | ⚪ 信息

---

## 执行摘要

本次安全审计发现了 **15 个安全问题**，其中包括：
- 🔴 严重问题: 2 个
- 🟠 高危问题: 5 个
- 🟡 中危问题: 4 个
- 🔵 低危问题: 3 个
- ⚪ 信息提示: 1 个

主要风险集中在：
1. **身份认证与授权**：默认密码、弱密码策略
2. **输入验证**：缺少输入验证和边界检查
3. **配置安全**：明文密码、敏感信息泄露
4. **通信安全**：缺少加密、重放攻击风险
5. **Web 安全**：XSS、CSRF、文件上传漏洞

---

## 1. 身份认证与授权问题

### 🔴 CRITICAL-001: 硬编码默认密码

**文件**: `jetson/src/network/auth.py`  
**位置**: 第 45-48 行

**问题描述**:
```python
# 默认用户（首次启动时创建）
DEFAULT_USERS = {
    "admin": ("admin123", UserRole.ADMIN),  # ⚠️ 硬编码默认密码
}
```


**风险**:
- 攻击者可以使用默认凭据 `admin/admin123` 获取系统完全控制权
- 默认密码在代码中公开，任何人都可以查看
- 用户可能忘记修改默认密码

**影响范围**:
- 完全控制相机系统
- 访问所有 API 端点
- 修改系统配置
- 控制相机运动

**修复建议**:
1. **强制首次登录修改密码**
2. **生成随机初始密码**并通过安全渠道告知用户
3. **密码复杂度要求**：至少 12 位，包含大小写字母、数字、特殊字符
4. **密码过期策略**：90 天强制更换

**修复代码示例**:
```python
import secrets
import string

def generate_secure_password(length=16):
    """生成安全的随机密码"""
    alphabet = string.ascii_letters + string.digits + string.punctuation
    password = ''.join(secrets.choice(alphabet) for _ in range(length))
    return password

# 首次启动时生成并保存到安全位置
initial_password = generate_secure_password()
print(f"初始管理员密码: {initial_password}")
print("请立即登录并修改密码！")
```

---

### 🟠 HIGH-002: 弱密码策略

**文件**: `jetson/src/network/auth.py`  
**位置**: `change_password()` 方法

**问题描述**:
密码修改功能没有任何密码强度验证，允许用户设置弱密码如 "123456"。

**风险**:
- 暴力破解攻击
- 字典攻击
- 社会工程学攻击

**修复建议**:
```python
import re

def validate_password_strength(password: str) -> Tuple[bool, str]:
    """验证密码强度"""
    if len(password) < 12:
        return False, "密码长度至少 12 位"
    
    if not re.search(r'[A-Z]', password):
        return False, "密码必须包含大写字母"
    
    if not re.search(r'[a-z]', password):
        return False, "密码必须包含小写字母"
    
    if not re.search(r'\d', password):
        return False, "密码必须包含数字"
    
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, "密码必须包含特殊字符"
    
    # 检查常见弱密码
    common_passwords = ['password', '12345678', 'admin123', 'qwerty']
    if password.lower() in common_passwords:
        return False, "密码过于常见，请使用更复杂的密码"
    
    return True, ""
```

---

### 🟠 HIGH-003: 缺少登录失败限制

**文件**: `jetson/src/network/auth.py`  
**位置**: `login()` 方法

**问题描述**:
登录功能没有失败次数限制，允许无限次尝试登录。

**风险**:
- 暴力破解攻击
- 账户枚举攻击
- 拒绝服务攻击

**修复建议**:
```python
from collections import defaultdict
from datetime import datetime, timedelta

class AuthManager:
    def __init__(self):
        self._login_attempts = defaultdict(list)  # IP -> [timestamp, ...]
        self._max_attempts = 5
        self._lockout_duration = timedelta(minutes=15)
    
    def _check_rate_limit(self, ip: str) -> Tuple[bool, str]:
        """检查登录速率限制"""
        now = datetime.now()
        
        # 清理过期记录
        self._login_attempts[ip] = [
            t for t in self._login_attempts[ip]
            if now - t < self._lockout_duration
        ]
        
        # 检查是否超过限制
        if len(self._login_attempts[ip]) >= self._max_attempts:
            return False, f"登录失败次数过多，请 {self._lockout_duration.seconds // 60} 分钟后重试"
        
        return True, ""
    
    def login(self, username: str, password: str, ip: str = None) -> Optional[str]:
        """用户登录（带速率限制）"""
        if ip:
            allowed, message = self._check_rate_limit(ip)
            if not allowed:
                logger.warning(f"登录速率限制触发: {ip}")
                return None
        
        # 验证用户名和密码
        if not self._verify_credentials(username, password):
            if ip:
                self._login_attempts[ip].append(datetime.now())
            return None
        
        # 登录成功，清除失败记录
        if ip and ip in self._login_attempts:
            del self._login_attempts[ip]
        
        return self._generate_token(username)
```

---

### 🟡 MEDIUM-004: JWT 密钥管理不当

**文件**: `jetson/src/web/app.py`  
**位置**: 第 42 行

**问题描述**:
```python
secret_key: str = "camera-control-secret"  # ⚠️ 硬编码密钥
```

JWT 密钥硬编码在代码中，所有部署使用相同密钥。

**风险**:
- 攻击者可以伪造 JWT token
- 无法撤销已泄露的密钥
- 跨系统 token 重放攻击

**修复建议**:
1. **从环境变量或配置文件读取密钥**
2. **每个部署使用唯一密钥**
3. **定期轮换密钥**

```python
import os
import secrets

# 从环境变量读取，如果不存在则生成
JWT_SECRET = os.getenv('JWT_SECRET_KEY')
if not JWT_SECRET:
    JWT_SECRET = secrets.token_urlsafe(32)
    logger.warning("未设置 JWT_SECRET_KEY 环境变量，已生成临时密钥")
    logger.warning(f"请将以下密钥添加到环境变量: {JWT_SECRET}")
```

---

## 2. 输入验证问题

### 🟠 HIGH-005: API 输入验证不足

**文件**: `jetson/src/web/app.py`  
**位置**: 多个 API 端点

**问题描述**:
多个 API 端点缺少输入验证，直接使用用户输入：

```python
@app.route("/api/motion/move", methods=["POST"])
def move_to():
    data = request.get_json()
    pan = data.get("pan")  # ⚠️ 未验证类型和范围
    tilt = data.get("tilt")
    rail = data.get("rail")
    
    # 直接使用可能导致类型错误或越界
    cmd = Command(value=int(pan * 100))
```

**风险**:
- 类型错误导致崩溃
- 越界值导致硬件损坏
- 注入攻击

**修复建议**:
```python
def validate_motion_params(pan=None, tilt=None, rail=None) -> Tuple[bool, str]:
    """验证运动参数"""
    if pan is not None:
        if not isinstance(pan, (int, float)):
            return False, "pan 必须是数字"
        if not -180 <= pan <= 180:
            return False, "pan 超出范围 [-180, 180]"
    
    if tilt is not None:
        if not isinstance(tilt, (int, float)):
            return False, "tilt 必须是数字"
        if not -90 <= tilt <= 90:
            return False, "tilt 超出范围 [-90, 90]"
    
    if rail is not None:
        if not isinstance(rail, (int, float)):
            return False, "rail 必须是数字"
        if not 0 <= rail <= 1000:
            return False, "rail 超出范围 [0, 1000]"
    
    return True, ""

@app.route("/api/motion/move", methods=["POST"])
def move_to():
    data = request.get_json()
    if not data:
        return jsonify({"error": "缺少请求数据"}), 400
    
    pan = data.get("pan")
    tilt = data.get("tilt")
    rail = data.get("rail")
    
    # 验证输入
    valid, error = validate_motion_params(pan, tilt, rail)
    if not valid:
        return jsonify({"error": error}), 400
    
    # 继续处理...
```

---

### 🟡 MEDIUM-006: 文件上传缺少验证

**文件**: `jetson/src/web/app.py`  
**位置**: `/api/face/register` 端点

**问题描述**:
```python
if 'image' in request.files:
    file = request.files['image']
    image = Image.open(io.BytesIO(file.read()))  # ⚠️ 未验证文件类型和大小
```

**风险**:
- 上传恶意文件（病毒、木马）
- 上传超大文件导致 DoS
- 文件类型混淆攻击

**修复建议**:
```python
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

def allowed_file(filename):
    """检查文件扩展名"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_image_file(file) -> Tuple[bool, str]:
    """验证图像文件"""
    # 检查文件名
    if not file.filename:
        return False, "文件名为空"
    
    if not allowed_file(file.filename):
        return False, f"不支持的文件类型，仅支持: {', '.join(ALLOWED_EXTENSIONS)}"
    
    # 检查文件大小
    file.seek(0, 2)  # 移动到文件末尾
    size = file.tell()
    file.seek(0)  # 重置到开头
    
    if size > MAX_FILE_SIZE:
        return False, f"文件过大，最大支持 {MAX_FILE_SIZE // (1024*1024)}MB"
    
    # 验证文件内容（防止扩展名欺骗）
    try:
        from PIL import Image
        img = Image.open(file)
        img.verify()  # 验证是否为有效图像
        file.seek(0)  # 重置
        return True, ""
    except Exception as e:
        return False, f"无效的图像文件: {str(e)}"

@app.route("/api/face/register", methods=["POST"])
def register_face():
    if 'image' in request.files:
        file = request.files['image']
        
        # 验证文件
        valid, error = validate_image_file(file)
        if not valid:
            return jsonify({"error": error}), 400
        
        # 继续处理...
```

---


## 3. 配置安全问题

### 🔴 CRITICAL-007: 配置文件包含明文密码

**文件**: `jetson/config/remote_access.yaml`  
**位置**: 第 8-10 行

**问题描述**:
```yaml
auth:
  username: "admin"
  password: "your_secure_password"  # ⚠️ 明文密码
```

**风险**:
- 密码泄露
- 版本控制系统中暴露密码
- 配置文件被未授权访问

**修复建议**:
1. **使用环境变量存储密码**
2. **使用密钥管理服务**（如 HashiCorp Vault）
3. **加密配置文件**

```python
import os
from cryptography.fernet import Fernet

# 方案 1: 环境变量
password = os.getenv('REMOTE_ACCESS_PASSWORD')
if not password:
    raise ValueError("未设置 REMOTE_ACCESS_PASSWORD 环境变量")

# 方案 2: 加密配置文件
def load_encrypted_config(config_path, key_path):
    """加载加密的配置文件"""
    with open(key_path, 'rb') as f:
        key = f.read()
    
    fernet = Fernet(key)
    
    with open(config_path, 'rb') as f:
        encrypted_data = f.read()
    
    decrypted_data = fernet.decrypt(encrypted_data)
    return yaml.safe_load(decrypted_data)
```

**配置文件修改**:
```yaml
auth:
  username: "admin"
  password_env: "REMOTE_ACCESS_PASSWORD"  # 从环境变量读取
```

---

### 🟠 HIGH-008: 敏感信息日志泄露

**文件**: 多个模块  
**位置**: 日志输出

**问题描述**:
日志中可能包含敏感信息（密码、token、个人信息）。

**风险**:
- 日志文件泄露导致凭据暴露
- 调试信息包含敏感数据
- 日志聚合系统中的数据泄露

**修复建议**:
```python
import re
import logging

class SensitiveDataFilter(logging.Filter):
    """过滤日志中的敏感数据"""
    
    PATTERNS = [
        (re.compile(r'password["\']?\s*[:=]\s*["\']?([^"\'}\s]+)', re.I), 'password=***'),
        (re.compile(r'token["\']?\s*[:=]\s*["\']?([^"\'}\s]+)', re.I), 'token=***'),
        (re.compile(r'Bearer\s+([A-Za-z0-9\-._~+/]+=*)', re.I), 'Bearer ***'),
        (re.compile(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b'), '****-****-****-****'),  # 信用卡
    ]
    
    def filter(self, record):
        """过滤敏感数据"""
        message = record.getMessage()
        
        for pattern, replacement in self.PATTERNS:
            message = pattern.sub(replacement, message)
        
        record.msg = message
        return True

# 应用过滤器
logger = logging.getLogger(__name__)
logger.addFilter(SensitiveDataFilter())
```

---

### 🟡 MEDIUM-009: 调试模式在生产环境启用

**文件**: `jetson/src/web/app.py`  
**位置**: WebConfig

**问题描述**:
```python
debug: bool = False  # 默认关闭，但可能被配置启用
```

**风险**:
- 详细错误信息泄露系统内部结构
- 调试端点暴露
- 性能下降

**修复建议**:
```python
import os

# 强制生产环境禁用调试模式
DEBUG_MODE = os.getenv('FLASK_ENV') == 'development'

if DEBUG_MODE and os.getenv('PRODUCTION') == 'true':
    raise ValueError("生产环境不允许启用调试模式！")

app.config['DEBUG'] = DEBUG_MODE
```

---

## 4. 通信安全问题

### 🟠 HIGH-010: 串口通信缺少加密

**文件**: `stm32/CameraControl/Core/Src/protocol.c`  
**位置**: 整个协议实现

**问题描述**:
STM32 与 Jetson 之间的串口通信使用明文协议，没有加密保护。

**风险**:
- 窃听攻击（嗅探串口数据）
- 中间人攻击
- 命令注入攻击

**修复建议**:
1. **添加 AES 加密层**
2. **使用 HMAC 进行消息认证**
3. **实现挑战-响应认证**

```c
// 简化的加密通信示例
#include "aes.h"
#include "hmac.h"

typedef struct {
    uint8_t encrypted_data[256];
    uint8_t hmac[32];
    uint8_t iv[16];
} SecureFrame;

bool send_secure_command(Command* cmd, const uint8_t* key) {
    SecureFrame frame;
    
    // 1. 序列化命令
    uint8_t plaintext[64];
    size_t len = serialize_command(cmd, plaintext);
    
    // 2. 生成随机 IV
    generate_random_iv(frame.iv, 16);
    
    // 3. AES 加密
    aes_encrypt(plaintext, len, key, frame.iv, frame.encrypted_data);
    
    // 4. 计算 HMAC
    hmac_sha256(frame.encrypted_data, len, key, frame.hmac);
    
    // 5. 发送
    return uart_send(&frame, sizeof(frame));
}
```

---

### 🟡 MEDIUM-011: 缺少重放攻击防护

**文件**: `stm32/CameraControl/Core/Src/protocol.c`  
**位置**: `cmd_parse()` 函数

**问题描述**:
协议虽然有序列号，但没有验证序列号的单调性，允许重放旧命令。

**风险**:
- 攻击者可以捕获并重放命令
- 绕过访问控制
- 造成意外的设备行为

**修复建议**:
```c
// 添加序列号验证
static uint8_t last_valid_seq = 0;

ParseResult cmd_parse(const uint8_t* buffer, size_t len, Command* out) {
    // ... 现有解析逻辑 ...
    
    // 验证序列号（必须递增）
    if (out->seq <= last_valid_seq) {
        return PARSE_ERROR_REPLAY;  // 检测到重放攻击
    }
    
    last_valid_seq = out->seq;
    return PARSE_OK;
}

// 添加时间戳验证
typedef struct {
    uint8_t seq;
    uint32_t timestamp;  // Unix 时间戳
    // ... 其他字段
} CommandV3;

bool validate_timestamp(uint32_t cmd_timestamp) {
    uint32_t current_time = get_system_time();
    uint32_t time_diff = abs(current_time - cmd_timestamp);
    
    // 允许 5 秒时间窗口
    return time_diff < 5;
}
```

---

### 🔵 LOW-012: HTTP 未强制 HTTPS

**文件**: `jetson/src/web/app.py`  
**位置**: WebConfig

**问题描述**:
Web 服务默认使用 HTTP，HTTPS 需要手动配置。

**风险**:
- 中间人攻击
- 凭据在网络中明文传输
- 会话劫持

**修复建议**:
```python
# 强制 HTTPS 重定向
from flask import redirect, request

@app.before_request
def force_https():
    """强制 HTTPS"""
    if not request.is_secure and not app.config['DEBUG']:
        url = request.url.replace('http://', 'https://', 1)
        return redirect(url, code=301)

# 添加安全响应头
@app.after_request
def add_security_headers(response):
    """添加安全响应头"""
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Content-Security-Policy'] = "default-src 'self'"
    return response
```

---

## 5. Web 安全问题

### 🟡 MEDIUM-013: 跨站脚本攻击 (XSS)

**文件**: `jetson/src/web/static/index.html` 和 `app.js`  
**位置**: 多处动态内容插入

**问题描述**:
```javascript
// app.js 中的不安全 HTML 插入
elements.targetList.innerHTML = targets.map(t => `
    <div class="target-item">
        <span class="target-name">#${t.id} ${t.class_name}</span>  // ⚠️ 未转义
    </div>
`).join('');
```

**风险**:
- 注入恶意脚本
- 窃取用户 cookie 和 token
- 钓鱼攻击

**修复建议**:
```javascript
// 添加 HTML 转义函数
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// 安全的内容插入
elements.targetList.innerHTML = targets.map(t => `
    <div class="target-item">
        <span class="target-name">#${escapeHtml(t.id)} ${escapeHtml(t.class_name)}</span>
    </div>
`).join('');

// 或使用 DOM API（更安全）
function createTargetElement(target) {
    const div = document.createElement('div');
    div.className = 'target-item';
    
    const span = document.createElement('span');
    span.className = 'target-name';
    span.textContent = `#${target.id} ${target.class_name}`;  // 自动转义
    
    div.appendChild(span);
    return div;
}
```

---

### 🔵 LOW-014: 跨站请求伪造 (CSRF)

**文件**: `jetson/src/web/app.py`  
**位置**: 所有 POST/PUT/DELETE 端点

**问题描述**:
API 端点没有 CSRF 保护，允许跨站请求。

**风险**:
- 攻击者可以诱导用户执行非预期操作
- 状态修改攻击

**修复建议**:
```python
from flask_wtf.csrf import CSRFProtect

# 启用 CSRF 保护
csrf = CSRFProtect(app)

# 对于 API，使用自定义 token
@app.before_request
def csrf_protect():
    if request.method in ['POST', 'PUT', 'DELETE', 'PATCH']:
        # 检查 CSRF token
        token = request.headers.get('X-CSRF-Token')
        if not token or not validate_csrf_token(token):
            return jsonify({"error": "CSRF token 无效"}), 403

# 生成 CSRF token
@app.route("/api/csrf-token", methods=["GET"])
def get_csrf_token():
    token = generate_csrf_token()
    return jsonify({"csrf_token": token})
```

前端修改：
```javascript
// 获取 CSRF token
let csrfToken = null;

async function getCsrfToken() {
    const response = await fetch('/api/csrf-token');
    const data = await response.json();
    csrfToken = data.csrf_token;
}

// 在所有请求中包含 CSRF token
async function api(endpoint, method = 'GET', data = null) {
    const options = {
        method,
        headers: {
            'Content-Type': 'application/json',
            'X-CSRF-Token': csrfToken  // 添加 CSRF token
        }
    };
    // ...
}

// 初始化时获取 token
getCsrfToken();
```

---

### 🔵 LOW-015: 缺少速率限制

**文件**: `jetson/src/web/app.py`  
**位置**: 所有 API 端点

**问题描述**:
API 端点没有速率限制，允许无限制请求。

**风险**:
- 拒绝服务攻击 (DoS)
- 资源耗尽
- 暴力破解攻击

**修复建议**:
```python
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# 创建限流器
limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

# 对敏感端点应用更严格的限制
@app.route("/api/auth/login", methods=["POST"])
@limiter.limit("5 per minute")  # 每分钟最多 5 次登录尝试
def login():
    # ...

@app.route("/api/camera/capture", methods=["POST"])
@limiter.limit("30 per minute")  # 每分钟最多 30 次拍摄
def capture():
    # ...

@app.route("/api/motion/move", methods=["POST"])
@limiter.limit("60 per minute")  # 每分钟最多 60 次运动命令
def move_to():
    # ...
```

---


## 6. 其他安全建议

### ⚪ INFO-016: 安全最佳实践建议

**1. 依赖项安全扫描**
```bash
# 定期扫描 Python 依赖漏洞
pip install safety
safety check

# 扫描 npm 依赖漏洞
cd desktop_app
npm audit

cd ../mobile_app
flutter pub outdated
```

**2. 代码安全扫描**
```bash
# Python 代码安全扫描
pip install bandit
bandit -r jetson/src/

# JavaScript 代码扫描
npm install -g eslint eslint-plugin-security
eslint desktop_app/src/
```

**3. 容器安全**（如果使用 Docker）
```bash
# 扫描 Docker 镜像漏洞
docker scan camera-control:latest

# 使用最小化基础镜像
FROM python:3.14-slim  # 而不是 python:3.14
```

**4. 网络安全**
- 使用防火墙限制端口访问
- 仅允许必要的入站连接
- 使用 VPN 进行远程访问

**5. 物理安全**
- 保护 Jetson Nano 和 STM32 设备的物理访问
- 禁用不必要的 USB 端口
- 使用安全启动（Secure Boot）

**6. 日志和监控**
```python
# 记录安全事件
import logging

security_logger = logging.getLogger('security')
security_logger.setLevel(logging.WARNING)

# 记录可疑活动
def log_security_event(event_type, details):
    security_logger.warning(f"安全事件: {event_type} - {details}")

# 示例：记录登录失败
if not verify_credentials(username, password):
    log_security_event('LOGIN_FAILED', f'用户: {username}, IP: {ip}')
```

**7. 备份和恢复**
- 定期备份配置文件和数据库
- 测试恢复流程
- 加密备份数据

**8. 安全更新**
- 定期更新操作系统和依赖包
- 订阅安全公告
- 建立补丁管理流程

---

## 7. 修复优先级建议

### 立即修复（1-3 天）
1. 🔴 **CRITICAL-001**: 修改默认密码，实施强密码策略
2. 🔴 **CRITICAL-007**: 移除配置文件中的明文密码
3. 🟠 **HIGH-002**: 实施密码强度验证
4. 🟠 **HIGH-003**: 添加登录失败限制

### 短期修复（1-2 周）
5. 🟠 **HIGH-005**: 添加 API 输入验证
6. 🟠 **HIGH-008**: 实施敏感数据日志过滤
7. 🟠 **HIGH-010**: 评估串口通信加密需求
8. 🟡 **MEDIUM-004**: 改进 JWT 密钥管理

### 中期修复（1 个月）
9. 🟡 **MEDIUM-006**: 完善文件上传验证
10. 🟡 **MEDIUM-009**: 确保生产环境配置安全
11. 🟡 **MEDIUM-011**: 实施重放攻击防护
12. 🟡 **MEDIUM-013**: 修复 XSS 漏洞

### 长期改进（持续）
13. 🔵 **LOW-012**: 强制 HTTPS
14. 🔵 **LOW-014**: 实施 CSRF 保护
15. 🔵 **LOW-015**: 添加 API 速率限制
16. ⚪ **INFO-016**: 建立安全开发流程

---

## 8. 安全检查清单

### 部署前检查
- [ ] 修改所有默认密码
- [ ] 禁用调试模式
- [ ] 启用 HTTPS
- [ ] 配置防火墙规则
- [ ] 移除测试账户
- [ ] 验证文件权限
- [ ] 检查日志配置
- [ ] 测试备份恢复

### 运行时监控
- [ ] 监控登录失败次数
- [ ] 检测异常 API 调用
- [ ] 监控系统资源使用
- [ ] 审计安全日志
- [ ] 检查证书过期时间

### 定期审计
- [ ] 每月：依赖项安全扫描
- [ ] 每季度：代码安全审计
- [ ] 每半年：渗透测试
- [ ] 每年：全面安全评估

---

## 9. 安全联系方式

如发现新的安全问题，请通过以下方式报告：

**安全邮箱**: security@example.com  
**PGP 公钥**: [链接]  
**漏洞奖励计划**: [链接]

**响应时间承诺**:
- 严重漏洞：24 小时内响应
- 高危漏洞：48 小时内响应
- 中低危漏洞：7 天内响应

---

## 10. 参考资源

### 安全标准
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [CWE Top 25](https://cwe.mitre.org/top25/)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)

### 工具推荐
- **代码扫描**: Bandit, ESLint, SonarQube
- **依赖扫描**: Safety, npm audit, Snyk
- **渗透测试**: OWASP ZAP, Burp Suite
- **密码管理**: HashiCorp Vault, AWS Secrets Manager

### 学习资源
- [OWASP Cheat Sheet Series](https://cheatsheetseries.owasp.org/)
- [Python Security Best Practices](https://python.readthedocs.io/en/stable/library/security_warnings.html)
- [Flask Security](https://flask.palletsprojects.com/en/2.3.x/security/)

---

## 附录 A: 快速修复脚本

### A.1 生成安全配置

```python
#!/usr/bin/env python3
"""
生成安全配置文件
"""
import secrets
import string
import yaml
from pathlib import Path

def generate_secure_password(length=16):
    """生成安全密码"""
    alphabet = string.ascii_letters + string.digits + string.punctuation
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def generate_jwt_secret():
    """生成 JWT 密钥"""
    return secrets.token_urlsafe(32)

def create_secure_config():
    """创建安全配置"""
    config = {
        'admin_password': generate_secure_password(),
        'jwt_secret': generate_jwt_secret(),
        'csrf_secret': secrets.token_hex(32),
        'encryption_key': secrets.token_urlsafe(32)
    }
    
    # 保存到文件
    config_path = Path('.env.secure')
    with open(config_path, 'w') as f:
        for key, value in config.items():
            f.write(f"{key.upper()}={value}\n")
    
    # 设置文件权限（仅所有者可读写）
    config_path.chmod(0o600)
    
    print("✅ 安全配置已生成: .env.secure")
    print("⚠️  请妥善保管此文件，不要提交到版本控制系统！")
    print("\n初始管理员密码:")
    print(f"  用户名: admin")
    print(f"  密码: {config['admin_password']}")
    print("\n请立即登录并修改密码！")

if __name__ == '__main__':
    create_secure_config()
```

### A.2 安全检查脚本

```bash
#!/bin/bash
# security_check.sh - 快速安全检查

echo "🔍 开始安全检查..."

# 1. 检查默认密码
echo "\n[1/6] 检查默认密码..."
if grep -r "admin123" jetson/src/ > /dev/null; then
    echo "❌ 发现默认密码！请立即修改"
else
    echo "✅ 未发现默认密码"
fi

# 2. 检查明文密码
echo "\n[2/6] 检查配置文件中的明文密码..."
if grep -r "password:" jetson/config/*.yaml | grep -v "password_env" > /dev/null; then
    echo "⚠️  发现可能的明文密码"
    grep -r "password:" jetson/config/*.yaml | grep -v "password_env"
else
    echo "✅ 未发现明文密码"
fi

# 3. 检查调试模式
echo "\n[3/6] 检查调试模式..."
if grep "debug.*=.*True" jetson/src/web/app.py > /dev/null; then
    echo "⚠️  发现启用的调试模式"
else
    echo "✅ 调试模式已禁用"
fi

# 4. 检查文件权限
echo "\n[4/6] 检查敏感文件权限..."
for file in jetson/config/*.yaml .env*; do
    if [ -f "$file" ]; then
        perms=$(stat -c "%a" "$file" 2>/dev/null || stat -f "%A" "$file" 2>/dev/null)
        if [ "$perms" != "600" ] && [ "$perms" != "400" ]; then
            echo "⚠️  $file 权限过于宽松: $perms"
        fi
    fi
done
echo "✅ 文件权限检查完成"

# 5. 检查依赖漏洞
echo "\n[5/6] 检查 Python 依赖漏洞..."
if command -v safety &> /dev/null; then
    cd jetson && safety check --json > /dev/null 2>&1
    if [ $? -eq 0 ]; then
        echo "✅ 未发现已知漏洞"
    else
        echo "⚠️  发现依赖漏洞，运行 'safety check' 查看详情"
    fi
else
    echo "⚠️  未安装 safety，跳过检查"
fi

# 6. 检查 HTTPS 配置
echo "\n[6/6] 检查 HTTPS 配置..."
if grep -r "ssl.*enabled.*true" jetson/config/*.yaml > /dev/null; then
    echo "✅ HTTPS 已启用"
else
    echo "⚠️  HTTPS 未启用，建议在生产环境启用"
fi

echo "\n✅ 安全检查完成！"
```

---

## 附录 B: 安全配置模板

### B.1 生产环境配置

```yaml
# jetson/config/system_config.production.yaml
# 生产环境安全配置

# Web 服务配置
web:
  enabled: true
  host: "0.0.0.0"
  port: 443  # HTTPS 端口
  enable_auth: true  # 强制启用认证
  debug: false  # 禁用调试模式
  
  # SSL/TLS 配置
  ssl:
    enabled: true
    cert_file: "/etc/ssl/certs/camera-control.crt"
    key_file: "/etc/ssl/private/camera-control.key"
  
  # 安全响应头
  security_headers:
    strict_transport_security: "max-age=31536000; includeSubDomains"
    x_content_type_options: "nosniff"
    x_frame_options: "DENY"
    x_xss_protection: "1; mode=block"
    content_security_policy: "default-src 'self'"

# 认证配置
auth:
  # 从环境变量读取
  admin_password_env: "ADMIN_PASSWORD"
  jwt_secret_env: "JWT_SECRET_KEY"
  
  # 密码策略
  password_policy:
    min_length: 12
    require_uppercase: true
    require_lowercase: true
    require_digits: true
    require_special: true
    expiry_days: 90
  
  # 登录限制
  rate_limit:
    max_attempts: 5
    lockout_duration_minutes: 15
  
  # Token 配置
  token:
    expiry_hours: 24
    refresh_enabled: true
    refresh_expiry_days: 7

# 日志配置
logging:
  level: "INFO"
  sensitive_data_filter: true
  max_file_size_mb: 100
  backup_count: 10
  
  # 安全日志单独记录
  security_log:
    enabled: true
    file: "/var/log/camera-control/security.log"
    level: "WARNING"

# 备份配置
backup:
  enabled: true
  schedule: "0 2 * * *"  # 每天凌晨 2 点
  retention_days: 30
  encryption: true
  encryption_key_env: "BACKUP_ENCRYPTION_KEY"
```

### B.2 环境变量模板

```bash
# .env.production
# 生产环境环境变量（不要提交到版本控制！）

# 管理员凭据
ADMIN_PASSWORD=<生成的安全密码>

# JWT 密钥
JWT_SECRET_KEY=<生成的随机密钥>

# CSRF 密钥
CSRF_SECRET_KEY=<生成的随机密钥>

# 数据库加密密钥
DB_ENCRYPTION_KEY=<生成的随机密钥>

# 备份加密密钥
BACKUP_ENCRYPTION_KEY=<生成的随机密钥>

# 远程访问密码
REMOTE_ACCESS_PASSWORD=<生成的安全密码>

# 生产环境标识
PRODUCTION=true
FLASK_ENV=production
```

---

**报告结束**

如有任何疑问或需要进一步协助，请联系安全团队。
