import os
import logging
from typing import Optional, Tuple
from langchain.tools import tool
from langchain.messages import HumanMessage
from neo4j import GraphDatabase
from .dot2png import dot2png
from langchain_openai import ChatOpenAI
import re, json, base64, ast
from qwen_chat_manager import advanced_json_loader, chat_with_mllm
from node_analyze_workflow import filter_module_executable_code, get_existing_function_body
# 设置日志
logger = logging.getLogger(__name__)

# ======================================================
# ✅ 工具函数实现
# ======================================================
AGENT_INSTANCE = None
    
# def _extract_key_codes(function_name: str, focuses: list[str] = None) -> str:
#     vulnerable_sink = AGENT_INSTANCE.current_sink
#     if(focuses == None):
#         focuses = [
#             f"在调用{vulnerable_sink}函数所使用的配置项是什么？是否是安全的？",
#             "传给下一跳函数的变量是什么？是否属于污点源（攻击者可控的外部文件、网络数据）或是可能被污点传播？",
#             "该函数在调用哪些被调函数时进行了污点传播？具体传播的变量是什么？",
#             f"代码中是否对污点变量进行了安全检查以避免{vulnerable_sink}漏洞？",
#             f"代码中是否针对性实现了对{vulnerable_sink}漏洞的安全消毒方案？"
#         ]

#     func_body = get_existing_function_body(function_name)
#     if(func_body == None):
#         return f"ERROR: {function_name}不属于目标项目中的代码，请确认该名称是否与图中给出的函数名一致，或者是否来自第三方package"

#     fcstr = '\n- '.join(focuses)
#     with open(f"prompts/_extract_key_codes.prompt.{AGENT_INSTANCE.language}.md", "r") as f:
#         prompt_template = f.read()
#     prompt = prompt_template.replace("{func_body}", func_body).replace("{function_name}", function_name).replace("{focuses}", fcstr)
#     with open(AGENT_INSTANCE.current_png_path, "rb") as image_file:
#         base64_image = base64.b64encode(image_file.read()).decode('utf-8')
#     messages = [HumanMessage(content=[
#         {"type": "text", "text": prompt},
#         {
#             "type": "image",
#             "base64": base64_image,
#             "mime_type": "image/png",
#         }
#     ])]
#     resp = AGENT_INSTANCE.inst_model.invoke(messages).content

#     jobj = advanced_json_loader(resp)
#     if(jobj == None):
#         resp = AGENT_INSTANCE.think_model.invoke(messages).content
#         jobj = advanced_json_loader(resp)
#         if(jobj == None):
#             AGENT_INSTANCE.add_function_summary_to_png(function_name, resp)
#             return "已更新至代码执行流中。"

#     sum = jobj['summary']
#     key_codes_in_function = jobj.get('key_codes_in_function', None)

#     # if(len(key_codes_in_function.split("\n")) > 15):
#     #     resp = AGENT_INSTANCE.think_model.invoke(messages).content
#     #     jobj = advanced_json_loader(resp)
#     #     if(jobj == None):
#     #         AGENT_INSTANCE.add_function_summary_to_png(function_name, resp)
#     #         return "已更新至代码执行流中。"
#     #     sum = jobj['summary']
#     #     key_codes_in_function = jobj.get('key_codes_in_function', None)

#     sum_dict = {}
#     for kw in ["security_sanitizer", "taint_propagation"]: #"attack_source", 
#         is_kw = f"is_{kw}"
#         if(jobj[is_kw] == True):
#             sum_dict[kw] = jobj[f"{kw}_analysis"]
#     if(sum_dict == {}):
#         sum_dict['summary'] = sum
#     sum_dict['key_codes'] = key_codes_in_function

#     AGENT_INSTANCE.add_function_summary_dict_to_png(function_name, sum_dict)
#     return "已更新至代码执行流中。"

