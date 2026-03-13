"""
应该是从neo4j中读取图像，然后传递给VLM进行分析的入口处
"""

from project_analyzer import ProjectAnalyzer
import json, os
import logging
import random
from aegis_agent.visualize_attack_paths import AttackPathVisualizer
from aegis_agent.aegis_agent_test_n_hop import AegisAgent
from logging_config import setup_logging
from node_analyze_workflow import NodeAnalyzeWorkflow 
from langchain_openai import ChatOpenAI
from xuanji_llm_service import LLM_SERVICE_INFO, XuanjiChatModel
from neo4j import GraphDatabase

from evaluation_dpi_selection_simply_check import check_main, get_ground_truth, aggregate_task_results_by_method

from evaluation_context import set_context

from litellm_service import OpenAIDirectChatModel

# 设置日志
logger = logging.getLogger(__name__)

# language = "CN"

# 统一配置参数
CONFIG = {
    # Neo4j 配置
    "neo4j_uri": "bolt://172.16.167.35:7687",
    "neo4j_username": "neo4j",
    "neo4j_password": "password",
    
    # AegisAgent 模型配置
    # "inst_model_name": test_model_name,
    # "think_model_name": test_model_name,
    "png_dir": "outputs/5.dpi_selection",
    # "temperature": temperature,
    "max_tokens": 4096,
    # "language": language
}


def main(test_size=0, min_size=0, target_png: str="", target_project: str='Megatron-LM', method: str = '', test_model_name='qwen-vl-max', temperature: float = 0.5, language="CN"):
    # 初始化日志系统
    setup_logging(level=logging.INFO)
    import time
    start_time = int(time.time())
    
    output_path = "./outputs"

    # check method
    method_list = ['dense', 'changeCharactor', 'locate', 'withNode', 'onlyFuncName']
    if method and method not in method_list:
        print('Methor wrong')
        return


    os.makedirs(output_path, exist_ok=True)
    retrieve_path = os.path.join(output_path, "1.retrieve_result.json")

    if os.path.exists(retrieve_path) is False:
        # 使用上下文管理器，自动管理Neo4j连接
        with ProjectAnalyzer(
            project_path=f'/workspace/target_projects_with_vuls/{target_project}',
            neo4j_uri=CONFIG["neo4j_uri"],
            neo4j_username=CONFIG["neo4j_username"],
            neo4j_password=CONFIG["neo4j_password"],
            language=language
        ) as analyzer:
            records = analyzer.find_potential_attack_paths()

            if language == "EN":
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
    
    # 初始化一些要用的工具
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

        base_png_name = os.path.basename(png_path)[:-4]

        # TODO debug: select png
        if (not target_png and not test_size and cg_size<min_size) or (target_png and target_png not in png_path) or (test_size and f"{test_size}__" not in png_path):
            continue

        all_nodes = get_ground_truth(base_png_name).get('all_nodes', {})

        test_dpi_list = [50, 75, 100, 150, 200, 250, 300]
        for current_dpi in test_dpi_list:
            current_png_path = path_visualizer.create_entry_sink_callgraph(png_path, vul_info, vul_info["function_analysis_records"], dpi=current_dpi, set_dpi_in_name=True, method=method)

            for _ in range(1):
                # randomly select 4 nodes from all_nodes
                random_select_nodes = random.choices(all_nodes, k=4)

                task_context = {
                                "png_name": os.path.basename(current_png_path), # 图片名称
                                "start_time": start_time,               # 开始时间
                                # "prompt_template_path": f"prompts/test_dpi_v2{'-'+method if method in ['locate', 'withNode'] else ''}.system_prompt.{language}.md", # 告诉Agent去哪里读模板
                                "prompt_template_path": f"prompts/test_dpi_v3.system_prompt.{language}.md", # 告诉Agent去哪里读模板
                                'model_temperature': temperature,
                                'language': language,
                                'method': method,
                                'task_nodes': random_select_nodes,  # dpi测试时随机选择的节点的任务
                                'current_test': "dpi_selection",
                            }
                token = set_context(task_context)

                # 创建Agent，并使用agent分析图片
                agent = AegisAgent(
                    retrieve_path,
                    inst_model,
                    think_model,
                    neo4j_driver,
                    language,
                    current_png_path,
                    vul_info["function_analysis_records"],
                    vul_info
                )
                try:
                    analyze_result = agent.analyze_current_graph_for_dpi_selection()
                except Exception as e:
                    print(e)
                    pass

        # check_main(test_model_name, base_png_name)


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
    # main(target_png="8__examples.post_training.modelopt.export._module_---torch.load")
    # test_method = ['', 'changeCharactor', 'locate', 'withNode', 'onlyFuncName']
    import time
    start_time = time.time()
    print(f'Start evaluation_dpi_selection')
    test_count = 1
    test_method = ['dense', 'onlyFuncName']
    # test_method = ['onlyFuncName']
    model_list = ['qwen-vl-max', 'qwen-vl-plus']
    # model_list = ['Doubao-Seed-2.0-pro']
    for model in model_list:
        for _ in range(test_count):
            for current_method in test_method:
                main(test_size=11, method=current_method, test_model_name=model)
        aggregate_task_results_by_method(model)

    end_time = time.time()
    print(f'Total run time: {end_time - start_time}, round: {test_count}')
    print(f'Test method: {test_method}, model: {model_list}')

