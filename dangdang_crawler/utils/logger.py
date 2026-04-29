"""日志系统模块：提供统一的日志管理，支持控制台输出、文件轮转和Qt界面集成"""

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path


class LoggerManager:
    """日志管理器（单例模式）：统一管理所有模块的日志输出"""

    _instance: "LoggerManager | None" = None
    _loggers: dict = {}

    def __new__(cls, *args, **kwargs):
        """单例模式：确保全局只有一个日志管理器实例"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, log_dir: str | None = None):
        """
        初始化日志管理器

        参数:
            log_dir: 日志文件目录，默认为用户主目录下的 .dangdang_crawler/logs
        """
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        if log_dir is None:
            log_dir = os.path.join(Path.home(), ".dangdang_crawler", "logs")
        self._log_dir = log_dir
        os.makedirs(self._log_dir, exist_ok=True)

    def get_logger(self, name: str = "dangdang") -> logging.Logger:
        """
        获取或创建指定名称的日志器

        每个日志器配备三个handler：
        - 控制台输出（INFO级别）
        - 文件输出（DEBUG级别，轮转10MB）
        - 错误文件输出（ERROR级别，轮转10MB）
        """
        if name in self._loggers:
            return self._loggers[name]

        # 确保日志目录存在
        os.makedirs(self._log_dir, exist_ok=True)

        logger = logging.getLogger(name)
        logger.setLevel(logging.DEBUG)

        # 避免重复添加handler
        if logger.handlers:
            self._loggers[name] = logger
            return logger

        # 日志格式
        formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        # 控制台输出handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        # 全量日志文件handler（轮转，每个文件最大10MB，保留5个备份）
        file_handler = RotatingFileHandler(
            os.path.join(self._log_dir, f"{name}.log"),
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        # 错误日志文件handler（仅记录ERROR及以上级别）
        error_handler = RotatingFileHandler(
            os.path.join(self._log_dir, f"{name}_error.log"),
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        logger.addHandler(error_handler)

        self._loggers[name] = logger
        return logger

    def add_qt_handler(self, logger: logging.Logger, callback):
        """为日志器添加Qt界面输出handler，将日志消息转发到UI"""
        handler = _QtLogHandler(callback)
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter("[%(levelname)s] %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)


class _QtLogHandler(logging.Handler):
    """自定义日志Handler：将日志消息转发到Qt界面的回调函数"""

    def __init__(self, callback):
        super().__init__()
        self._callback = callback

    def emit(self, record: logging.LogRecord):
        """发送日志记录到Qt回调"""
        try:
            msg = self.format(record)
            self._callback(msg)
        except Exception:
            pass
