import os
import logging
from typing import Literal, Annotated, List, Dict, Any
from typing_extensions import TypedDict
from langchain.messages import (
    AnyMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langgraph.graph import StateGraph, START, END
import operator
from langchain_openai import ChatOpenAI
import json
from .agent_tools import get_all_tools, get_tools_by_name
from neo4j import GraphDatabase
from .visualize_attack_paths import AttackPathVisualizer
from .agent_tools import AGENT_INSTANCE
import base64
from qwen_chat_manager import chat_with_mllm_with_probs, advanced_json_loader
import re
from xuanji_llm_service import LLM_SERVICE_INFO, XuanjiChatModel
# 设置日志
logger = logging.getLogger(__name__)


# ======================================================
# ✅ 状态定义
# ======================================================
class State(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]
    llm_calls: int

class AegisAgent:
    """
    AegisAgent - 漏洞调用图分析智能体
    封装了调用图分析、源码审计、漏洞检测等功能
    """
    
    def __init__(
        self,
        output_path: str,
        inst_model,
        think_model,
        neo4j_driver,
        language: str,
        png_path,
        function_analysis_records,
        target_vul_info
    ):
        """
        初始化AegisAgent
        
        Args:
            inst_model_name: 对话模型名称
            think_model_name: 推理模型名称
            dot_dir: DOT文件目录
            png_dir: PNG文件目录
            neo4j_uri: Neo4j数据库URI
            neo4j_auth: Neo4j认证信息
            temperature: 模型温度参数
            max_tokens: 最大token数
            language: 语言设置，可选"CH"或"EN"，默认为"CH"
        """
        self.output_path = output_path
        self.current_png_path = png_path
        self.language = language
        self.neo4j_driver = neo4j_driver
        
        self.inst_model = inst_model
        self.think_model = think_model
        self.path_visualizer = AttackPathVisualizer()
        self.current_graph_info = target_vul_info
        # 初始化工具
        self._init_tools()
        
        # 构建图
        self._build_graph()
    
        # 设置全局 AGENT_INSTANCE 引用
        import vul_analysis_agent.agent_tools
        vul_analysis_agent.agent_tools.AGENT_INSTANCE = self
        self.function_analysis_records = function_analysis_records
        self.in_mess = False

    def _init_tools(self):
        """初始化所有工具"""
        self.tools = get_all_tools(self.language)
        self.tools_by_name = get_tools_by_name(self.language)
        self.inst_model_with_tools = self.inst_model.bind_tools(self.tools)
        self.think_model_with_tools = self.think_model.bind_tools(self.tools)
    
    def _build_graph(self):
        """构建LangGraph图"""
        # 构建图
        graph = StateGraph(State)
        graph.add_node("llm", self._llm_node)
        graph.add_node("tool_exec", self._tool_exec_node)
        graph.add_edge(START, "llm")
        graph.add_conditional_edges("llm", self._should_continue, ["tool_exec", "llm", END])
        graph.add_edge("tool_exec", "llm")
        self.agent = graph.compile()
    
    def _llm_node(self, state: State):
        """LLM主调用节点"""
        msg = state["messages"]

        with open(f"prompts/llm_node.user_prompt.{self.language}.md", "r") as f:
            user_prompt = f.read()
        with open(self.current_png_path, "rb") as image_file:
            base64_image = base64.b64encode(image_file.read()).decode('utf-8')

        user_input = HumanMessage(content=[
            {"type": "text", "text": "最新的漏洞代码流程图如下。注意：节点名代表函数，节点下面的文字描述代表已通过工具获取的该函数信息，请勿重复获取！"},
            {
                "type": "image",
                "base64": base64_image,
                "mime_type": "image/png",
            }
        ])
        msg.append(user_input) # TODO，将msg历史对话中的图像内容清除
        if(self.in_mess):
            response = self.think_model_with_tools.invoke(msg)
            self.in_mess = False
        else:
            response = self.inst_model_with_tools.invoke(msg)
        return {
            "messages": [response],
            "llm_calls": state.get("llm_calls", 0) + 1,
        }
    
    def _tool_exec_node(self, state: State):
        """工具执行节点"""
        last_msg = state["messages"][-1]
        tcs = getattr(last_msg, "tool_calls", [])
        # logger.info(f"本轮推理输出：{last_msg.content}")
        logger.info(f"Current reasoning output: {last_msg.content}")
        # logger.info(f"本轮调用工具数：{len(tcs)}")
        logger.info(f"Current tool calls count: {len(tcs)}")

        results = []
        for call in tcs:
            tool_name = call["name"]
            tool_args = call["args"]
            # logger.info(f"- 工具名：{tool_name}")
            logger.info(f"- Tool name: {tool_name}")
            # logger.info(f"- 工具参数：{tool_args}")
            logger.info(f"- Tool arguments: {tool_args}")

            tool_fn = self.tools_by_name[tool_name]
            call_desc = f"调用{tool_name} (参数为{tool_args})"

            content = None
            for msg in state["messages"]:
                mct = str(msg.content)
                if(mct.startswith(call_desc)):
                    self.in_mess = True
                    content = f"重复调用！已有调用结果：{mct}"
                    break
            if(content == None):
                result = tool_fn.invoke(tool_args)
                if(result.startswith("ERROR")):
                    content = f"{call_desc} 失败：{result}"
                    self.in_mess = True
                else:
                    content = f"{call_desc} 成功：{result}"
            results.append(ToolMessage(content=content, tool_call_id=call["id"]))
        return {"messages": results}
    
    def _double_check(self, messages):
        with open(f"prompts/double_check.prompt.{self.language}.md", "r") as f:
            prompt = f.read()

        with open(self.current_png_path, "rb") as image_file:
            base64_image = base64.b64encode(image_file.read()).decode('utf-8')
        messages.append(HumanMessage(content=[
            {"type": "text", "text": prompt},
            {
                "type": "image",
                "base64": base64_image,
                "mime_type": "image/png",
            }
        ]))
        
        text = self.think_model.invoke(messages).content
        json_obj = advanced_json_loader(text)
        def _get_result_confidence(keyword, text_with_probs):
            # 查找最后一个 keyword 的 JSON 格式 "keyword": "true|0.9999"
            pattern = f'"{keyword}":\\s*"([^"]+)"'
            matches = re.findall(pattern, text_with_probs)
            
            # 取最后一个匹配项
            last_match = matches[-1]
            result_with_prob = last_match.split("|")
            
            # 提取 true/false 和浮点数
            result = result_with_prob[0].strip().lower() == "true"
            prob = float(result_with_prob[1].strip())
            return result, prob
        
        # logger.debug("double_check结果分析：")
        logger.debug("double_check result analysis:")
        # logger.debug(json_obj["feedback"])
        logger.debug(json_obj["feedback"])
        if(json_obj["is_accurate_and_complete"] == False):
            # logger.warning(f"- 模型认为当前信息不充分、不准确：")
            logger.warning(f"- Model considers current information insufficient or inaccurate:")
            # logger.warning(json_obj["feedback"])
            logger.warning(json_obj["feedback"])
            return json_obj["feedback"]

        self.current_graph_info["double_check"] = json_obj["feedback"]
        self.current_graph_info["conclusion"] = {
            "is_vulnerable": json_obj['is_vulnerable']
        }
        return END

    def _should_continue(self, state: State) -> Literal["tool_exec", "llm", END]:
        """边控制逻辑"""
        last = state["messages"][-1]
        if getattr(last, "tool_calls", None):
            return "tool_exec"
        
        jobj = advanced_json_loader(last.content)
        if(jobj):
            content = f"# 攻击数据可污染性分析\n{jobj['external_input_taint_analysis']}"
            content += f"\n\n# 安全消毒措施分析\n{jobj['security_anitization_analysis']}"
            content += f"\n\n# 漏洞利用条件分析\n{jobj['unsecure_call_analysis']}"
            content += f"\n\n# 需进一步确认的信息\n{jobj['to_be_confirmed']}"
            content += f"\n\n# 初步结论\n{'是漏洞!' if jobj['is_vulnerable'] else '不是漏洞!'}"
        else:
            content = last.content

        # logger.debug(f"Agent认为可以结束：\n{content}")
        logger.debug(f"Agent considers it can end:\n{content}")
        self.path_visualizer.create_entry_sink_callgraph(
            self.current_png_path, 
            self.current_graph_info, 
            self.function_analysis_records,
            additional_remarks = content)

        # return END  # TODO recover
    
        cr = self._double_check(state["messages"])

        if(cr == END):
            self.path_visualizer.create_entry_sink_callgraph(
                self.current_png_path, 
                self.current_graph_info,
                self.function_analysis_records,
                # additional_remarks = f"{content}\n---\n### 漏洞报告二次审计结论：\n{self.current_graph_info['double_check']}.\n---\nIS_VULNERABLE: {self.current_graph_info['conclusion']['is_vulnerable']} --- PROBABILITY: {self.current_graph_info['conclusion']['probability']}")
                additional_remarks = f"{content}\n---\n### 漏洞报告二次审计结论：\n{self.current_graph_info['double_check']}.\n---\nIS_VULNERABLE: {self.current_graph_info['conclusion']['is_vulnerable']}")
            return cr
        
        fdmsg = HumanMessage(content=[
            {"type": "text", "text": f"结论被驳回！需进一步调用工具以补充相关信息：\n{cr}"}
        ])
        state["messages"].append(fdmsg)
        return "llm"

    def audit_potential_attack_paths(self):
        with open(self.output_path, "r") as f:
            pa_paths = json.loads(f.read())

        # TODO recover
        # test_pa_paths = {}
        # for key, info in pa_paths.items():
        #     if(key == "tools.report_theoretical_memory.<module>---torch.load"):
        #     # if(info["entry_name"] == "tasks.main.<module>" and info["sink_name"] == "torch.load"):
        #         test_pa_paths[key] = info
        # pa_paths = test_pa_paths

        # 按照 cg_size 升序排列
        sorted_items = sorted(
            pa_paths.items(),
            key=lambda item: len(item[1]["call_graph"])
        )

        # for key, info in sorted_items:
        #     cg_size = len(info["call_graph"])
        #     png_path = f"{self.png_dir}/{cg_size}__{key}_ORIGINAL.png".replace(".<module>", "._module_")
        #     self.path_visualizer.create_entry_sink_callgraph(
        #         png_path, 
        #         info, 
        #         self.function_analysis_records)

        for key, info in sorted_items:
            if("conclusion" in info):
                # logger.info(f"{key}已有结论:\n{json.dumps(info['audit_result'], indent=2, ensure_ascii=False)}")
                logger.debugs(f"{key} already has conclusion:\n{json.dumps(info['audit_result'], indent=2, ensure_ascii=False)}")
                continue

            self.function_analysis_records = info["function_analysis_records"]
            cg_size = len(info["call_graph"])
            png_path = f"{self.png_dir}/{cg_size}__{key}.png".replace(".<module>", "._module_")

            if(png_path != "outputs/2.attack_path_images/16__tasks.vision.main._module_---torch.load.png"):
                continue

            self.path_visualizer.create_entry_sink_callgraph(
                png_path, 
                info, 
                self.function_analysis_records)
            
            # 创建硬链接，让 current.png 指向当前 PNG 文件
            current_link = f"{self.png_dir}/_current.png"
            try:
                if os.path.exists(current_link):
                    os.remove(current_link)
                # os.link(png_path, current_link)
                os.symlink(png_path, current_link)
                # logger.info(f"创建硬链接: {current_link} -> {png_path}")
                logger.debug(f"Created symlink: {current_link} -> {png_path}")
            except Exception as e:
                # logger.error(f"创建硬链接失败: {e}")
                logger.error(f"Failed to create hard link: {e}")

            self.current_entry = info["entry_name"]
            self.current_sink = info["sink_name"]
            self.current_graph_info = info
            self.current_png_path = png_path

            result = self.analyze_current_graph()
            info["audit_result"] = result
        
            # 将更新后的paths内容写入output_path代表的JSON文件
            with open(self.output_path, 'w', encoding='utf-8') as f:
                json.dump(pa_paths, f, ensure_ascii=False, indent=2)
    
    def analyze_current_graph(
        self, 
        recursion_limit: int = 100
    ) -> Dict[str, Any]:
        """
        分析调用图
        
        Args:
            project_source_path: 项目源码路径
            recursion_limit: 递归限制
            output_file: 输出结果文件路径
            
        Returns:
            分析结果
        """
        self.in_mess = False
        with open(f"prompts/analyze_paths.system_prompt.{self.language}.md", "r") as f:
            system_prompt = f.read()
        sys_input = SystemMessage(content=system_prompt)
        
        result = self.agent.invoke(
            {"messages": [sys_input]}, 
            {"recursion_limit": recursion_limit}
        )
        
        return result["messages"][-1].content
    
    def add_function_summary_to_png(self, function_name, to_add):
        self.function_analysis_records.setdefault(function_name, {})["summary"] = to_add
        self.path_visualizer.create_entry_sink_callgraph(
            self.current_png_path, 
            self.current_graph_info,
            self.function_analysis_records)

    def add_function_summary_dict_to_png(self, function_name, to_add_dict):
        for kw, desc in to_add_dict.items():
            self.function_analysis_records.setdefault(function_name, {})[kw] = desc
        self.path_visualizer.create_entry_sink_callgraph(
            self.current_png_path, 
            self.current_graph_info,
            self.function_analysis_records)

    def __enter__(self):
        """上下文管理器入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        if hasattr(self, 'driver'):
            self.neo4j_driver.close()
