import json, ast
import base64
from langchain.messages import HumanMessage, AIMessage
from qwen_chat_manager import advanced_json_loader
import logging
import os
import re

# 设置日志
logger = logging.getLogger(__name__)

class NodeAnalyzeWorkflow:
    def __init__(self, neo4j_driver, language, inst_model, think_model):
        """
        初始化 NodeAnalyzeWorkflow
        
        Args:
            neo4j_driver: Neo4j 数据库驱动
            language: 语言代码（如 'CN' 或 'EN'）
            inst_model: 指令模型实例
            think_model: 思考模型实例（可选）
        """
        self.neo4j_driver = neo4j_driver
        self.language = language
        self.inst_model = inst_model
        self.think_model = think_model
    
    def extract_codes_before_callees(self, function_name: str, callees: list[str], sink:str = None) -> str:
        full_body = get_existing_function_body(self.neo4j_driver, function_name)
        full_body_splits = full_body.split("\n")
        
        last_line_idx = -1
        match_targets = []
        for cle in callees:
            if(sink and cle == sink):
                match_targets.append(sink + "(")
            else:
                match_targets.append(cle.split(".")[-1] + "(")

        for idx, line in enumerate(full_body_splits):
            for t in match_targets:
                if(t in line):
                    last_line_idx = idx
        if(last_line_idx == -1):
            return full_body
        else:
            if(last_line_idx == len(full_body_splits) - 1):
                return "\n".join(full_body_splits[:last_line_idx + 1])
            else:
                ret_list = full_body_splits[:last_line_idx + 1]
                ret_list.append("# ...")
                return "\n".join(ret_list)

        # full_body = get_existing_function_body(self.neo4j_driver, function_name)
        # with open(f"prompts/extract_codes_before_callees.prompt.{self.language}.md", "r") as f:
        #     prompt_template = f.read()
        # prompt = prompt_template.replace("{full_body}", full_body).replace("{function_name}", function_name)
        # messages = [HumanMessage(content=[
        #     {"type": "text", "text": prompt},
        #     {
        #         "type": "image",
        #         "base64": base64_image,
        #         "mime_type": "image/png",
        #     }
        # ])]
        # resp = self.inst_model.invoke(messages).content
        # # jobj = advanced_json_loader(resp)
        # # logger.info(f"{function_name}的callee前代码提取结果：\n{json.dumps(jobj, indent=2, ensure_ascii=False)}")
        # # ret = resp
        # # return jobj['pre_call_code']

        # pattern = r'```python\n(.*?)\n```'
        # match = re.search(pattern, resp, re.DOTALL)
        # if match:
        #     ret = match.group(1)
        #     return ret
        # return None


    def extract_key_codes(self, function_name: str, png_path: str, callees: list[str], focuses: list[str] = None, sink: str = None) -> str:
        if(focuses == None):
            if(self.language == "CN"):
                focuses = [
                    "污点分析（taint_propagation_analysis）：传给下游函数的变量是什么？是否属于污点源（攻击者可控的外部文件、网络数据）或是可能被污点传播？",
                    "污点分析（taint_propagation_analysis）：该函数在调用哪些被调函数时进行了污点传播？具体传播的变量是什么？",
                    "安全措施分析（security_sanitizer_analysis）：代码中是否对污点变量进行了安全检查以避免vulnerable_sink点的漏洞发生？",
                    "安全措施分析（security_sanitizer_analysis）：代码中是否针对性实现了对vulnerable_sink点的漏洞安全消毒方案？",
                    "安全措施分析（security_sanitizer_analysis）：在调用图中下游函数时所使用的配置项是什么？是否是安全的？",
                ]
            else:
                focuses = [
                    "taint propagation analysis: Which variables are passed to downstream functions in the vulnerable call graph? Are they taint source (attacker-controllable external files, network data) or may be subject to taint propagation?",
                    "taint propagation analysis: When calling down-stream functions, does this function propagate taint variables? Which variables are propagated?",
                    "security sanitizer analysis: Does the code perform security checks on taint variables to avoid vulnerabilities at vulnerable_sink point?",
                    "security sanitizer analysis: Does the code specifically implement security sanitization solutions to avoid vulnerabilities at vulnerable_sink point?",
                    "security sanitizer analysis: What configurations are used when calling downstream functions in the call graph? Are they secure or vulnerable?",
                ]

        with open(png_path, "rb") as image_file:
            base64_image = base64.b64encode(image_file.read()).decode('utf-8')

        func_body = self.extract_codes_before_callees(function_name, callees, sink)
        # logger.debug(f"{function_name}提取的关键调用前的函数代码：\n{func_body}")
        logger.debug(f"{function_name} extracted key function code before calls:\n{func_body}")
        if(func_body == None):
            return f"ERROR: {function_name}不属于目标项目中的代码，请确认该名称是否与图中给出的函数名一致，或者是否来自第三方package"

        fcstr = '\n- '.join(focuses)
        with open(f"prompts/extract_key_codes.prompt.{self.language}.md", "r") as f:
            prompt_template = f.read()
        prompt = prompt_template.replace("{func_body}", func_body).replace("{function_name}", function_name).replace("{focuses}", fcstr)

        messages = [HumanMessage(content=[
            {"type": "text", "text": prompt},
            {
                "type": "image",
                "base64": base64_image,
                "mime_type": "image/png",
            }
        ])]
        resp = self.inst_model.invoke(messages).content
        jobj = advanced_json_loader(resp)

        fix_msg = None
        if(jobj == None):
            fix_msg = "json.loads failed on AI's response, fix it!"
        elif(len(jobj.get('key_codes_in_function').split("\n")) > 15):
            fix_msg = "key_codes_in_function is too long, simplify it and keep only the key code and variables ! ***NOTICE***: only return the simplified key_codes_in_function part in json format."

        if(fix_msg):
            logger.warning(f"LLM's response does not meet the requirements: {fix_msg}.")

            messages.append(
                AIMessage(content=resp)
            )
            messages.append(
                HumanMessage(content=fix_msg)
            )
            # resp = self.inst_model.invoke(messages).content
            resp = self.think_model.invoke(messages).content
            jobj_fix = advanced_json_loader(resp)
            if(jobj_fix == None):
                self.add_function_summary_to_png(function_name, jobj_fix)
                return "已更新至代码执行流中。"
            if(jobj):
                for k,v in jobj_fix.items():
                    jobj[k] = v
            else:
                jobj = jobj_fix

        sum = jobj['summary']
        key_codes_in_function = jobj.get('key_codes_in_function', None)

        # logger.debug(f"{function_name}的分析结果：\n{json.dumps(jobj, indent=2, ensure_ascii=False)}")
        logger.debug(f"{function_name} analysis result:\n{json.dumps(jobj, indent=2, ensure_ascii=False)}")

        # if(len(key_codes_in_function.split("\n")) > 15):
        #     resp = AGENT_INSTANCE.think_model.invoke(messages).content
        #     jobj = advanced_json_loader(resp)
        #     if(jobj == None):
        #         AGENT_INSTANCE.add_function_summary_to_png(function_name, resp)
        #         return "已更新至代码执行流中。"
        #     sum = jobj['summary']
        #     key_codes_in_function = jobj.get('key_codes_in_function', None)

        sum_dict = {}
        for kw in ["security_sanitizer", "taint_propagation"]: #"attack_source", 
            is_kw = f"is_{kw}"
            if(jobj[is_kw] == True):
                sum_dict[kw] = jobj[f"{kw}_analysis"]
        if(sum_dict == {}):
            sum_dict['summary'] = sum
        sum_dict['key_codes'] = key_codes_in_function
        return sum_dict
    
