"""
OTA 更新管理器

功能：
1. Jetson 端代码更新（Git pull 或下载包）
2. STM32 固件更新（通过串口烧录）
3. 配置文件更新
4. 回滚机制
"""

import os
import json
import shutil
import hashlib
import logging
import subprocess
import threading
import time
from pathlib import Path
from enum import Enum
from dataclasses import dataclass
from typing import Optional, Tuple, Callable, Dict, List
from datetime import datetime
from urllib.request import urlretrieve
from urllib.error import URLError

logger = logging.getLogger(__name__)


class UpdateStatus(Enum):
    """更新状态"""
    IDLE = "idle"
    CHECKING = "checking"
    DOWNLOADING = "downloading"
    INSTALLING = "installing"
    REBOOTING = "rebooting"
    SUCCESS = "success"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class UpdateType(Enum):
    """更新类型"""
    JETSON_CODE = "jetson_code"
    STM32_FIRMWARE = "stm32_firmware"
    CONFIG = "config"
    MODEL = "model"


@dataclass
class UpdateInfo:
    """更新信息"""
    version: str
    update_type: UpdateType
    description: str = ""
    download_url: str = ""
    file_size: int = 0
    md5_hash: str = ""
    release_date: str = ""
    is_critical: bool = False
    requires_reboot: bool = False
    
    def to_dict(self) -> dict:
        return {
            'version': self.version,
            'update_type': self.update_type.value,
            'description': self.description,
            'download_url': self.download_url,
            'file_size': self.file_size,
            'md5_hash': self.md5_hash,
            'release_date': self.release_date,
            'is_critical': self.is_critical,
            'requires_reboot': self.requires_reboot
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'UpdateInfo':
        data = data.copy()
        data['update_type'] = UpdateType(data['update_type'])
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class OTAManager:
    """
    OTA 更新管理器
    
    支持：
    - Git 仓库更新
    - 下载包更新
    - STM32 固件更新
    - 配置热更新
    - 自动回滚
    """
    
    def __init__(
        self,
        app_dir: str = ".",
        backup_dir: str = "backups",
        update_server: str = None
    ):
        self._app_dir = Path(app_dir).absolute()
        self._backup_dir = Path(backup_dir)
        self._backup_dir.mkdir(parents=True, exist_ok=True)
        
        self._update_server = update_server
        self._status = UpdateStatus.IDLE
        self._current_version = self._get_current_version()
        self._progress = 0.0
        self._error_message = ""
        
        # 更新历史
        self._history_file = self._backup_dir / "update_history.json"
        self._history: List[dict] = self._load_history()
        
        # 回调
        self._progress_callback: Optional[Callable[[float, str], None]] = None
        
        # 锁
        self._lock = threading.Lock()
    
    def _get_current_version(self) -> str:
        """获取当前版本"""
        version_file = self._app_dir / "VERSION"
        if version_file.exists():
            return version_file.read_text().strip()
        
        # 尝试从 Git 获取
        try:
            result = subprocess.run(
                ['git', 'describe', '--tags', '--always'],
                cwd=self._app_dir,
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            # 获取Git版本失败
            pass
        
        return "unknown"
    
    def _load_history(self) -> List[dict]:
        """加载更新历史"""
        if self._history_file.exists():
            try:
                with open(self._history_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                # JSON解析失败或文件读取失败
                pass
        return []
    
    def _save_history(self):
        """保存更新历史"""
        with open(self._history_file, 'w') as f:
            json.dump(self._history, f, indent=2)
    
    def _add_history(self, update_type: str, version: str, status: str, message: str = ""):
        """添加历史记录"""
        self._history.append({
            'timestamp': datetime.now().isoformat(),
            'type': update_type,
            'version': version,
            'status': status,
            'message': message
        })
        # 只保留最近 50 条
        self._history = self._history[-50:]
        self._save_history()
    
    # ==================== 状态查询 ====================
    
    def get_status(self) -> dict:
        """获取更新状态"""
        with self._lock:
            return {
                'status': self._status.value,
                'current_version': self._current_version,
                'progress': self._progress,
                'error_message': self._error_message
            }
    
    def get_current_version(self) -> str:
        """获取当前版本"""
        return self._current_version
    
    def get_history(self) -> List[dict]:
        """获取更新历史"""
        return self._history.copy()
    
    # ==================== 检查更新 ====================
    
    def check_update(self) -> Tuple[bool, Optional[UpdateInfo]]:
        """
        检查是否有可用更新
        
        Returns:
            (是否有更新, 更新信息)
        """
        with self._lock:
            self._status = UpdateStatus.CHECKING
        
        try:
            # 方式1: 检查 Git 远程
            if self._is_git_repo():
                has_update, info = self._check_git_update()
                if has_update:
                    return True, info
            
            # 方式2: 检查更新服务器
            if self._update_server:
                has_update, info = self._check_server_update()
                if has_update:
                    return True, info
            
            with self._lock:
                self._status = UpdateStatus.IDLE
            return False, None
            
        except Exception as e:
            logger.error(f"检查更新失败: {e}")
            with self._lock:
                self._status = UpdateStatus.FAILED
                self._error_message = str(e)
            return False, None
    
    def _is_git_repo(self) -> bool:
        """检查是否是 Git 仓库"""
        return (self._app_dir / ".git").exists()
    
    def _check_git_update(self) -> Tuple[bool, Optional[UpdateInfo]]:
        """检查 Git 更新"""
        try:
            # Fetch 远程
            subprocess.run(
                ['git', 'fetch', '--tags'],
                cwd=self._app_dir,
                capture_output=True
            )
            
            # 检查是否有新提交
            result = subprocess.run(
                ['git', 'rev-list', 'HEAD..origin/main', '--count'],
                cwd=self._app_dir,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                count = int(result.stdout.strip())
                if count > 0:
                    # 获取最新版本
                    result = subprocess.run(
                        ['git', 'describe', '--tags', 'origin/main'],
                        cwd=self._app_dir,
                        capture_output=True,
                        text=True
                    )
                    new_version = result.stdout.strip() if result.returncode == 0 else "latest"
                    
                    return True, UpdateInfo(
                        version=new_version,
                        update_type=UpdateType.JETSON_CODE,
                        description=f"{count} 个新提交可用"
                    )
            
            return False, None
            
        except Exception as e:
            logger.error(f"Git 检查失败: {e}")
            return False, None
    
    def _check_server_update(self) -> Tuple[bool, Optional[UpdateInfo]]:
        """检查服务器更新"""
        try:
            import urllib.request
            
            url = f"{self._update_server}/api/check?version={self._current_version}"
            with urllib.request.urlopen(url, timeout=10) as response:
                data = json.loads(response.read().decode())
            
            if data.get('has_update'):
                return True, UpdateInfo.from_dict(data['update_info'])
            
            return False, None
            
        except Exception as e:
            logger.error(f"服务器检查失败: {e}")
            return False, None
    
    # ==================== 执行更新 ====================
    
    def update_from_git(
        self, 
        branch: str = "main",
        progress_callback: Callable[[float, str], None] = None
    ) -> Tuple[bool, str]:
        """
        从 Git 更新
        
        Args:
            branch: 分支名
            progress_callback: 进度回调 (progress, message)
            
        Returns:
            (成功标志, 消息)
        """
        self._progress_callback = progress_callback
        
        with self._lock:
            self._status = UpdateStatus.DOWNLOADING
            self._progress = 0.0
        
        try:
            # 创建备份
            self._report_progress(0.1, "创建备份...")
            backup_path = self._create_backup()
            
            # 拉取更新
            self._report_progress(0.3, "拉取更新...")
            result = subprocess.run(
                ['git', 'pull', 'origin', branch],
                cwd=self._app_dir,
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                raise Exception(f"Git pull 失败: {result.stderr}")
            
            # 安装依赖
            self._report_progress(0.6, "安装依赖...")
            self._install_dependencies()
            
            # 验证
            self._report_progress(0.9, "验证更新...")
            if not self._verify_installation():
                raise Exception("安装验证失败")
            
            # 更新版本
            new_version = self._get_current_version()
            self._current_version = new_version
            
            self._report_progress(1.0, "更新完成")
            
            with self._lock:
                self._status = UpdateStatus.SUCCESS
            
            self._add_history("git", new_version, "success")
            
            return True, f"更新成功: {new_version}"
            
        except Exception as e:
            logger.error(f"Git 更新失败: {e}")
            
            # 回滚
            if backup_path:
                self._rollback(backup_path)
            
            with self._lock:
                self._status = UpdateStatus.FAILED
                self._error_message = str(e)
            
            self._add_history("git", "", "failed", str(e))
            
            return False, str(e)
    
    def update_from_package(
        self,
        package_url: str,
        expected_hash: str = None,
        progress_callback: Callable[[float, str], None] = None
    ) -> Tuple[bool, str]:
        """
        从下载包更新
        
        Args:
            package_url: 包下载地址
            expected_hash: 预期 MD5 哈希
            progress_callback: 进度回调
            
        Returns:
            (成功标志, 消息)
        """
        self._progress_callback = progress_callback
        
        with self._lock:
            self._status = UpdateStatus.DOWNLOADING
            self._progress = 0.0
        
        try:
            # 下载包
            self._report_progress(0.1, "下载更新包...")
            package_path = self._backup_dir / "update_package.tar.gz"
            
            def download_progress(block_num, block_size, total_size):
                if total_size > 0:
                    progress = 0.1 + 0.4 * (block_num * block_size / total_size)
                    self._report_progress(progress, "下载中...")
            
            urlretrieve(package_url, str(package_path), reporthook=download_progress)
            
            # 验证哈希
            if expected_hash:
                self._report_progress(0.5, "验证文件...")
                actual_hash = self._calculate_md5(package_path)
                if actual_hash != expected_hash:
                    raise Exception(f"哈希不匹配: {actual_hash} != {expected_hash}")
            
            # 创建备份
            self._report_progress(0.55, "创建备份...")
            backup_path = self._create_backup()
            
            # 解压安装
            self._report_progress(0.6, "安装更新...")
            self._extract_package(package_path)
            
            # 安装依赖
            self._report_progress(0.8, "安装依赖...")
            self._install_dependencies()
            
            # 验证
            self._report_progress(0.95, "验证安装...")
            if not self._verify_installation():
                raise Exception("安装验证失败")
            
            # 清理
            package_path.unlink()
            
            new_version = self._get_current_version()
            self._current_version = new_version
            
            self._report_progress(1.0, "更新完成")
            
            with self._lock:
                self._status = UpdateStatus.SUCCESS
            
            self._add_history("package", new_version, "success")
            
            return True, f"更新成功: {new_version}"
            
        except Exception as e:
            logger.error(f"包更新失败: {e}")
            
            if backup_path:
                self._rollback(backup_path)
            
            with self._lock:
                self._status = UpdateStatus.FAILED
                self._error_message = str(e)
            
            self._add_history("package", "", "failed", str(e))
            
            return False, str(e)

    # ==================== STM32 固件更新 ====================
    
    def update_stm32_firmware(
        self,
        firmware_path: str,
        serial_port: str = "/dev/ttyUSB0",
        progress_callback: Callable[[float, str], None] = None
    ) -> Tuple[bool, str]:
        """
        更新 STM32 固件
        
        使用 stm32flash 工具通过串口烧录
        
        Args:
            firmware_path: 固件文件路径 (.bin 或 .hex)
            serial_port: 串口设备
            progress_callback: 进度回调
            
        Returns:
            (成功标志, 消息)
        """
        self._progress_callback = progress_callback
        
        firmware_file = Path(firmware_path)
        if not firmware_file.exists():
            return False, f"固件文件不存在: {firmware_path}"
        
        with self._lock:
            self._status = UpdateStatus.INSTALLING
            self._progress = 0.0
        
        try:
            # 检查 stm32flash 工具
            self._report_progress(0.1, "检查烧录工具...")
            if not self._check_stm32flash():
                return False, "stm32flash 工具未安装"
            
            # 进入 bootloader 模式
            self._report_progress(0.2, "进入 Bootloader 模式...")
            # 这里需要通过 GPIO 控制 BOOT0 和 RESET 引脚
            # 具体实现取决于硬件连接
            
            # 烧录固件
            self._report_progress(0.3, "烧录固件...")
            
            cmd = [
                'stm32flash',
                '-w', str(firmware_file),
                '-v',  # 验证
                '-g', '0x08000000',  # 启动地址
                serial_port
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode != 0:
                raise Exception(f"烧录失败: {result.stderr}")
            
            # 退出 bootloader 模式
            self._report_progress(0.9, "重启 STM32...")
            # 复位 STM32
            
            self._report_progress(1.0, "固件更新完成")
            
            with self._lock:
                self._status = UpdateStatus.SUCCESS
            
            self._add_history("stm32", firmware_file.name, "success")
            
            return True, "STM32 固件更新成功"
            
        except subprocess.TimeoutExpired:
            with self._lock:
                self._status = UpdateStatus.FAILED
                self._error_message = "烧录超时"
            return False, "烧录超时"
            
        except Exception as e:
            logger.error(f"STM32 更新失败: {e}")
            
            with self._lock:
                self._status = UpdateStatus.FAILED
                self._error_message = str(e)
            
            self._add_history("stm32", "", "failed", str(e))
            
            return False, str(e)
    
    def _check_stm32flash(self) -> bool:
        """检查 stm32flash 是否可用"""
        try:
            result = subprocess.run(
                ['stm32flash', '--version'],
                capture_output=True
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False
    
    # ==================== 配置更新 ====================
    
    def update_config(
        self,
        config_url: str = None,
        config_data: dict = None
    ) -> Tuple[bool, str]:
        """
        更新配置文件
        
        Args:
            config_url: 配置文件 URL
            config_data: 配置数据字典
            
        Returns:
            (成功标志, 消息)
        """
        try:
            config_dir = self._app_dir / "config"
            
            # 备份当前配置
            backup_config = self._backup_dir / f"config_backup_{int(time.time())}"
            if config_dir.exists():
                shutil.copytree(config_dir, backup_config)
            
            if config_url:
                # 从 URL 下载
                import urllib.request
                with urllib.request.urlopen(config_url, timeout=30) as response:
                    config_data = json.loads(response.read().decode())
            
            if config_data:
                # 合并配置
                for filename, content in config_data.items():
                    config_file = config_dir / filename
                    
                    if filename.endswith('.yaml') or filename.endswith('.yml'):
                        import yaml
                        with open(config_file, 'w') as f:
                            yaml.dump(content, f, default_flow_style=False)
                    else:
                        with open(config_file, 'w') as f:
                            json.dump(content, f, indent=2)
                    
                    logger.info(f"更新配置: {filename}")
            
            self._add_history("config", "", "success")
            return True, "配置更新成功"
            
        except Exception as e:
            logger.error(f"配置更新失败: {e}")
            
            # 回滚
            if backup_config and backup_config.exists():
                if config_dir.exists():
                    shutil.rmtree(config_dir)
                shutil.copytree(backup_config, config_dir)
            
            self._add_history("config", "", "failed", str(e))
            return False, str(e)
    
    # ==================== 备份和回滚 ====================
    
    def _create_backup(self) -> Optional[Path]:
        """创建备份"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = self._backup_dir / f"backup_{timestamp}"
            
            # 备份关键文件
            files_to_backup = [
                "src",
                "config",
                "VERSION",
                "requirements.txt"
            ]
            
            backup_path.mkdir(parents=True, exist_ok=True)
            
            for item in files_to_backup:
                src = self._app_dir / item
                if src.exists():
                    dst = backup_path / item
                    if src.is_dir():
                        shutil.copytree(src, dst)
                    else:
                        shutil.copy2(src, dst)
            
            logger.info(f"备份创建: {backup_path}")
            return backup_path
            
        except Exception as e:
            logger.error(f"创建备份失败: {e}")
            return None
    
    def _rollback(self, backup_path: Path) -> bool:
        """回滚到备份"""
        try:
            logger.warning(f"回滚到备份: {backup_path}")
            
            for item in backup_path.iterdir():
                dst = self._app_dir / item.name
                
                if dst.exists():
                    if dst.is_dir():
                        shutil.rmtree(dst)
                    else:
                        dst.unlink()
                
                if item.is_dir():
                    shutil.copytree(item, dst)
                else:
                    shutil.copy2(item, dst)
            
            with self._lock:
                self._status = UpdateStatus.ROLLED_BACK
            
            self._add_history("rollback", "", "success", str(backup_path))
            
            return True
            
        except Exception as e:
            logger.error(f"回滚失败: {e}")
            return False
    
    def list_backups(self) -> List[dict]:
        """列出所有备份"""
        backups = []
        
        for item in self._backup_dir.iterdir():
            if item.is_dir() and item.name.startswith("backup_"):
                backups.append({
                    'name': item.name,
                    'path': str(item),
                    'created': datetime.fromtimestamp(item.stat().st_mtime).isoformat(),
                    'size_mb': sum(f.stat().st_size for f in item.rglob('*') if f.is_file()) / (1024*1024)
                })
        
        return sorted(backups, key=lambda x: x['created'], reverse=True)
    
    def restore_backup(self, backup_name: str) -> Tuple[bool, str]:
        """恢复指定备份"""
        backup_path = self._backup_dir / backup_name
        
        if not backup_path.exists():
            return False, f"备份不存在: {backup_name}"
        
        if self._rollback(backup_path):
            return True, f"已恢复到备份: {backup_name}"
        else:
            return False, "恢复失败"
    
    def delete_backup(self, backup_name: str) -> Tuple[bool, str]:
        """删除备份"""
        backup_path = self._backup_dir / backup_name
        
        if not backup_path.exists():
            return False, f"备份不存在: {backup_name}"
        
        try:
            shutil.rmtree(backup_path)
            return True, f"已删除备份: {backup_name}"
        except Exception as e:
            return False, str(e)
    
    # ==================== 辅助方法 ====================
    
    def _report_progress(self, progress: float, message: str):
        """报告进度"""
        with self._lock:
            self._progress = progress
        
        if self._progress_callback:
            self._progress_callback(progress, message)
        
        logger.info(f"[{progress*100:.0f}%] {message}")
    
    def _calculate_md5(self, file_path: Path) -> str:
        """计算文件 MD5"""
        md5 = hashlib.md5()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                md5.update(chunk)
        return md5.hexdigest()
    
    def _extract_package(self, package_path: Path):
        """解压更新包"""
        import tarfile
        
        with tarfile.open(package_path, 'r:gz') as tar:
            tar.extractall(self._app_dir)
    
    def _install_dependencies(self):
        """安装依赖"""
        requirements_file = self._app_dir / "requirements.txt"
        
        if requirements_file.exists():
            subprocess.run(
                ['pip', 'install', '-r', str(requirements_file), '-q'],
                cwd=self._app_dir
            )
    
    def _verify_installation(self) -> bool:
        """验证安装"""
        # 检查关键文件
        required_files = [
            "main.py",
            "src/__init__.py"
        ]
        
        for f in required_files:
            if not (self._app_dir / f).exists():
                logger.error(f"缺少文件: {f}")
                return False
        
        # 尝试导入主模块
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "main", self._app_dir / "main.py"
            )
            # 只检查语法，不执行
            return spec is not None
        except (ImportError, FileNotFoundError):
            # 导入失败或文件不存在
            return False
        
        return True
