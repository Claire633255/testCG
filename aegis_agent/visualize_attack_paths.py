#!/usr/bin/env python3
"""
攻击路径可视化脚本
将potential_attack_path绘制成PNG图片
"""

import json
import os
import logging
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch, ConnectionPatch
import networkx as nx
from typing import List, Dict, Any
import matplotlib.font_manager as fm
import graphviz
from typing import Dict, Any
import html

# 设置日志
logger = logging.getLogger(__name__)

# 设置中文字体支持
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

class AttackPathVisualizer:
    def _wrap_text(self, text: str, max_chinese_chars: int = 35) -> list:
        """
        自动换行函数 - 基于中英文字符宽度计算换行
        
        Args:
            text: 需要换行的文本
            max_chinese_chars: 最大中文字符数（英文字符按0.6个中文字符宽度计算）
            
        Returns:
            换行后的文本行列表
        """
        if not text:
            return []
            
        # 首先按已有的换行符分割
        lines = text.split('\n')
        wrapped_lines = []
        
        for line in lines:
            # 计算当前行的宽度（按中文字符宽度）
            line_width = 0
            current_line = ""
            
            for char in line:
                # 判断字符类型：中文字符宽度为1，英文字符宽度为0.6
                # 在等宽字体中，中文字符通常是英文字符的两倍宽度
                if '\u4e00' <= char <= '\u9fff':  # 中文字符
                    char_width = 1
                else:  # 英文字符或其他字符
                    char_width = 0.45
                
                # 如果加上当前字符不超过限制，添加到当前行
                if line_width + char_width <= max_chinese_chars:
                    current_line += char
                    line_width += char_width
                else:
                    # 当前行已满，保存并开始新行
                    if current_line:
                        wrapped_lines.append(current_line)
                    current_line = char
                    line_width = char_width
            
            # 添加最后一行
            if current_line:
                wrapped_lines.append(current_line)
        
        return wrapped_lines

    def _get_node_style_for_types(self, node_type: str):
        """根据类型组合获取节点样式"""
        # 基础颜色映射
        base_colors = {
            'vulnerable_sink': "#FFA4A4",       
            'attack_source': "#FFFFA9",
            'taint_propagation': "#FFFFA9",
            'security_sanitizer': "#D5FFB8",
        }
        return {
            'fillcolor': base_colors.get(node_type, "#EEEEEE"),
            'fontcolor': '#000000',
            'shape': 'box'
        }
    
    def init_digraph(self):
        dot = graphviz.Digraph(graph_attr={'dpi': '72'})
        
        # 设置图的属性 - 使用支持中文的字体
        dot.attr(rankdir='TB')  # 从上到下布局
        dot.attr('graph', 
                bgcolor='white',
                fontname='WenQuanYi Micro Hei, WenQuanYi Zen Hei, DejaVu Sans',
                fontsize='14',
                label='',
                labelloc='t',
                pad='0.2',  # 减少内边距
                nodesep='0.3',  # 减少节点间距
                ranksep='0.5',  # 减少层级间距
                rankdir='TB',   # 确保方向一致
                concentrate='true',  # 合并边线
                splines='polyline')  # 使用直线减少空白
        
        # 设置默认节点和边属性
        dot.attr('node', 
                fontname='WenQuanYi Micro Hei, WenQuanYi Zen Hei, DejaVu Sans',  # 使用已安装的中文字体
                fontsize='12',
                style='filled',
                shape='box',
                width='0',
                height='0',
                margin='0.1,0.05',
                color='black',     # 边框颜色
                fillcolor='white', # 填充颜色
                fontcolor='black') # 字体颜色
        
        dot.attr('edge', 
                fontname='WenQuanYi Micro Hei, WenQuanYi Zen Hei, DejaVu Sans',  # 使用已安装的中文字体
                fontsize='12',
                color='black',
                arrowhead='vee')
        
        return dot

    def create_entry_sink_callgraph(self, output_path: str, path_info: Dict[str, Any], function_analysis_records, additional_remarks: str = None) -> str:
        """
        创建入口点到漏洞点的攻击路径图表
        
        Args:
            output_path: 输出图片文件路径
            path_info: 攻击路径信息，包含以下字段：
                - sink_name: 漏洞点名称
                - entry_name: 入口点名称  
                - call_graph: 调用图列表，包含 caller -> callee 关系
            function_analysis_records: 函数分析记录字典
            additional_remarks: 额外的分析结论备注
                
        Returns:
            生成的图片文件路径
        """
        dot = self.init_digraph()
        
        # 设置图表标题
        entry_name = path_info.get("entry_name")
        sink_name = path_info.get("sink_name")
        # title = f"攻击路径: {entry_name} -> {sink_name}"
        title = f"Vulnerability Path: {entry_name} -> {sink_name}"
        
        # 如果 additional_remarks 不为 None，将标题和备注合并显示在底部
        if additional_remarks is not None:
            # 处理多行文本，使用自动换行
            wrapped_remarks = self._wrap_text(additional_remarks, max_chinese_chars=80)
            
            # 创建 HTML 表格格式的标签，包含标题和备注
            label_lines = [
                '<TABLE BORDER="1" CELLBORDER="1" CELLSPACING="0" CELLPADDING="4" COLOR="black" BGCOLOR="#F0F8FF">',
                '<TR><TD ALIGN="CENTER" BGCOLOR="#E6F3FF" BORDER="0"><FONT FACE="WenQuanYi Micro Hei, WenQuanYi Zen Hei, DejaVu Sans" COLOR="black" POINT-SIZE="14"><B>{}</B></FONT></TD></TR>'.format(
                    html.escape(title)
                )
            ]
            
            # 添加每行备注内容
            for line in wrapped_remarks:
                label_lines.append(
                    '<TR><TD ALIGN="LEFT" BGCOLOR="#F0F8FF" BORDER="0"><FONT FACE="WenQuanYi Micro Hei, WenQuanYi Zen Hei, DejaVu Sans" COLOR="black" POINT-SIZE="10">{}</FONT></TD></TR>'.format(
                        html.escape(line)
                    )
                )
            
            label_lines.append('</TABLE>')
            html_label = '<{}>'.format(''.join(label_lines))
            
            # 设置图表标签在底部
            dot.attr('graph', label=html_label, labelloc='b')
        else:
            # 如果没有备注，只显示标题在顶部
            dot.attr('graph', label=title, labelloc='t', fontsize='16')
        
        # 跟踪已处理的节点和边
        processed_nodes = set()
        processed_edges = set()
        
        # 收集所有节点
        all_nodes = set()
        call_graph = path_info.get("call_graph", [])
        
        # 从调用图中提取所有节点
        for call_edge in call_graph:
            all_nodes.add(call_edge["caller"])
            all_nodes.add(call_edge["callee"])
        
        # 添加节点
        for node_name in all_nodes:
            if node_name not in processed_nodes:
                
                # 构建节点标签
                label_lines = [
                    '<TABLE BORDER="1" CELLBORDER="1" CELLSPACING="0" CELLPADDING="4" COLOR="black" BGCOLOR="white">',
                    '<TR><TD ALIGN="CENTER" BGCOLOR="white" BORDER="0"><FONT FACE="WenQuanYi Micro Hei, WenQuanYi Zen Hei, DejaVu Sans" COLOR="black">{}</FONT></TD></TR>'.format(
                        html.escape(node_name)
                    ),
                ]
                
                # 添加分析信息
                if node_name in function_analysis_records:
                    analysis_info = function_analysis_records[node_name]
                    for ana_type, ana_desc in analysis_info.items():
                        node_style = self._get_node_style_for_types(ana_type)
                        if(ana_type in ["key_codes"]):
                            # wrapped_lines = self._wrap_text(f"关键代码: \n{ana_desc}")
                            wrapped_lines = self._wrap_text(f"### Key Codes ###\n{ana_desc}")
                        else:
                            wrapped_lines = self._wrap_text(f"{ana_type}: {ana_desc}")
                        for line in wrapped_lines:
                            label_lines.append(
                                '<TR><TD ALIGN="LEFT" BGCOLOR="{}" BORDER="0"><FONT FACE="WenQuanYi Micro Hei, WenQuanYi Zen Hei, DejaVu Sans" COLOR="{}" POINT-SIZE="10">{}</FONT></TD></TR>'.format(
                                    node_style['fillcolor'], 
                                    node_style['fontcolor'],
                                    html.escape(line)
                                ))
                
                label_lines.append('</TABLE>')
                html_label = '<{}>'.format(''.join(label_lines))
                
                # 创建节点
                dot.node(node_name, 
                        label=html_label,
                        shape='plain',
                        margin='0')
                processed_nodes.add(node_name)
        
        # 添加调用关系边
        for call_edge in call_graph:
            caller = call_edge["caller"]
            callee = call_edge["callee"]
            edge_key = (caller, callee)
            
            if edge_key not in processed_edges:
                dot.edge(caller, callee, label='calls', color='black', fontsize='12')
                processed_edges.add(edge_key)
        
        # 确保输出目录存在
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # 保存 DOT 文件（用于调试）
        dot.save(f"{output_path[:-4]}.dot")
        
        # 渲染为 PNG
        try:
            dot.render(output_path[:-4], format='png', cleanup=True, engine='dot')
            png_path = f"{output_path[:-4]}.png"
            # logger.debug(f"成功生成: {png_path}")
            logger.debug(f"Successfully generated: {png_path}")
            # 创建硬链接，让 current.png 指向当前 PNG 文件
            current_link = "_current.png"
            current_link_inoutput = f"{os.path.dirname(png_path)}/{current_link}"
            for cl in [current_link, current_link_inoutput]:
                try:
                    if os.path.exists(cl):
                        os.remove(cl)
                    os.link(png_path, cl)
                    logger.debug(f"Created hard link: {cl} -> {png_path}")
                except Exception as e:
                    # logger.error(f"创建硬链接失败: {e}")
                    logger.error(f"Failed to create hard link: {e}")

        except Exception as e:
            # logger.error(f"WARNING! 生成图片时出错: {e}")
            logger.error(f"WARNING! Error occurred while generating image: {e}")