@tool
def add_new_function(function: str, callers: list[str]) -> str:
    """
    向当前调用图中添加新的函数，以及相应的 *直接* 调用关系    
    Args:
        function:要调用的函数名，要求必须是出现在当前调用图的函数代码中的，且不能是builtin或external
        callers:调用者函数全名列表，要求必须是当前图中函数，且是function代表函数的直接调用者
    Returns:
        str: 关于执行成功与否的结果描述

    """
    # 检查AGENT_INSTANCE是否已初始化
    if AGENT_INSTANCE is None:
        return "ERROR: AGENT_INSTANCE is not initialized, cannot add new function"
    
    # 获取当前图信息和函数分析记录
    current_graph_info = AGENT_INSTANCE.current_graph_info
    function_analysis_records = AGENT_INSTANCE.function_analysis_records
    call_graph = current_graph_info.get("call_graph", [])
    
    # 1. 参数验证
    if not callers:
        return "ERROR: callers list cannot be empty, at least one caller is required"
    
    # 检查所有调用者是否存在于图中
    all_functions = set()
    for edge in call_graph:
        all_functions.add(edge["caller"])
        all_functions.add(edge["callee"])
    
    missing_callers = []
    for caller in callers:
        if caller not in all_functions:
            missing_callers.append(caller)
    
    if missing_callers:
        return f"ERROR: The following callers are not in the current call graph: {missing_callers}"
    
    # 2. 检查要添加的函数是否已经在图中（使用全名检查）
    # function参数可能是短的函数名，需要先查找对应的全名
    full_function_name = None
    
    # 3. 查找函数的全名
    # 查询每个caller调用的函数，找到以".{function}"结尾的函数全名
    full_function_names = set()
    
    for caller in callers:
        try:
            # 查询caller调用的所有函数
            query = """
            MATCH (caller:Function {name: $caller_name})-[:CALLS]->(callee:Function)
            RETURN callee.name AS callee_name
            """
            
            with AGENT_INSTANCE.neo4j_driver.session() as session:
                result = session.run(query, caller_name=caller)
                for record in result:
                    callee_name = record["callee_name"]
                    # 检查是否以".{function}"结尾
                    if callee_name.endswith(f".{function}"):
                        full_function_names.add(callee_name)
        except Exception as e:
            return f"ERROR: Failed to query functions called by {caller}: {str(e)}"
    
    if not full_function_names:
        return f"ERROR: No function ending with '.{function}' found among the functions called by the specified callers"
    
    # 如果有多个匹配，选择第一个
    full_function_name = list(full_function_names)[0]
    
    # 检查找到的全名是否已经在图中
    if full_function_name in all_functions:
        return f"ERROR: Function {full_function_name} already exists in the call graph"
    
    # 4. 验证函数是否存在于项目中
    func_body = get_existing_function_body(AGENT_INSTANCE.neo4j_driver, full_function_name)
    if func_body is None:
        return f"ERROR: Function {full_function_name} is not found in the project code or is a builtin/external function"
    
    # 5. 添加新的调用关系
    for caller in callers:
        # 检查是否已经存在相同的调用关系
        existing_edge = any(edge["caller"] == caller and edge["callee"] == full_function_name for edge in call_graph)
        if not existing_edge:
            call_graph.append({
                "caller": caller,
                "callee": full_function_name,
                "label": "calls"
            })
    
    # 6. 更新current_graph_info
    current_graph_info["call_graph"] = call_graph
    
    # 7. 提取新函数的关键代码和分析信息
    # 由于不知道新函数会调用哪些函数，传递空列表作为callees
    try:
        from node_analyze_workflow import NodeAnalyzeWorkflow
        
        # 提取关键代码和分析信息，callees为空列表
        sum_dict = NodeAnalyzeWorkflow(
            AGENT_INSTANCE.neo4j_driver,
            AGENT_INSTANCE.language,
            AGENT_INSTANCE.inst_model,
            AGENT_INSTANCE.think_model
        ).extract_key_codes(
            function_name=full_function_name,
            png_path=AGENT_INSTANCE.current_png_path,
            callees=[],  # 空列表，因为不知道新函数会调用哪些函数
            focuses=None,
            sink=current_graph_info.get("sink_name")
        )
        
        # 将分析结果添加到function_analysis_records
        if isinstance(sum_dict, dict):
            for kw, desc in sum_dict.items():
                function_analysis_records.setdefault(full_function_name, {})[kw] = desc
        else:
            # 如果返回的是字符串（错误信息），则只添加summary
            function_analysis_records.setdefault(full_function_name, {})["summary"] = str(sum_dict)
            
    except Exception as e:
        # 如果提取失败，至少添加一个空的记录
        return f"ERROR: Failed to extract key codes: {str(e)}"
    
    # 8. 重新生成可视化
    try:
        AGENT_INSTANCE.path_visualizer.create_entry_sink_callgraph(
            AGENT_INSTANCE.current_png_path,
            current_graph_info,
            function_analysis_records
        )
    except Exception as e:
        return f"ERROR: Failed to regenerate visualization: {str(e)}"
    
    # 返回成功信息
    callers_str = ", ".join(callers)
    return f"Successfully added function {full_function_name} (matched from '{function}') to the call graph with callers: {callers_str}"

