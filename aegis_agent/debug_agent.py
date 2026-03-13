#!/usr/bin/env python3
"""
AegisAgent 调试工具
提供详细的执行过程监控、日志记录和性能分析
"""

import os
import sys
import time
import logging
import json
import traceback
from datetime import datetime
from typing import Dict, Any, List
import threading
from dataclasses import dataclass, asdict
from contextlib import contextmanager

# 添加当前目录到路径，以便导入 agent_demo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ======================================================
# ✅ 调试配置
# ======================================================
DEBUG_CONFIG = {
    "log_level": "DEBUG",  # DEBUG, INFO, WARNING, ERROR
    "log_file": "/workspace/AegisAgent/debug.log",
    "performance_log": "/workspace/AegisAgent/performance.log",
    "state_log": "/workspace/AegisAgent/state_log.json",
    "enable_timing": True,
    "enable_memory_monitoring": False,  # 需要 psutil
    "max_log_size_mb": 10,
    "backup_count": 3
}

# ======================================================
# ✅ 日志设置
# ======================================================
def setup_logging():
    """设置日志配置"""
    logger = logging.getLogger('AegisAgentDebug')
    logger.setLevel(getattr(logging, DEBUG_CONFIG["log_level"]))
    
    # 清除现有处理器
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # 文件处理器
    file_handler = logging.FileHandler(DEBUG_CONFIG["log_file"], encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # 格式化器
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# 全局日志器
logger = setup_logging()

# ======================================================
# ✅ 性能监控类
# ======================================================
@dataclass
class PerformanceMetrics:
    """性能指标数据类"""
    timestamp: str
    operation: str
    duration: float
    llm_calls: int = 0
    tool_calls: int = 0
    memory_usage: float = 0.0
    error_count: int = 0

class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self):
        self.metrics: List[PerformanceMetrics] = []
        self.start_time = None
        self.llm_call_count = 0
        self.tool_call_count = 0
        self.error_count = 0
        
    def start_timing(self, operation: str):
        """开始计时"""
        self.current_operation = operation
        self.start_time = time.time()
        logger.debug(f"开始执行: {operation}")
        
    def stop_timing(self):
        """停止计时并记录指标"""
        if self.start_time is None:
            return
            
        duration = time.time() - self.start_time
        metric = PerformanceMetrics(
            timestamp=datetime.now().isoformat(),
            operation=self.current_operation,
            duration=duration,
            llm_calls=self.llm_call_count,
            tool_calls=self.tool_call_count,
            error_count=self.error_count
        )
        
        self.metrics.append(metric)
        
        # 记录到性能日志
        with open(DEBUG_CONFIG["performance_log"], 'a', encoding='utf-8') as f:
            f.write(json.dumps(asdict(metric), ensure_ascii=False) + '\n')
        
        logger.info(f"操作完成: {self.current_operation}, 耗时: {duration:.2f}s")
        self.start_time = None
        
    def increment_llm_calls(self):
        """增加LLM调用计数"""
        self.llm_call_count += 1
        logger.debug(f"LLM调用计数: {self.llm_call_count}")
        
    def increment_tool_calls(self):
        """增加工具调用计数"""
        self.tool_call_count += 1
        logger.debug(f"工具调用计数: {self.tool_call_count}")
        
    def increment_errors(self):
        """增加错误计数"""
        self.error_count += 1
        logger.warning(f"错误计数: {self.error_count}")
        
    def get_summary(self) -> Dict[str, Any]:
        """获取性能摘要"""
