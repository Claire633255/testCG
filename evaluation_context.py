from contextvars import ContextVar
from typing import Dict, Any

# 定义一个 ContextVar，默认值为空字典
# 这个变量在每一条线程/协程里都是独立的，互不干扰
current_task_context: ContextVar[Dict[str, Any]] = ContextVar("current_task_context", default={})

def set_context(ctx: Dict[str, Any]):
    """设置当前任务上下文"""
    return current_task_context.set(ctx)

def get_context() -> Dict[str, Any]:
    """获取当前任务上下文"""
    return current_task_context.get()