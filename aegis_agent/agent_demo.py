import os
import re
import logging
from typing import Literal, Annotated
from typing_extensions import TypedDict
from langchain.tools import tool
from langchain.chat_models import init_chat_model
from langchain.messages import (
    AnyMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langgraph.graph import StateGraph, START, END
import operator
from dot2png import dot2png
from langchain_openai import ChatOpenAI
import base64
import json

# 设置日志
logger = logging.getLogger(__name__)


# ======================================================
# ✅ 环境准备 &  模型初始化（按你项目替换 API 名称）
# ======================================================
model = ChatOpenAI(
    # model="/Qwen3-VL-32B-Thinking-FP8",
    model="Qwen/Qwen3-VL-32B-Instruct-FP8",
    openai_api_key="EMPTY",
    # openai_api_base="http://10.24.4.152:4545/v1",
    openai_api_base="http://172.16.167.35:8000/v1",
    temperature=0,
    max_tokens=2048
)


# DOT 文件路径
DOT_DIR = "/workspace/AegisAgent/DOT/"
PNG_DIR = "/workspace/AegisAgent/PNG/"


# ======================================================
# ✅ 工具实现
# ======================================================
def load_dot(filename: str) -> str:
    """读取 DOT 文件内容"""
    file_path = os.path.join(DOT_DIR, filename)
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"{file_path} 不存在")
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()


def save_dot(filename: str, content: str):
    """保存 DOT 文件内容"""
    file_path = os.path.join(DOT_DIR, filename)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)


def dot_to_png(filename: str):
    """将 DOT 文件转化为 PNG 文件"""
    dot2png(filename)


@tool
def modify_field(filename: str, node_name: str, field: str, new_value: str) -> str:
    """
    ✅ 修改特定结点字段内容。需要修改现有字段时，使用此工具
    filename 为 .dot 类型，路径为：/workspace/AegisGraph/AegisGraph_Megatron-LM/Chain/DOT/agent_output
    node_name 为节点全称，对应图上每个节点（表格）最上方的一行内容
    """
    new_value = new_value.replace('<module>', '&lt;module&gt;')
    content = load_dot(filename)
    pattern = rf'("{re.escape(node_name)}".*?)(<FONT.*?>){field}:.*?(</FONT>)'
    replacement = rf'\1\2{field}: {new_value}\3'
    content, count = re.subn(pattern, replacement, content, flags=re.DOTALL)
    save_dot(filename, content)
    dot_to_png(filename)
    return f"[modify_field ✅] {count} occurrence(s) updated."


@tool
def add_field(filename: str, node_name: str, field: str, value: str, color: str = "#AAFFAA") -> str:
    """
    ✅ 增加字段内容并指定背景色。需要添加新字段时，使用此工具
    filename 为 .dot 类型，路径为：/workspace/AegisGraph/AegisGraph_Megatron-LM/Chain/DOT/agent_output
    node_name 为节点全称，对应图上每个节点（表格）最上方的一行内容
    """
    value = value.replace('<module>', '&lt;module&gt;')
    content = load_dot(filename)
    insert_pattern = rf'("{re.escape(node_name)}".*?</TR>)'
    insert_html = (
        f'<TR><TD ALIGN="LEFT" BGCOLOR="{color}">'
        f'<FONT FACE="WenQuanYi Micro Hei, WenQuanYi Zen Hei, DejaVu Sans" COLOR="#000000">'
        f'{field}: {value}'
        f'</FONT></TD></TR>'
    )
    replacement = rf'\1{insert_html}'
    content, count = re.subn(insert_pattern, replacement, content, flags=re.DOTALL)
    save_dot(filename, content)
    dot_to_png(filename)
    return f"[add_field ✅] Added {field} to {node_name}, count={count}"
    

