"""
云端备份管理器

功能：
1. 图像自动上传
2. 配置备份
3. 日志备份
4. 恢复功能

支持的云存储：
- AWS S3
- 阿里云 OSS
- 本地 FTP/SFTP
- WebDAV
"""

import os
import json
import shutil
import logging
import threading
import time
from pathlib import Path
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Callable, Tuple
from datetime import datetime
from queue import Queue, Empty

logger = logging.getLogger(__name__)


class BackupStatus(Enum):
    """备份状态"""
    IDLE = "idle"
    UPLOADING = "uploading"
    DOWNLOADING = "downloading"
    SUCCESS = "success"
    FAILED = "failed"


class StorageType(Enum):
    """存储类型"""
    LOCAL = "local"
    S3 = "s3"
    OSS = "oss"
    FTP = "ftp"
    WEBDAV = "webdav"


@dataclass
class BackupConfig:
    """备份配置"""
    enabled: bool = True
    storage_type: StorageType = StorageType.LOCAL
    
    # 本地备份路径
    local_path: str = "cloud_backup"
    
    # S3 配置
    s3_bucket: str = ""
    s3_prefix: str = "camera_backup/"
    s3_region: str = "us-east-1"
    aws_access_key: str = ""
    aws_secret_key: str = ""
    
    # OSS 配置
    oss_bucket: str = ""
    oss_endpoint: str = ""
    oss_access_key: str = ""
    oss_secret_key: str = ""
    
    # FTP 配置
    ftp_host: str = ""
    ftp_port: int = 21
    ftp_user: str = ""
    ftp_password: str = ""
    ftp_path: str = "/backup/"
    
    # 自动备份设置
    auto_backup_images: bool = True
    auto_backup_config: bool = True
    auto_backup_logs: bool = False
    backup_interval_hours: int = 24
    max_backup_size_mb: int = 1000
    
    def to_dict(self) -> dict:
        return {
            'enabled': self.enabled,
            'storage_type': self.storage_type.value,
            'local_path': self.local_path,
            's3_bucket': self.s3_bucket,
            's3_prefix': self.s3_prefix,
            's3_region': self.s3_region,
            'oss_bucket': self.oss_bucket,
            'oss_endpoint': self.oss_endpoint,
            'ftp_host': self.ftp_host,
            'ftp_port': self.ftp_port,
            'ftp_path': self.ftp_path,
            'auto_backup_images': self.auto_backup_images,
            'auto_backup_config': self.auto_backup_config,
            'auto_backup_logs': self.auto_backup_logs,
            'backup_interval_hours': self.backup_interval_hours,
            'max_backup_size_mb': self.max_backup_size_mb
        }


@dataclass
class BackupTask:
    """备份任务"""
    file_path: str
    remote_path: str
    task_type: str  # upload, download
    priority: int = 0
    retry_count: int = 0
    max_retries: int = 3


