from project_analyzer import ProjectAnalyzer
import json, os
import logging
from vul_analysis_agent.visualize_attack_paths import AttackPathVisualizer
from vul_analysis_agent.vul_analysis_agent import AegisAgent
from logging_config import setup_logging
from node_analyze_workflow import NodeAnalyzeWorkflow 
from langchain_openai import ChatOpenAI
from xuanji_llm_service import LLM_SERVICE_INFO, XuanjiChatModel
from neo4j import GraphDatabase

# 设置日志
logger = logging.getLogger(__name__)

# 统一配置参数
CONFIG = {
    # Neo4j 配置
    "neo4j_uri": "bolt://xxx.xxx.xxx.xxx:xxxx",
    "neo4j_username": "neo4j",
    "neo4j_password": "password",
    
    # AegisAgent 模型配置
    "inst_model_name": "Qwen3-VL-32B-Instruct-FP8",
    # "think_model_name": "Qwen3-VL-32B-Thinking-FP8",
    # "inst_model_name": "qwen-vl-plus",
    # "think_model_name": "qwen-vl-max",
    # "inst_model_name": "qwen-vl-max",
    "think_model_name": "qwen-vl-max",
    "png_dir": "outputs/2.attack_path_images",
    "temperature": 0,
    "max_tokens": 4096,
    "language": "CN"
    # "language": "EN"
}

def collect_callees(caller, graph):
    ret = []
    for call_edge in graph:
        if(call_edge["caller"] == caller):
            ret.append(call_edge["callee"])
    return ret


def main():
    # 初始化日志系统
    setup_logging(level=logging.INFO)
    
    output_path = "./outputs"
    # language = "EN"
    os.makedirs(output_path, exist_ok=True)
    retrieve_path = os.path.join(output_path, "1.retrieve_result.json")

    if os.path.exists(retrieve_path) is False:
        # 使用上下文管理器，自动管理Neo4j连接
        with ProjectAnalyzer(
            project_path='/workspace/target_projects_with_vuls/Megatron-LM',
            neo4j_uri=CONFIG["neo4j_uri"],
            neo4j_username=CONFIG["neo4j_username"],
            neo4j_password=CONFIG["neo4j_password"],
            language=CONFIG["language"]
        ) as analyzer:
            records = analyzer.find_potential_attack_paths()

            if CONFIG["language"] == "EN":
                from vul_analysis_agent.sink_records import SINK_INFO_EN as sink_function_info
            else:
                from vul_analysis_agent.sink_records import SINK_INFO_CN as sink_function_info

            for vul_key, vul_info in records.items():
                sink = vul_info['sink_name']
                vul_info["function_analysis_records"] = {}
                vul_info["function_analysis_records"][sink] = sink_function_info[sink]

            text = json.dumps(records, indent=2, ensure_ascii=False)
            with open(retrieve_path, 'w', encoding='utf-8') as f:
                f.write(text)
    else:
        with open(retrieve_path, "r") as f:
            records = json.loads(f.read())
    
    inst_model = get_chat_model_instantce(CONFIG["inst_model_name"], CONFIG["temperature"], CONFIG["max_tokens"])
    think_model = get_chat_model_instantce(CONFIG["think_model_name"], CONFIG["temperature"], CONFIG["max_tokens"])
    neo4j_driver = GraphDatabase.driver(CONFIG["neo4j_uri"], auth=(CONFIG["neo4j_username"], CONFIG["neo4j_password"]))

    path_visualizer = AttackPathVisualizer()
    naw = NodeAnalyzeWorkflow(neo4j_driver, CONFIG["language"], inst_model, think_model)

    for vul_key, vul_info in records.items():
        sink_name = vul_info["sink_name"]
        # entry_name = vul_info["entry_name"]
        call_graph = vul_info["call_graph"]
        cg_size = len(call_graph)
        png_path = f"{CONFIG['png_dir']}/{cg_size}__{vul_key}.png".replace(".<module>", "._module_")
        if(png_path != "outputs/2.attack_path_images/7__tasks.main._module_---eval.png"): # TODO delete debug
            continue

        if(cg_size < 7):
            continue

        path_visualizer.create_entry_sink_callgraph(png_path, vul_info, vul_info["function_analysis_records"])
        # for call_edge in call_graph:
        #     caller = call_edge["caller"]
        #     if(caller in vul_info["function_analysis_records"]):
        #         continue
        #     callees = collect_callees(caller, call_graph)
        #     sum_dict = naw.extract_key_codes(caller, png_path, callees, sink = sink_name)
        #     for kw, desc in sum_dict.items():
        #         vul_info["function_analysis_records"].setdefault(caller, {})[kw] = desc
        #         with open(retrieve_path, 'w', encoding='utf-8') as f: 
        #             f.write(json.dumps(records, ensure_ascii=False, indent=2))
        #     path_visualizer.create_entry_sink_callgraph(png_path, vul_info, vul_info["function_analysis_records"])
        #     # import time
        #     # time.sleep(3)

        agent = AegisAgent(
            retrieve_path,
            inst_model,
            think_model,
            neo4j_driver,
            CONFIG["language"],
            png_path,
            vul_info["function_analysis_records"],
            vul_info
        )
        agent.analyze_current_graph()

from langchain_core.callbacks.base import BaseCallbackHandler
class LoggerCallbackHandler(BaseCallbackHandler):
    """自定义回调处理器，使用 logger 记录流式输出"""
    
    def __init__(self, logger):
        self.logger = logger
        self.current_text = ""
    
    def on_llm_start(self, serialized, prompts, **kwargs):
        """LLM 开始时调用"""
        self.logger.info("LLM started generating response...")
        self.current_text = ""
    
    def on_llm_new_token(self, token: str, **kwargs):
        """每次生成新 token 时调用"""
        self.current_text += token
        # 实时打印到控制台
        print(token, end="", flush=True)
        # 也可以记录到日志（可选，避免日志过多）
        # self.logger.debug(f"New token: {token}")
    
    def on_llm_end(self, response, **kwargs):
        """LLM 结束时调用"""
        print()  # 换行
        self.logger.info(f"LLM generation completed, total length: {len(self.current_text)}")
        self.logger.debug(f"Full response: {self.current_text}")
    
    def on_llm_error(self, error, **kwargs):
        """发生错误时调用"""
        self.logger.error(f"LLM generation error: {error}")


def get_chat_model_instantce(model_name, temperature, max_tokens):
    if(model_name in ["Qwen3-VL-32B-Instruct-FP8", "Qwen3-VL-32B-Thinking-FP8"]):
        # 初始化模型
        return ChatOpenAI(
            model=model_name,
            openai_api_key="EMPTY",
            base_url="http://xxx.xxx.xxx.xxx:xxxx/v1",
            temperature=temperature,
            max_tokens=max_tokens,
            streaming=True,
            callbacks=[LoggerCallbackHandler(logger)]
        )

if __name__ == "__main__":
    main()
