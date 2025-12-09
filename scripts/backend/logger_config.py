"""
Logging Configuration Manager
处理所有日志相关的配置和初始化
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path


class LoggerManager:
    """日志管理器"""
    
    # 单例实例
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if LoggerManager._initialized:
            return
        
        self.log_dir = os.path.join(os.path.dirname(__file__), "logs")
        self._setup_logging()
        LoggerManager._initialized = True
    
    def _setup_logging(self):
        """配置日志系统"""
        # 创建日志目录
        Path(self.log_dir).mkdir(exist_ok=True)
        
        # 日志格式
        log_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # 获取根logger
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        
        # 清空已有的handlers（避免重复添加）
        root_logger.handlers.clear()
        
        # Console Handler (INFO level)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(log_format)
        root_logger.addHandler(console_handler)
        
        # File Handler - app.log (DEBUG level，所有日志)
        app_log_path = os.path.join(self.log_dir, "app.log")
        app_file_handler = RotatingFileHandler(
            app_log_path,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,  # 保留5个备份
            encoding='utf-8'
        )
        app_file_handler.setLevel(logging.DEBUG)
        app_file_handler.setFormatter(log_format)
        root_logger.addHandler(app_file_handler)
        
        # File Handler - error.log (ERROR level，仅错误)
        error_log_path = os.path.join(self.log_dir, "error.log")
        error_file_handler = RotatingFileHandler(
            error_log_path,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        error_file_handler.setLevel(logging.ERROR)
        error_file_handler.setFormatter(log_format)
        root_logger.addHandler(error_file_handler)
    
    @staticmethod
    def get_logger(name: str) -> logging.Logger:
        """获取指定名称的logger"""
        LoggerManager()  # 确保日志系统已初始化
        return logging.getLogger(name)


def get_logger(name: str) -> logging.Logger:
    """便捷函数：获取logger"""
    return LoggerManager.get_logger(name)


def init_logging():
    """初始化日志系统"""
    LoggerManager()