def filter_module_executable_code(code_string: str) -> str:
    """
    过滤模块级代码，只保留直接执行的语句
    忽略类定义和导入语句
    """
    try:
        tree = ast.parse(code_string)
        executable_statements = []
        
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                continue
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            executable_statements.append(node)
        
        if executable_statements:
            new_tree = ast.Module(body=executable_statements, type_ignores=[])
            return ast.unparse(new_tree)
        else:
            return ""
    except SyntaxError:
        # logger.warning("解析module可执行代码失败，返回全量原代码。")
        logger.warning("Failed to parse module executable code, returning full original code.")
        return code_string  # 如果解析失败，返回原代码


def get_existing_function_body(neo4j_driver, function_name) -> str:
    """
    获取函数函数体代码
    
    Args:
        function_name: 目标函数名（注意是图中展示的函数全名）
    
    Returns:
        函数体代码或错误信息
    """
    # 查询函数节点信息
    query = """
    MATCH (f:Function {name: $function_name})
    RETURN f.module_path AS module_path, f.start_line AS start_line, f.total_lines AS total_lines
    """
    
    try:
        with neo4j_driver.session() as session:
            result = session.run(query, function_name=function_name)
            record = result.single()
            
            if not record:
                # return f"错误：未找到名为 '{function_name}' 的函数"
                return None
            
            module_path = record["module_path"]
            start_line = record["start_line"]
            total_lines = record["total_lines"]
            
            if not module_path or not os.path.exists(module_path):
                # return f"错误：模块文件 '{module_path}' 不存在"
                return None
            
            # 读取文件并提取函数体
            with open(module_path, 'r', encoding='utf-8') as file:
                lines = file.readlines()
            
            # 计算函数体的行范围（注意：行号从1开始）
            start_idx = start_line - 1  # 转换为0-based索引
            end_idx = start_idx + total_lines
            
            # 确保行号在有效范围内
            if start_idx < 0 or end_idx > len(lines):
                # return f"错误：行号超出文件范围 (文件行数: {len(lines)}, 请求范围: {start_line}-{start_line + total_lines - 1})"
                return None
            
            # 提取函数体代码
            function_lines = lines[start_idx:end_idx]
            if function_name.endswith(".<module>"):
                fb = filter_module_executable_code(''.join(function_lines))
            else:
                fb = ''.join(function_lines)
            return fb

    except Exception as e:
        # return f"错误：查询函数信息时发生异常 - {str(e)}"
        return None
