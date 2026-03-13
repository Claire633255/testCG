"""测试AST Walker的各种情况"""
import ast
import sys
import os
import json
import logging

# 添加项目路径
sys.path.insert(0, '/workspace')

from project_analyzer.project_analyzer import ProjectAnalyzer
from logging_config import setup_logging

# 设置日志
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    # 初始化日志系统
    setup_logging()
    
    test_folder = '/workspace/target_projects_with_vuls/Megatron-LM'
    # test_folder = '/workspace/tests/multifile_tests'
    analyzer = ProjectAnalyzer(test_folder,         
        neo4j_uri="bolt://172.16.167.35:7687",  # 替换为实际IP
        neo4j_username="neo4j",
        neo4j_password="password")

    analyzer.call_graph_analyze()
    analyzer.upload_call_graph(force_reupload = True)
    
    # logger.info("项目构建和分析完成")
    logger.info("Project construction and analysis completed")
