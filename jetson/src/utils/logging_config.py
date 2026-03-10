"""
日志配置模块

提供统一的日志配置，支持：
- 控制台输出（彩色）
- 文件输出（按日期轮转）
- 不同模块不同级别
"""

import logging
import sys
from pathlib import Path
from datetime import datetime


# ANSI 颜色代码
class Colors:
    RESET = "\033[0m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    GRAY = "\033[90m"


class ColoredFormatter(logging.Formatter):
    """彩色日志格式化器"""
    
    LEVEL_COLORS = {
        logging.DEBUG: Colors.GRAY,
        logging.INFO: Colors.GREEN,
        logging.WARNING: Colors.YELLOW,
        logging.ERROR: Colors.RED,
        logging.CRITICAL: Colors.MAGENTA,
    }
    
    def format(self, record):
        # 添加颜色
        color = self.LEVEL_COLORS.get(record.levelno, Colors.RESET)
        
        # 格式化时间
        time_str = datetime.fromtimestamp(record.created).strftime('%H:%M:%S')
        
        # 缩短模块名
        name = record.name
        if name.startswith('src.'):
            name = name[4:]
        if len(name) > 20:
            name = '...' + name[-17:]
        
        # 构建消息
        level = record.levelname[0]  # 只取首字母
        msg = f"{Colors.GRAY}{time_str}{Colors.RESET} {color}{level}{Colors.RESET} {Colors.CYAN}{name:20}{Colors.RESET} {record.getMessage()}"
        
        # 添加异常信息
        if record.exc_info:
            msg += '\n' + self.formatException(record.exc_info)
        
        return msg


class FileFormatter(logging.Formatter):
    """文件日志格式化器"""
    
    def __init__(self):
        super().__init__(
            fmt='%(asctime)s %(levelname)-8s %(name)s %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )


def setup_logging(
    level: int = logging.INFO,
    log_dir: Path = None,
    console: bool = True,
    file: bool = True
):
    """
    设置日志配置
    
    Args:
        level: 日志级别
        log_dir: 日志文件目录
        console: 是否输出到控制台
        file: 是否输出到文件
    """
    # 获取根日志器
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # 清除现有处理器
    root_logger.handlers.clear()
    
    # 控制台处理器
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(ColoredFormatter())
        root_logger.addHandler(console_handler)
    
    # 文件处理器
    if file:
        if log_dir is None:
            log_dir = Path(__file__).parent.parent.parent / "logs"
        
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # 按日期命名日志文件
        log_file = log_dir / f"{datetime.now().strftime('%Y-%m-%d')}.log"
        
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(level)
        file_handler.setFormatter(FileFormatter())
        root_logger.addHandler(file_handler)
    
    # 设置第三方库日志级别
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    logging.getLogger('PIL').setLevel(logging.WARNING)
    
    # 记录启动信息
    logger = logging.getLogger(__name__)
    logger.info("日志系统已初始化")


def get_logger(name: str) -> logging.Logger:
    """
    获取日志器
    
    Args:
        name: 日志器名称
        
    Returns:
        日志器实例
    """
    return logging.getLogger(name)