@tool
def delete_node(filename: str, node_name: str) -> str:
    """
    ✅ 删除节点与连接边。
    filename 为 .dot 类型，路径为：/workspace/AegisGraph/AegisGraph_Megatron-LM/Chain/DOT/agent_output
    node_name 为节点全称，对应图上每个节点（表格）最上方的一行内容
    """
    import re

    content = load_dot(filename)
    esc = re.escape(node_name)

    # ✅ 精确统计节点定义
    node_def_pattern = rf'"{esc}"\s*\[.*?\]'
    node_defs = re.findall(node_def_pattern, content, flags=re.DOTALL)
    node_def_count = len(node_defs)

    # ✅ 精确统计边引用
    edge_pattern = (
        rf'"{esc}"\s*->\s*".*?"(?:\s*\[.*?\])?'
        rf'|".*?"\s*->\s*"{esc}"(?:\s*\[.*?\])?'
    )
    edge_defs = re.findall(edge_pattern, content, flags=re.DOTALL)
    edge_def_count = len(edge_defs)

    # ✅ 移除节点和边
    content = re.sub(node_def_pattern, "", content, flags=re.DOTALL)
    content = re.sub(edge_pattern, "", content, flags=re.DOTALL)

    # ✅ 移除残留空边（防止 "} -> }" 异常）
    content = re.sub(r'->\s*}', "}", content)

    # ✅ 清理空行与多余空格
    content = re.sub(r'\n\s*\n+', '\n', content)
    content = re.sub(r'}\s*$', '}\n', content)

    save_dot(filename, content)
    dot_to_png(filename)

    return f"[delete_node ✅] node removed: 1, edges removed: {edge_def_count}"


@tool
def analysis_chain_graph(image_path: str) -> str:
    """
    对潜在漏洞调用图进行分析
    """
    with open(image_path, "rb") as image_file:
        base64_image = base64.b64encode(image_file.read()).decode('utf-8')

        analysis_prompt = """
对潜在漏洞调用图进行分析，并给出后续源码审计建议。

**调用链定义**：
- 起点：<module> 入口函数
- 终点：sink 点（红色标注区域，颜色为 #FF8080）
- 路径：从 <module> 到 sink 点的完整函数调用序列

**图例说明**：
- 🔴 红色区域：可能的 sink 点（危险函数），请先正确提取出所有sink点，再逐一进行漏洞分析
- 🟡 黄色区域：可能的 source 点（数据来源）

## 重要提醒：要仔细辨别红色区域，准确提取所有sink点，只有包含红色（#FF8080）区域（vulnerable_sink）的函数才是sink点！
"""

    messages = [
        HumanMessage(
            content=[
                {"type": "text", "text": analysis_prompt},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{base64_image}"
                    }
                }
            ]
        )
    ]

    response = model.invoke(messages)
    return response

from neo4j import GraphDatabase
driver = GraphDatabase.driver("bolt://172.16.167.35:7687", auth=("neo4j", "password"))
@tool
def neo4j_execute_cmd(cmd: str) -> str:
    """执行 neo4j 图谱相关指令"""
    logger.info(f"要执行的命令为：{cmd}")
    with driver.session() as session:
        cmd_result = session.run(cmd).data()
    
    # 需要过滤的字段列表
    fields_to_filter = [
        'attack_source_embeds',
        'control_flow_analysis_embeds',
        'data_flow_analysis_embeds',
        'function_summary_embeds'
    ]
    
    # 过滤结果
    filtered_result = []
    for record in cmd_result:
        filtered_record = {}
        for key, value in record.items():
            # 如果是字典类型，递归过滤
            if isinstance(value, dict):
                filtered_record[key] = {
                    k: v for k, v in value.items() 
                    if k not in fields_to_filter
                }
            else:
                # 如果key不在过滤列表中，保留
                if key not in fields_to_filter:
                    filtered_record[key] = value
        filtered_result.append(filtered_record)
    
    return f"命令执行结果为：{filtered_result}"