@tool
def compress_call_chain(start_function: str, intermediate_functions: list[str], end_function: str, new_edge_label: str) -> str:
    """
    压缩调用图中的非关键线性调用链，将intermediate_functions列表中的节点（要求至少一个）删除，并在start_function和end_function函数间建立直接调用边。
    
    intermediate_functions列表中的函数被认定为“非关键”时需同时满足以下条件：
    1. 与污点传播无关，或仅对污点数据做直接传递
    2. 对PoC构造不提供关键信息
    3. 未对污点数据实施有效校验，或不构成对sink点漏洞的有效防御
    
    线性调用链定义：从起始点到终止点之间的节点顺序执行，不存在分支进入或离开该链路（start/end节点除外）。
    
    Args:
        start_function: 调用链起始函数
        intermediate_functions：要删除的非关键中间函数的列表
        end_function: 调用链终止函数
        new_edge_label: 新建调用边的描述文本，可参考：
        - "经过{intermediate_functions}的调用链, {start_function}函数的xxx变量直接传递到{end_function}的xxx变量，过程中未实施有效的安全校验或安全措施" 
        - "经过{intermediate_functions}的调用链, {start_function}函数间接调用到了{end_function}，过程中未进行污点变量传递也未实施有效的安全校验或安全措施" 
    
    Returns:
        str: 执行结果描述（成功/失败及原因）
    
    注意：在一次工具调用的规划过程中，就要在满足要求的前提下把intermediate_functions提取的足够长。
    """
    # 检查AGENT_INSTANCE是否已初始化
    if AGENT_INSTANCE is None:
        return "ERROR: AGENT_INSTANCE is not initialized, cannot perform compression operation"
    
    # 获取当前图信息和函数分析记录
    current_graph_info = AGENT_INSTANCE.current_graph_info
    function_analysis_records = AGENT_INSTANCE.function_analysis_records
    call_graph = current_graph_info.get("call_graph", [])
    
    # 1. 参数验证
    if not intermediate_functions:
        return "ERROR: intermediate_functions list cannot be empty, at least one intermediate function is required"
    
    # 检查所有函数是否存在于图中
    all_functions = set()
    for edge in call_graph:
        all_functions.add(edge["caller"])
        all_functions.add(edge["callee"])
    
    missing_functions = []
    for func in [start_function, end_function] + intermediate_functions:
        if func not in all_functions:
            missing_functions.append(func)
    
    if missing_functions:
        return f"ERROR: The following functions are not in the current call graph: {missing_functions}"
    
    # 2. 验证线性调用链
    # 构建完整的调用链：start_function -> intermediate_functions[0] -> ... -> end_function
    full_chain = [start_function] + intermediate_functions + [end_function]
    
    # 检查调用链是否连续
    for i in range(len(full_chain) - 1):
        caller = full_chain[i]
        callee = full_chain[i + 1]
        
        # 检查是否存在直接的调用关系
        edge_exists = any(edge["caller"] == caller and edge["callee"] == callee for edge in call_graph)
        if not edge_exists:
            return f"ERROR: Call chain is not continuous, missing {caller} -> {callee} call relationship"
    
    # 3. 检查中间函数的调用关系（确保无分支）
    for i, func in enumerate(intermediate_functions):
        # 获取调用该函数的所有调用者
        callers = [edge["caller"] for edge in call_graph if edge["callee"] == func]
        # 获取该函数调用的所有被调用者
        callees = [edge["callee"] for edge in call_graph if edge["caller"] == func]
        
        # 中间函数应该只有一个调用者（前一个函数）和一个被调用者（后一个函数）
        expected_caller = start_function if i == 0 else intermediate_functions[i - 1]
        expected_callee = end_function if i == len(intermediate_functions) - 1 else intermediate_functions[i + 1]
        
        if len(callers) != 1 or callers[0] != expected_caller:
            return f"ERROR: Intermediate function {func} does not meet linear chain requirements, expected caller: {expected_caller}, actual callers: {callers}"
        
        if len(callees) != 1 or callees[0] != expected_callee:
            return f"ERROR: Intermediate function {func} does not meet linear chain requirements, expected callee: {expected_callee}, actual callees: {callees}"
    
    # 4. 更新调用图
    # 删除涉及中间函数的边
    edges_to_remove = []
    for i in range(len(full_chain) - 1):
        caller = full_chain[i]
        callee = full_chain[i + 1]
        edges_to_remove.append((caller, callee))
    
    # 创建新的调用图，删除旧边
    new_call_graph = []
    for edge in call_graph:
        if (edge["caller"], edge["callee"]) not in edges_to_remove:
            new_call_graph.append(edge)
    
    # 添加新的直接调用边
    # 处理new_edge_label中的占位符
    formatted_label = new_edge_label
    if "{intermediate_functions}" in new_edge_label:
        intermediate_str = " -> ".join(intermediate_functions)
        formatted_label = formatted_label.replace("{intermediate_functions}", intermediate_str)
    if "{start_function}" in new_edge_label:
        formatted_label = formatted_label.replace("{start_function}", start_function)
    if "{end_function}" in new_edge_label:
        formatted_label = formatted_label.replace("{end_function}", end_function)
    
    new_call_graph.append({
        "caller": start_function,
        "callee": end_function,
        "label": formatted_label
    })
    
    # 更新current_graph_info
    current_graph_info["call_graph"] = new_call_graph
    
    # 5. 重新生成可视化
    try:
        AGENT_INSTANCE.path_visualizer.create_entry_sink_callgraph(
            AGENT_INSTANCE.current_png_path,
            current_graph_info,
            function_analysis_records
        )
    except Exception as e:
        return f"ERROR: Failed to regenerate visualization: {str(e)}"
    
    # 返回成功信息
    intermediate_str = " -> ".join(intermediate_functions)
    return f"Successfully compressed call chain: {start_function} -> [{intermediate_str}] -> {end_function} has been compressed to {start_function} -> {end_function}, new edge label: '{formatted_label}'"

