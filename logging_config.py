"""
统一的日志配置模块
提供同时输出到控制台和文件的日志配置
"""

import logging
import logging.handlers
import os
from datetime import datetime

def setup_logging(log_file=None, level=logging.INFO, max_bytes=10*1024*1024, backup_count=5):
    """
    设置日志配置
    
    Args:
        log_file: 日志文件路径，如果为None则使用默认路径
        level: 日志级别
        max_bytes: 单个日志文件最大大小（字节）
        backup_count: 备份文件数量
    """
    # 创建日志目录
    if log_file is None:
        log_dir = "logs"
        os.makedirs(log_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = os.path.join(log_dir, f"app_{timestamp}.log")
    
    # 创建logger
    logger = logging.getLogger()
    logger.setLevel(level)
    
    # 清除现有的处理器
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # 创建格式化器
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 文件处理器（带轮转）
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # 记录日志配置信息
    # logger.info(f"日志系统已初始化 - 控制台和文件输出: {log_file}")
    logger.info(f"Logging system initialized - console and file output: {log_file}")
    
    return logger

def get_logger(name):
    """
    获取指定名称的logger实例
    
    Args:
        name: logger名称，通常是模块名
        
    Returns:
        logging.Logger实例
    """
    return logging.getLogger(name)

# 默认配置
if __name__ == "__main__":
    setup_logging()
