import os
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
from agent_tools import get_all_tools, get_tools_by_name
from neo4j import GraphDatabase
from agent_tools import AGENT_INSTANCE
import base64
from qwen_chat_manager import chat_with_mllm_with_probs, advanced_json_loader

# ======================================================
# ✅ 状态定义
# ======================================================
class State(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]
    llm_calls: int

class PoCAgent:
    """
    PoCAgent - PoC生成、验证智能体
    封装了PoC生成、验证、CVSS评分等功能
    """
    
    def __init__(
        self,
        inst_model_name: str = "Qwen/Qwen3-VL-32B-Instruct-FP8",
        inst_api_base: str = "http://172.16.167.35:8000/v1",
        think_model_name: str ="/Qwen3-VL-32B-Thinking-FP8",
        think_api_base: str = "http://10.24.4.152:4545/v1",
        neo4j_uri: str = "bolt://172.16.167.35:7687",
        neo4j_auth: tuple = ("neo4j", "password"),
        temperature: float = 0,
        max_tokens: int = 4096,
        language: str = "CN"
    ):
        """
        初始化PoCAgent
        
        Args:
            inst_model_name: 对话模型名称
            inst_api_base: 对话API基础URL
            think_model_name: 推理模型名称
            think_api_base: 推理API基础URL
            neo4j_uri: Neo4j数据库URI
            neo4j_auth: Neo4j认证信息
            temperature: 模型温度参数
            max_tokens: 最大token数
            language: 语言设置，可选"CH"或"EN"，默认为"CH"
        """

        self.current_png_path = None
        self.failure_rec = []
        self.language = language

        self.neo4j_driver = GraphDatabase.driver(neo4j_uri, auth=neo4j_auth)
        
        # 初始化模型
        self.model_in_agent = ChatOpenAI(
            model=think_model_name,
            openai_api_key="EMPTY",
            base_url=think_api_base,
            temperature=temperature,
            max_tokens=max_tokens
        )

        self.instr_model_info = {
            "base_url": inst_api_base,
            "model_name": inst_model_name
        }

        self.think_model_info = {
            "base_url": think_api_base,
            "model_name": think_model_name
        }

        
        # 初始化工具
        self._init_tools()
        
        # 构建图
        self._build_graph()
    
        # 设置全局 AGENT_INSTANCE 引用
        import agent_tools
        agent_tools.AGENT_INSTANCE = self

    def _init_tools(self):
        """初始化所有工具"""
        self.tools = get_all_tools(self.language)
        self.tools_by_name = get_tools_by_name(self.language)
        self.model_with_tools = self.model_in_agent.bind_tools(self.tools)
    
    def _build_graph(self):
        """构建LangGraph图"""
        # 构建图
        graph = StateGraph(State)
        graph.add_node("llm", self._llm_node)
        graph.add_node("tool_exec", self._tool_exec_node)
        graph.add_edge(START, "llm")
        graph.add_conditional_edges("llm", self._should_continue, ["tool_exec", END])
        graph.add_edge("tool_exec", "llm")
        self.agent = graph.compile()
    
    def _llm_node(self, state: State):
        """LLM主调用节点"""
        with open(f"prompts/system_prompt.{self.language}.md", "r") as f:
            system_prompt = f.read()
        response = self.model_with_tools.invoke(
            [
                SystemMessage(content=system_prompt),
                *state["messages"]
            ]
        )
        return {
            "messages": [response],
            "llm_calls": state.get("llm_calls", 0) + 1,
        }

    
    def _tool_exec_node(self, state: State):
        """工具执行节点"""
        last_msg = state["messages"][-1]
        tcs = getattr(last_msg, "tool_calls", [])
        print(f"Reasoning output for this round:{last_msg.content}")
        print(f"Number of tool calls in this round:{len(tcs)}")

        results = []

        for call in tcs:
            tool_name = call["name"]
            tool_args = call["args"]
            print(f"- tool name：{tool_name}")
            print(f"- tool parameters：{tool_args}")

            tool_fn = self.tools_by_name[tool_name]
            result = tool_fn.invoke(tool_args)
            if(result.startswith("ERROR")):
                content = f"调用工具{tool_name}时出错。调用参数是{str(tool_args)}，报错内容是{result}。"
                results.append(ToolMessage(content=str(content), tool_call_id=call["id"]))
            else:
                results.append(ToolMessage(content=str(result), tool_call_id=call["id"]))

        return {"messages": results}

    def _should_continue(self, state: State) -> Literal["tool_exec", END]:
        """边控制逻辑"""
        last = state["messages"][-1]
        if getattr(last, "tool_calls", None):
            return "tool_exec"
        print(f"The agent believes the task can be terminated：{last.content}")
        return END
    
    def poc_gen(self):
        with open(f"prompts/user_prompt.{self.language}.md", "r") as f:
            user_prompt = f.read()
        with open(self.current_png_path, "rb") as image_file:
            base64_image = base64.b64encode(image_file.read()).decode('utf-8')

        user_input = HumanMessage(content=[
            {"type": "text", "text": user_prompt},
            {
                "type": "image",
                "base64": base64_image,
                "mime_type": "image/png",
            }
        ])

        result = self.agent.invoke({"messages": [user_input]}, {"recursion_limit": 100})

        return result["messages"][-1].content


    def __enter__(self):
        """上下文管理器入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        if hasattr(self, 'driver'):
            self.neo4j_driver.close()