@tool
def update_function_node(function: str, updates: dict) -> str:
    """
    对调用图中的函数节点下方的文件描述和关键信息进行更新，如修改不准确的信息描述、精简关键代码片段(如删除下一跳函数调用之后的一些无关代码)
    Args:
        function:要更新的函数名
        updates:包含更新信息的字典，可以选择性包含以下key：
            - security_sanitizer: 安全消毒分析（如包含安全消毒代码时填写）
            - taint_propagation: 污点传播分析（如包含污点传播代码时填写）
            - summary: 函数摘要（如需要更新整体描述时填写）
            - key_codes: 关键代码片段（如需要精简关键代码片段或更正描述时填写）

    Returns:
        str: 关于执行成功与否的结果描述

    """
    # 检查AGENT_INSTANCE是否已初始化
    if AGENT_INSTANCE is None:
        return "ERROR: AGENT_INSTANCE is not initialized, cannot update function node"
    
    # 获取当前图信息和函数分析记录
    current_graph_info = AGENT_INSTANCE.current_graph_info
    function_analysis_records = AGENT_INSTANCE.function_analysis_records
    
    # 1. 检查函数是否存在于图中
    all_functions = set()
    call_graph = current_graph_info.get("call_graph", [])
    for edge in call_graph:
        all_functions.add(edge["caller"])
        all_functions.add(edge["callee"])
    
    if function not in all_functions:
        return f"ERROR: Function {function} is not in the current call graph"
    
    # 2. 验证updates参数
    if not isinstance(updates, dict):
        return "ERROR: updates parameter must be a dictionary"
    
    # 检查updates中是否包含有效的key
    valid_keys = {"security_sanitizer", "taint_propagation", "summary", "key_codes"}
    updates_keys = set(updates.keys())
    
    if not updates_keys.intersection(valid_keys):
        return f"ERROR: updates dictionary must contain at least one of the valid keys: {valid_keys}"
    
    # 检查是否有无效的key
    invalid_keys = updates_keys - valid_keys
    if invalid_keys:
        return f"ERROR: updates dictionary contains invalid keys: {invalid_keys}. Valid keys are: {valid_keys}"
    
    # 3. 确保函数有分析记录（如果没有，创建一个空的）
    if function not in function_analysis_records:
        function_analysis_records[function] = {}
    
    # 4. 更新函数分析记录
    func_record = function_analysis_records[function]
    
    # 更新指定的字段
    updated_fields = []
    for key in valid_keys:
        if key in updates:
            func_record[key] = updates[key]
            updated_fields.append(key)
    
    # 5. 重新生成可视化
    try:
        AGENT_INSTANCE.path_visualizer.create_entry_sink_callgraph(
            AGENT_INSTANCE.current_png_path,
            current_graph_info,
            function_analysis_records
        )
    except Exception as e:
        return f"ERROR: Failed to regenerate visualization: {str(e)}"
    
    # 返回成功信息
    updated_str = ", ".join(updated_fields)
    return f"Successfully updated function {function}: {updated_str}"