@tool
def read_file(path: str, line: int = None, context_lines: int = 30) -> str:
    """
    读取指定路径的代码文件内容。默认情况下，不用传 line 和 context_lines 参数，只有要读取的代码文件过大的时候，再传参。
    
    Args:
        path: 文件路径
        line: 可选，指定行号（从1开始）。如果提供，则只返回该行前后context_lines行的内容
        context_lines: 当指定line时，返回目标行前后的行数，默认30行
    
    Returns:
        文件内容或错误信息
    
    Examples:
        read_file("main.py")  # 读取整个文件
        read_file("main.py", line=50)  # 读取第50行前后30行
        read_file("main.py", line=50, context_lines=20)  # 读取第50行前后20行
    """
    if not os.path.exists(path):
        return (
            f"❌ 文件路径不存在: {path}"
            f"建议重新识别图片，按照以下顺序依次进行排查文件路径是否识别错误："
            f"      1. 是否存在字母拼写或顺序错误"
            f"      2. 是否有下划线或其他符号的丢失"
            f"      3. 在拼接源码文件路径时是否出现拼接错误"
        )
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        total_lines = len(lines)
        
        # 如果指定了行号，返回该行前后的内容
        if line is not None:
            if line < 1 or line > total_lines:
                return f"❌ 行号 {line} 超出范围（文件共 {total_lines} 行）"
            
            start_line = max(1, line - context_lines)
            end_line = min(total_lines, line + context_lines)
            
            result = f"📄 文件 {path} (第 {start_line}-{end_line} 行，共 {total_lines} 行)\n"
            result += f"{'='*60}\n"
            
            for i in range(start_line - 1, end_line):
                line_num = i + 1
                prefix = "➤ " if line_num == line else "  "
                result += f"{prefix}{line_num:4d} | {lines[i]}"
                if not lines[i].endswith('\n'):
                    result += '\n'
            
            return result
        
        # 读取全部内容
        content = ''.join(lines)
        
        # 估算token数（粗略估计：1 token ≈ 4 字符）
        estimated_tokens = len(content) / 4
        max_tokens = 100000  # 为128K留出余量，用于对话和响应
        
        if estimated_tokens > max_tokens:
            # 计算可以安全显示的字符数
            safe_chars = int(max_tokens * 4)
            preview_lines = int(total_lines * safe_chars / len(content))
            
            return (
                f"⚠️ 文件 {path} 内容过大\n"
                f"📊 统计信息:\n"
                f"  - 总行数: {total_lines}\n"
                f"  - 总字符数: {len(content):,}\n"
                f"  - 估算tokens: {int(estimated_tokens):,}\n"
                f"  - 超出限制: {int(estimated_tokens - max_tokens):,} tokens\n\n"
                f"💡 建议:\n"
                f"  1. 使用 read_file('{path}', line=N) 读取特定行附近的代码\n"
                f"  2. 文件可分约 {int(estimated_tokens / max_tokens) + 1} 次读取\n"
                f"  3. 前 {preview_lines} 行预览如下:\n\n"
                f"{'='*60}\n"
                + ''.join(f"{i+1:4d} | {lines[i]}" for i in range(min(preview_lines, total_lines)))
            )
        
        # 文件大小合适，返回完整内容
        result = f"📄 文件 {path} (共 {total_lines} 行)\n"
        result += f"{'='*60}\n"
        
        for i, line_content in enumerate(lines, 1):
            result += f"{i:4d} | {line_content}"
            if not line_content.endswith('\n'):
                result += '\n'
        
        return result
        
    except UnicodeDecodeError:
        return f"⚠️ 文件编码错误: {path} (可能是二进制文件)"
    except Exception as e:
        return f"⚠️ 读取文件出错: {e}"


tools = [modify_field, add_field, delete_node, analysis_chain_graph, neo4j_execute_cmd, read_file]
tools_by_name = {tool.name: tool for tool in tools}
inst_model_with_tools = model.bind_tools(tools)


# ======================================================
# ✅ LangGraph 状态
# ======================================================
class State(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]
    llm_calls: int


# ======================================================
# ✅ LLM 主调用节点
# ======================================================
def llm_node(state: State):
    response = inst_model_with_tools.invoke(
        [
            SystemMessage(content="""
            你的任务是：
            1. 解析调用图中的所有调用链；
            2. 对每条调用链，分析需要阅读哪些相关源码；
            3. 结合源码逻辑，判断该调用链是否可能存在漏洞；
            4. 将分析结论标记回调用图中（例如标记“存在漏洞”或“无漏洞”）。
            注意：在你的分析过程中，你可以对调用图进行修改，你可以通过在图中增删结点或修改内容的方式来标注你的阶段性分析结果；在修改完调用图后，你要重新读取调用图文件以获取到最新的调用图信息，避免针对同一内容的重复分析；你要谨慎规划你的行为逻辑，你要尽量以最小的开销完成对调用图的全面分析。你是经验丰富的安全专家，因此你不应该遗漏任何一条存在的漏洞调用链。你给出的结论应该尽量准确、完整，有理有据的给出漏洞是否存在的结论。
            """),
            *state["messages"]
        ]
    )
    return {
        "messages": [response],
        "llm_calls": state.get("llm_calls", 0) + 1,
    }


