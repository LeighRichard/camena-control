@echo off
REM 一键部署脚本 - 智能相机位置控制系统
REM 适用于 Windows 系统

setlocal enabledelayedexpansion

REM 颜色代码（Windows 10+）
set "GREEN=[92m"
set "YELLOW=[93m"
set "RED=[91m"
set "BLUE=[94m"
set "NC=[0m"

REM 显示横幅
echo ========================================
echo   智能相机位置控制系统 - 一键部署
echo   Smart Camera Position Control System
echo ========================================
echo.

REM 日志函数
goto :main

:log_info
echo %BLUE%[INFO]%NC% %~1
goto :eof

:log_success
echo %GREEN%[SUCCESS]%NC% %~1
goto :eof

:log_warning
echo %YELLOW%[WARNING]%NC% %~1
goto :eof

:log_error
echo %RED%[ERROR]%NC% %~1
goto :eof

REM 检查 Python
:check_python
call :log_info "检查 Python 版本..."

REM 仅支持 Python 3.6（TensorRT 要求）
python --version >nul 2>&1
if errorlevel 1 (
    call :log_error "未找到 Python"
    call :log_error "本项目仅支持 Python 3.6（TensorRT 要求）"
    call :log_info ""
    call :log_info "注意: 本项目仅支持 Jetson 平台"
    call :log_info "Windows 不支持 TensorRT"
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
for /f "tokens=1,2 delims=." %%a in ("%PYTHON_VERSION%") do (
    set PYTHON_MAJOR=%%a
    set PYTHON_MINOR=%%b
)

if %PYTHON_MAJOR% equ 3 (
    if %PYTHON_MINOR% equ 6 (
        set PYTHON_CMD=python
        call :log_success "Python 3.6 已找到: %PYTHON_VERSION%"
        call :log_warning "注意: Windows 不支持 TensorRT"
        call :log_info "本项目仅支持 Jetson 平台"
        goto :eof
    )
)

call :log_error "本项目仅支持 Python 3.6（TensorRT 要求）"
call :log_error "当前版本: %PYTHON_VERSION%"
call :log_info ""
call :log_info "注意: 本项目仅支持 Jetson 平台"
pause
exit /b 1

REM 创建虚拟环境
:create_virtualenv
call :log_info "创建 Python 虚拟环境..."

if exist venv (
    call :log_warning "虚拟环境已存在，跳过创建"
) else (
    %PYTHON_CMD% -m venv venv
    call :log_success "虚拟环境创建完成"
)

REM 激活虚拟环境
call venv\Scripts\activate.bat
call :log_info "已激活虚拟环境"
goto :eof

REM 安装 Python 依赖
:install_dependencies
call :log_info "安装 Python 依赖..."

REM 升级 pip
python -m pip install --upgrade pip setuptools wheel

REM 安装依赖
if exist requirements.txt (
    call :log_info "安装 requirements.txt 中的依赖..."
    pip install -r requirements.txt
) else (
    call :log_error "未找到 requirements.txt"
    pause
    exit /b 1
)

REM 检测 GPU
call :log_info "检测 GPU..."
nvidia-smi >nul 2>&1
if errorlevel 1 (
    call :log_info "未检测到 NVIDIA GPU，安装 CPU 版本..."
    pip install onnxruntime
) else (
    call :log_info "检测到 NVIDIA GPU，安装 GPU 版本..."
    pip install onnxruntime-gpu
)

call :log_success "Python 依赖安装完成"
goto :eof

REM 安装相机 SDK
:install_camera_sdk
call :log_info "安装相机 SDK..."

set /p install_realsense="是否安装 Intel RealSense SDK? (y/n): "
if /i "%install_realsense%"=="y" (
    call :log_info "安装 pyrealsense2..."
    pip install pyrealsense2 || call :log_warning "pyrealsense2 安装失败"
)

set /p install_orbbec="是否安装 Orbbec SDK? (y/n): "
if /i "%install_orbbec%"=="y" (
    call :log_info "安装 pyorbbecsdk..."
    pip install pyorbbecsdk || call :log_warning "pyorbbecsdk 安装失败"
)

call :log_success "相机 SDK 安装完成"
goto :eof

REM 创建目录
:create_directories
call :log_info "创建必要的目录..."

if not exist models mkdir models
if not exist logs mkdir logs
if not exist data mkdir data
if not exist config mkdir config

call :log_success "目录创建完成"
goto :eof

REM 配置系统
:configure_system
call :log_info "配置系统..."

if exist config\system_config.yaml.example (
    if not exist config\system_config.yaml (
        copy config\system_config.yaml.example config\system_config.yaml
        call :log_success "已创建配置文件: config\system_config.yaml"
    ) else (
        call :log_warning "配置文件已存在，跳过"
    )
)

if exist .env.example (
    if not exist .env (
        copy .env.example .env
        call :log_success "已创建环境变量文件: .env"
    ) else (
        call :log_warning "环境变量文件已存在，跳过"
    )
)

call :log_success "系统配置完成"
goto :eof

REM 运行测试
:run_tests
call :log_info "运行测试..."

set /p run_test="是否运行集成测试? (y/n): "
if /i "%run_test%"=="y" (
    call :log_info "运行 ONNX Runtime 集成测试..."
    python scripts\test_onnx_support.py

    call :log_info "运行单元测试..."
    pytest tests\ -v || call :log_warning "部分测试失败"
)

call :log_success "测试完成"
goto :eof

REM 创建启动脚本
:create_startup_script
call :log_info "创建启动脚本..."

(
echo @echo off
echo REM 启动脚本
echo call venv\Scripts\activate.bat
echo python main.py
) > start.bat

call :log_success "启动脚本创建完成: start.bat"
goto :eof

REM 显示总结
:show_summary
echo.
echo ========================================
echo   部署完成！
echo ========================================
echo.
echo 项目目录: %CD%
echo Python 环境: %CD%\venv\Scripts\python.exe
echo.
echo 快速开始:
echo   1. 激活虚拟环境: venv\Scripts\activate.bat
echo   2. 编辑配置文件: config\system_config.yaml
echo   3. 运行系统: python main.py
echo   或使用启动脚本: start.bat
echo.
echo 文档:
echo   - 快速开始: QUICKSTART_ONNX.md
echo   - 使用指南: docs\ONNX_RUNTIME_USAGE_GUIDE.md
echo   - 技术方案: docs\TENSORRT_PYTHON_COMPATIBILITY_SOLUTION.md
echo.
echo 工具:
echo   - 模型转换: python scripts\convert_to_onnx.py
echo   - 性能测试: python scripts\benchmark_detector.py
echo   - 集成测试: python scripts\test_onnx_support.py
echo.
echo GitHub: https://github.com/LeighRichard/camena-control
echo.
pause
goto :eof

REM 主函数
:main
call :check_python
call :create_virtualenv
call :install_dependencies
call :install_camera_sdk
call :create_directories
call :configure_system
call :run_tests
call :create_startup_script
call :show_summary