class CloudBackup:
    """
    云端备份管理器
    
    支持多种云存储后端，提供自动和手动备份功能
    """
    
    def __init__(self, config: BackupConfig = None):
        self._config = config or BackupConfig()
        self._status = BackupStatus.IDLE
        self._progress = 0.0
        self._error_message = ""
        
        # 任务队列
        self._task_queue: Queue = Queue()
        self._running = False
        self._worker_thread: Optional[threading.Thread] = None
        
        # 统计
        self._uploaded_count = 0
        self._uploaded_size = 0
        self._failed_count = 0
        
        # 存储客户端
        self._storage_client = None
        
        # 初始化存储
        self._init_storage()
    
    def _init_storage(self):
        """初始化存储后端"""
        storage_type = self._config.storage_type
        
        if storage_type == StorageType.LOCAL:
            self._init_local_storage()
        elif storage_type == StorageType.S3:
            self._init_s3_storage()
        elif storage_type == StorageType.OSS:
            self._init_oss_storage()
        elif storage_type == StorageType.FTP:
            self._init_ftp_storage()
    
    def _init_local_storage(self):
        """初始化本地存储"""
        local_path = Path(self._config.local_path)
        local_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"本地备份目录: {local_path}")
    
    def _init_s3_storage(self):
        """初始化 S3 存储"""
        try:
            import boto3
            self._storage_client = boto3.client(
                's3',
                region_name=self._config.s3_region,
                aws_access_key_id=self._config.aws_access_key,
                aws_secret_access_key=self._config.aws_secret_key
            )
            logger.info(f"S3 存储已初始化: {self._config.s3_bucket}")
        except ImportError:
            logger.warning("boto3 未安装，S3 备份不可用")
        except Exception as e:
            logger.error(f"S3 初始化失败: {e}")
    
    def _init_oss_storage(self):
        """初始化阿里云 OSS"""
        try:
            import oss2
            auth = oss2.Auth(
                self._config.oss_access_key,
                self._config.oss_secret_key
            )
            self._storage_client = oss2.Bucket(
                auth,
                self._config.oss_endpoint,
                self._config.oss_bucket
            )
            logger.info(f"OSS 存储已初始化: {self._config.oss_bucket}")
        except ImportError:
            logger.warning("oss2 未安装，OSS 备份不可用")
        except Exception as e:
            logger.error(f"OSS 初始化失败: {e}")
    
    def _init_ftp_storage(self):
        """初始化 FTP 存储"""
        # FTP 连接在需要时创建
        logger.info(f"FTP 存储配置: {self._config.ftp_host}")
    
    # ==================== 上传功能 ====================
    
    def upload_file(self, local_path: str, remote_path: str = None) -> Tuple[bool, str]:
        """
        上传单个文件
        
        Args:
            local_path: 本地文件路径
            remote_path: 远程路径（可选）
            
        Returns:
            (成功标志, 消息)
        """
        local_file = Path(local_path)
        
        if not local_file.exists():
            return False, f"文件不存在: {local_path}"
        
        if remote_path is None:
            remote_path = local_file.name
        
        storage_type = self._config.storage_type
        
        try:
            if storage_type == StorageType.LOCAL:
                return self._upload_local(local_file, remote_path)
            elif storage_type == StorageType.S3:
                return self._upload_s3(local_file, remote_path)
            elif storage_type == StorageType.OSS:
                return self._upload_oss(local_file, remote_path)
            elif storage_type == StorageType.FTP:
                return self._upload_ftp(local_file, remote_path)
            else:
                return False, f"不支持的存储类型: {storage_type}"
                
        except Exception as e:
            logger.error(f"上传失败: {e}")
            return False, str(e)
    
    def _upload_local(self, local_file: Path, remote_path: str) -> Tuple[bool, str]:
        """上传到本地备份目录"""
        dst = Path(self._config.local_path) / remote_path
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(local_file, dst)
        return True, f"已备份到: {dst}"
    
    def _upload_s3(self, local_file: Path, remote_path: str) -> Tuple[bool, str]:
        """上传到 S3"""
        if not self._storage_client:
            return False, "S3 客户端未初始化"
        
        key = self._config.s3_prefix + remote_path
        self._storage_client.upload_file(
            str(local_file),
            self._config.s3_bucket,
            key
        )
        return True, f"已上传到 S3: {key}"
    
    def _upload_oss(self, local_file: Path, remote_path: str) -> Tuple[bool, str]:
        """上传到 OSS"""
        if not self._storage_client:
            return False, "OSS 客户端未初始化"
        
        self._storage_client.put_object_from_file(remote_path, str(local_file))
        return True, f"已上传到 OSS: {remote_path}"
    
    def _upload_ftp(self, local_file: Path, remote_path: str) -> Tuple[bool, str]:
        """上传到 FTP"""
        import ftplib
        
        with ftplib.FTP() as ftp:
            ftp.connect(self._config.ftp_host, self._config.ftp_port)
            ftp.login(self._config.ftp_user, self._config.ftp_password)
            
            # 创建目录
            remote_dir = self._config.ftp_path + os.path.dirname(remote_path)
            self._ftp_makedirs(ftp, remote_dir)
            
            # 上传文件
            full_path = self._config.ftp_path + remote_path
            with open(local_file, 'rb') as f:
                ftp.storbinary(f'STOR {full_path}', f)
        
        return True, f"已上传到 FTP: {full_path}"
    
    def _ftp_makedirs(self, ftp, path: str):
        """FTP 递归创建目录"""
        dirs = path.split('/')
        current = ''
        for d in dirs:
            if not d:
                continue
            current += '/' + d
            try:
                ftp.mkd(current)
            except Exception:
                # 目录可能已存在，忽略错误
                pass
    
    # ==================== 批量备份 ====================
    
    def backup_images(self, images_dir: str, since: datetime = None) -> Tuple[int, int]:
        """
        备份图像目录
        
        Args:
            images_dir: 图像目录
            since: 只备份此时间之后的文件
            
        Returns:
            (成功数, 失败数)
        """
        images_path = Path(images_dir)
        
        if not images_path.exists():
            logger.warning(f"图像目录不存在: {images_dir}")
            return 0, 0
        
        success_count = 0
        fail_count = 0
        
        for img_file in images_path.rglob("*"):
            if not img_file.is_file():
                continue
            
            # 检查文件扩展名
            if img_file.suffix.lower() not in ['.jpg', '.jpeg', '.png', '.bmp']:
                continue
            
            # 检查修改时间
            if since:
                mtime = datetime.fromtimestamp(img_file.stat().st_mtime)
                if mtime < since:
                    continue
            
            # 构建远程路径
            rel_path = img_file.relative_to(images_path)
            remote_path = f"images/{rel_path}"
            
            success, msg = self.upload_file(str(img_file), remote_path)
            
            if success:
                success_count += 1
            else:
                fail_count += 1
                logger.error(f"备份失败: {img_file} - {msg}")
        
        logger.info(f"图像备份完成: {success_count} 成功, {fail_count} 失败")
        return success_count, fail_count
    
    def backup_config(self, config_dir: str = "config") -> Tuple[bool, str]:
        """备份配置文件"""
        config_path = Path(config_dir)
        
        if not config_path.exists():
            return False, f"配置目录不存在: {config_dir}"
        
        # 创建配置压缩包
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_name = f"config_backup_{timestamp}"
        
        archive_path = shutil.make_archive(
            archive_name,
            'zip',
            config_path
        )
        
        # 上传
        remote_path = f"config/{archive_name}.zip"
        success, msg = self.upload_file(archive_path, remote_path)
        
        # 清理临时文件
        Path(archive_path).unlink()
        
        return success, msg
    
    def backup_logs(self, logs_dir: str = "logs") -> Tuple[bool, str]:
        """备份日志文件"""
        logs_path = Path(logs_dir)
        
        if not logs_path.exists():
            return False, f"日志目录不存在: {logs_dir}"
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_name = f"logs_backup_{timestamp}"
        
        archive_path = shutil.make_archive(
            archive_name,
            'zip',
            logs_path
        )
        
        remote_path = f"logs/{archive_name}.zip"
        success, msg = self.upload_file(archive_path, remote_path)
        
        Path(archive_path).unlink()
        
        return success, msg
    
    # ==================== 下载/恢复 ====================
    
    def download_file(self, remote_path: str, local_path: str) -> Tuple[bool, str]:
        """下载文件"""
        storage_type = self._config.storage_type
        local_file = Path(local_path)
        local_file.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            if storage_type == StorageType.LOCAL:
                src = Path(self._config.local_path) / remote_path
                shutil.copy2(src, local_file)
                return True, f"已恢复: {local_path}"
                
            elif storage_type == StorageType.S3:
                key = self._config.s3_prefix + remote_path
                self._storage_client.download_file(
                    self._config.s3_bucket,  
                    key,
                    str(local_file)
                )
                return True, f"已从 S3 下载: {local_path}"
                
            elif storage_type == StorageType.OSS:
                self._storage_client.get_object_to_file(remote_path, str(local_file))
                return True, f"已从 OSS 下载: {local_path}"
                
            elif storage_type == StorageType.FTP:
                import ftplib
                with ftplib.FTP() as ftp:
                    ftp.connect(self._config.ftp_host, self._config.ftp_port)
                    ftp.login(self._config.ftp_user, self._config.ftp_password)
                    full_path = self._config.ftp_path + remote_path
                    with open(local_file, 'wb') as f:
                        ftp.retrbinary(f'RETR {full_path}', f.write)
                return True, f"已从 FTP 下载: {local_path}"
            
            return False, f"不支持的存储类型: {storage_type}"
            
        except Exception as e:
            return False, str(e)
    
    def restore_config(self, backup_name: str, config_dir: str = "config") -> Tuple[bool, str]:
        """恢复配置"""
        # 下载备份
        temp_file = f"/tmp/{backup_name}"
        success, msg = self.download_file(f"config/{backup_name}", temp_file)
        
        if not success:
            return False, msg
        
        # 解压
        import zipfile
        with zipfile.ZipFile(temp_file, 'r') as zip_ref:
            zip_ref.extractall(config_dir)
        
        Path(temp_file).unlink()
        
        return True, f"配置已恢复到: {config_dir}"
    
    # ==================== 自动备份 ====================
    
    def start_auto_backup(self):
        """启动自动备份"""
        if self._running:
            return
        
        self._running = True
        self._worker_thread = threading.Thread(target=self._auto_backup_loop, daemon=True)
        self._worker_thread.start()
        logger.info("自动备份已启动")
    
    def stop_auto_backup(self):
        """停止自动备份"""
        self._running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=5)
        logger.info("自动备份已停止")
    
    def _auto_backup_loop(self):
        """自动备份循环"""
        interval = self._config.backup_interval_hours * 3600
        last_backup = 0
        
        while self._running:
            now = time.time()
            
            if now - last_backup >= interval:
                logger.info("执行自动备份...")
                
                if self._config.auto_backup_images:
                    self.backup_images("captures")
                
                if self._config.auto_backup_config:
                    self.backup_config()
                
                if self._config.auto_backup_logs:
                    self.backup_logs()
                
                last_backup = now
            
            time.sleep(60)  # 每分钟检查一次
    
    # ==================== 状态查询 ====================
    
    def get_status(self) -> dict:
        """获取备份状态"""
        return {
            'status': self._status.value,
            'progress': self._progress,
            'error_message': self._error_message,
            'uploaded_count': self._uploaded_count,
            'uploaded_size_mb': self._uploaded_size / (1024 * 1024),
            'failed_count': self._failed_count,
            'storage_type': self._config.storage_type.value,
            'auto_backup_running': self._running
        }
    
    def list_backups(self, prefix: str = "") -> List[dict]:
        """列出远程备份"""
        storage_type = self._config.storage_type
        backups = []
        
        try:
            if storage_type == StorageType.LOCAL:
                backup_path = Path(self._config.local_path) / prefix
                if backup_path.exists():
                    for f in backup_path.rglob("*"):
                        if f.is_file():
                            backups.append({
                                'name': str(f.relative_to(self._config.local_path)),
                                'size': f.stat().st_size,
                                'modified': datetime.fromtimestamp(f.stat().st_mtime).isoformat()
                            })
            
            elif storage_type == StorageType.S3:
                response = self._storage_client.list_objects_v2(
                    Bucket=self._config.s3_bucket,
                    Prefix=self._config.s3_prefix + prefix
                )
                for obj in response.get('Contents', []):
                    backups.append({
                        'name': obj['Key'].replace(self._config.s3_prefix, ''),
                        'size': obj['Size'],
                        'modified': obj['LastModified'].isoformat()
                    })
        
        except Exception as e:
            logger.error(f"列出备份失败: {e}")
        
        return backups