# ======================================================
# ✅ Tool 执行节点
# ======================================================
def tool_exec_node(state: State):
    results = []
    last_msg = state["messages"][-1]

    for call in getattr(last_msg, "tool_calls", []):
        tool_fn = tools_by_name[call["name"]]
        result = tool_fn.invoke(call["args"])
        results.append(ToolMessage(content=str(result), tool_call_id=call["id"]))

    return {"messages": results}


# ======================================================
# ✅ 边控制逻辑
# ======================================================
def should_continue(state: State) -> Literal["tool_exec", END]:
    last = state["messages"][-1]
    # logger.debug("**********messages**********\n" + str(last) + "\n" + "******************************")
    if getattr(last, "tool_calls", None):
        return "tool_exec"
    return END


# ======================================================
# ✅ Graph 构建与编译
# ======================================================
graph = StateGraph(State)
graph.add_node("llm", llm_node)
graph.add_node("tool_exec", tool_exec_node)

graph.add_edge(START, "llm")
graph.add_conditional_edges("llm", should_continue, ["tool_exec", END])
graph.add_edge("tool_exec", "llm")

agent = graph.compile()


# ======================================================
# ✅ DEMO 调用
# ======================================================
if __name__ == "__main__":
    user_prompt = """
请对以下调用图进行分析：/workspace/AegisAgent/PNG/0002_tools.openwebtext.find_duplicates.<module>.png

## 项目上下文信息
- 项目源码路径：
  `/workspace/target_projects_with_vuls/Megatron-LM`
- 图中每个节点的最上方一行表示函数的完整路径，例如：`xxx.yyy.zzz`
  - 其中最后的 `.zzz` 通常为函数名或模块名；
  - 在拼接源码文件路径时，应去掉 `.zzz`，再追加 `.py`，从而定位到源码文件。
  - 例如：表格最上方的函数名为 megatron.training.arguments.parse_args，则该模块对应的源码位于 /workspace/AegisGraph/AegisGraph_Megatron-LM/SourceCode/Megatron-LM/megatron/training/arguments.py
  - 注意函数名提取的准确性！！非常重要！！函数名必须提取准确，这关系着漏洞分析链路能否走通！在提取名称时，要注意名称中的下划线不要丢失！
- 请你逐字符提取图片中显示的完整模块路径
  - 你必须逐段检查（按“.”分段）
  - 不得自动纠错、不得自作主张地改写、联想、补全
  - 如果某个字符 不确定，你必须输出：“我无法从图片中确定这个字符，请要求用户提供更清晰的图像或高分辨率区域截图”
  - 绝不能凭经验猜测。
- 若多个节点属于同一个脚本文件，仅需读取该文件源码一次。

## 工具使用规范
默认情况下，在使用read_file工具进行代码读取时，不用传 line 和 context_lines 参数，如果代码文件过大，会返回相应提醒，才需要根据行号读取部分代码。

## 任务完成标准
当且仅当所有 sink 已分析并在图上完成“漏洞结论标注 + 漏洞触发路径”后，任务结束。

    """
    result = agent.invoke({"messages": [HumanMessage(content=user_prompt)]}, {"recursion_limit": 100}, print_mode = "debug")
    for m in result["messages"]:
        m.pretty_print()
    output_file = "/workspace/AegisGraph/result/result.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        messages_data = []
        for m in result["messages"]:
            # 使用 dict() 方法转换
            if hasattr(m, 'dict'):
                messages_data.append(m.dict())
            else:
                messages_data.append({
                    "type": m.__class__.__name__,
                    "content": m.content
                })
        
        json.dump(messages_data, f, ensure_ascii=False, indent=2)
