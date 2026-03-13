#!/usr/bin/env python3
"""
dot2png.py
将指定的 .dot 文件直接渲染为 .png 文件，保存到指定目录。
不修改 dot 内容。
"""

import os
import logging
import graphviz

# 设置日志
logger = logging.getLogger(__name__)

SRC_DIR = "/workspace/AegisGraph/AegisGraph_Megatron-LM/Chain/DOT/agent_output"
DST_DIR = "/workspace/AegisGraph/AegisGraph_Megatron-LM/Chain/PNG/agent_output"

def dot2png(dot_filename: str, output_dir: str = DST_DIR) -> str:
    """
    渲染指定 dot 文件为 png。
    
    Args:
        dot_filename: dot 文件名（位于 SRC_DIR 下）
        output_dir: png 输出目录
    
    Returns:
        生成的 PNG 文件路径，失败返回 None
    """
    dot_path = os.path.join(SRC_DIR, dot_filename)
    
    if not os.path.isfile(dot_path):
        # logger.error(f"未找到 dot 文件: {dot_path}")
        logger.error(f"Dot file not found: {dot_path}")
        return None

    os.makedirs(output_dir, exist_ok=True)
    base_name = os.path.splitext(dot_filename)[0]
    out_path_no_ext = os.path.join(output_dir, base_name)

    try:
        with open(dot_path, 'r', encoding='utf-8') as f:
            dot_src = f.read()
        src = graphviz.Source(dot_src)
        src.format = 'png'
        rendered_path = src.render(filename=out_path_no_ext, cleanup=True)
        # logger.info(f"成功生成 PNG: {rendered_path}")
        logger.info(f"Successfully generated PNG: {rendered_path}")
        return rendered_path
    except Exception as e:
        # logger.error(f"渲染失败: {dot_filename} -> {e}")
        logger.error(f"Rendering failed: {dot_filename} -> {e}")
        return None

if __name__ == "__main__":
    # 测试示例
    dot2png("/workspace/AegisGraph/AegisGraph_Megatron-LM/Chain/DOT/agent_output/0013_tasks.vision.main._module_.dot")
