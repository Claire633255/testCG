"""
应该是从neo4j中读取图像，然后传递给VLM进行分析的入口处
"""

from project_analyzer import ProjectAnalyzer
import json, os
import logging
from aegis_agent.visualize_attack_paths import AttackPathVisualizer
from aegis_agent.aegis_agent_test_n_hop import AegisAgent
from logging_config import setup_logging
from node_analyze_workflow import NodeAnalyzeWorkflow 
from langchain_openai import ChatOpenAI
from xuanji_llm_service import LLM_SERVICE_INFO, XuanjiChatModel
from neo4j import GraphDatabase

from evaluation_n_hop_simply_check import aggregate_n_hop_results, compare_models
from evaluation_context import set_context

from litellm_service import OpenAIDirectChatModel

# 设置日志
logger = logging.getLogger(__name__)

test_model_name = "qwen-vl-max"
temperature = 0.5

# 统一配置参数
CONFIG = {
    # Neo4j 配置
    "neo4j_uri": "bolt://172.16.167.35:7687",
    "neo4j_username": "neo4j",
    "neo4j_password": "password",
    
    # AegisAgent 模型配置
    "inst_model_name": test_model_name,
    "think_model_name": test_model_name,
    "png_dir": "outputs/4.n_hop_evaluation",
    "temperature": temperature,
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


def main(use_text_mode=False, test_size=0, min_size=0, target_png: str="", test_model_name: str = 'qwen-vl-max', target_project: str='Megatron-LM', temperature=0.5, language="CN", dpi=100):
    if not test_model_name:
        logger.warning("No select model")
        return None

    # 设置全局环境变量
    os.environ['USE_TXT_MODE'] = str(use_text_mode)
    print(f"[DEBUG] Set USE_TXT_MODE to {use_text_mode}")

    # 初始化日志系统
    setup_logging(level=logging.INFO)
    import time
    start_time = int(time.time())
    
    output_path = "./outputs"
    # language = "EN"
    os.makedirs(output_path, exist_ok=True)
    retrieve_path = os.path.join(output_path, "1.retrieve_result.json")

    if os.path.exists(retrieve_path) is False:
        # 使用上下文管理器，自动管理Neo4j连接
        with ProjectAnalyzer(
            project_path=f'/workspace/target_projects_with_vuls/{target_project}',
            neo4j_uri=CONFIG["neo4j_uri"],
            neo4j_username=CONFIG["neo4j_username"],
            neo4j_password=CONFIG["neo4j_password"],
            language=CONFIG["language"]
        ) as analyzer:
            records = analyzer.find_potential_attack_paths()

            if CONFIG["language"] == "EN":
                from aegis_agent.sink_records import SINK_INFO_EN as sink_function_info
            else:
                from aegis_agent.sink_records import SINK_INFO_CN as sink_function_info

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
    
    inst_model = get_chat_model_instantce(test_model_name, temperature, CONFIG["max_tokens"])
    think_model = get_chat_model_instantce(test_model_name, temperature, CONFIG["max_tokens"])
    print("[DEBUG] connect neo4j server")
    neo4j_driver = GraphDatabase.driver(CONFIG["neo4j_uri"], auth=(CONFIG["neo4j_username"], CONFIG["neo4j_password"]))

    # 路径可视化——应该就是转换成图片
    path_visualizer = AttackPathVisualizer()
    # 调用这个NodeAnalyzeWorkflow对图上的节点进行推断
    naw = NodeAnalyzeWorkflow(neo4j_driver, language, inst_model, think_model)

    for vul_key, vul_info in records.items():
        sink_name = vul_info["sink_name"]
        # entry_name = vul_info["entry_name"]
        call_graph = vul_info["call_graph"]
        cg_size = len(call_graph)
        png_path = f"{CONFIG['png_dir']}/{cg_size}__{vul_key}.png".replace(".<module>", "._module_")

        # TODO debug: select png
        if (not target_png and not test_size and cg_size<min_size) or (target_png and target_png not in png_path) or (test_size and f"{test_size}__" not in png_path):
            continue

        path_visualizer.create_entry_sink_callgraph(png_path, vul_info, vul_info["function_analysis_records"], dpi=dpi, method='onlyFuncName')

        path_extracted_file = f'evaluations/extracted_paths/{os.path.basename(png_path).replace(".png", ".json")}'
        
        if not os.path.exists(path_extracted_file):
            print(f"[ERROR] No such file or directory: '{path_extracted_file}'")
        
        with open(path_extracted_file, "r") as f:
            extracted_result = json.loads(f.read())['all_paths']

        seen_tasks = set()  # 用于去重，避免同一对(start, end, n)重复跑
        for start_node, item in extracted_result.items():
            for end_node, paths in item.items():
                for each_path in paths:
                    hop_count = len(each_path) - 1

                    task_signature = (start_node, end_node, hop_count)
            
                    if task_signature not in seen_tasks:
                        seen_tasks.add(task_signature)

                        # 包含当前任务所有需要的动态参数
                        task_context = {
                            "png_name": os.path.basename(png_path), # 图片名称
                            "start_node": start_node,               # 起始节点
                            "end_node": end_node,                   # 终止节点
                            "n_hops": hop_count,                    # 跳数
                            "start_time": start_time,               # 开始时间
                            "prompt_template_path": f"prompts/test_n_hop{'_text' if use_text_mode else ''}_v4.system_prompt.{language}.md", # 告诉Agent去哪里读模板
                            'current_test': "n_hop",
                        }
                        token = set_context(task_context)

                        # 创建Agent，并使用agent分析图片
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
                        try:
                            analyze_result = agent.analyze_n_hop_on_current_graph(use_text=use_text_mode)
                        except Exception as e:
                            print(e)
    
    # 设置全局环境变量
    os.environ['USE_TXT_MODE'] = "False"


            


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
    if(model_name in ["qwen3-vl:32b-instruct", "Qwen3-VL-32B-Thinking-FP8"]):
        # 初始化模型
        return ChatOpenAI(
            model=model_name,
            api_key="8122602127:BxwqQHAZVrLEVsSO:chatgpt-api.vmic.xyz",
            base_url="http://10.24.4.150:8000/xuanji", 
            temperature=temperature,
            max_tokens=max_tokens,
            streaming=True,
            callbacks=[LoggerCallbackHandler(logger)]
        )
    else:
        print(f"[DEBUG] Use XuanjiChatModel --- model: {model_name}")

        if model_name in ["gemini-2.5-pro", "gemini-3-pro"]:
            domain = "ai-chatgpt-hub-prd.vmic.xyz"
        elif "environment" in LLM_SERVICE_INFO[model_name] and LLM_SERVICE_INFO[model_name]["environment"] == "online":
            domain = "chatgpt-api.vmic.xyz"
        else:
            domain = "chatgpt-api-pre.vmic.xyz"

        return XuanjiChatModel(
            model_name=model_name,
            app_id=LLM_SERVICE_INFO[model_name]["APP_ID"], # owned by 刘海辉
            app_key=LLM_SERVICE_INFO[model_name]["APP_KEY"],
            domain=domain,
            uri=LLM_SERVICE_INFO[model_name]["URI"],
            temperature=temperature,
            max_tokens=max_tokens
        )


if __name__ == "__main__":
    model_list = ['qwen-vl-max', 'qwen-vl-plus']
    fromat_list = [True, False]
    # model_list = ['qwen-vl-max']
    for model in model_list:
        for mode in fromat_list:
            for _ in range(1):
                main(use_text_mode=mode, min_size=7, test_model_name=model)
            aggregate_n_hop_results(model, use_text=mode, save_result=True, run_check=True, fuzzy_match_flag=True)
        compare_models(model, fuzzy_match_flag=True)
