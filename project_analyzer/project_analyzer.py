"""项目分析器主类"""
import os
import json
import logging
import networkx as nx
from typing import Dict, Tuple, List, Set, Optional

from .analyzers.project_structure import ProjectStructureAnalyzer
from .analyzers.ast_walker import ASTWalker
from .analyzers.type_inference import TypeInferenceEngine
from .analyzers.import_resolver import ImportResolver
from .analyzers.llm_analyzer import LlmAnalyzer
from .analyzers.dependency_analyzer import DependencyAnalyzer
from .analyzers.call_graph_analyzer import CallGraphAnalyzer
from .extractors.function_body import FunctionBodyExtractor
from .managers.neo4j_wrapper import Neo4jManager
from .utils.constants import BUILTIN_FUNCTIONS

# 设置日志
logger = logging.getLogger(__name__)


class ProjectAnalyzer:
    """项目分析器主类"""
    def __init__(self, project_path, neo4j_uri=None, neo4j_username="neo4j", neo4j_password="password", record_file="./project_analysis.json", language = "CN"):
        self.project_path = project_path
        self.project_name = os.path.basename(os.path.abspath(project_path))
        self.record_file = record_file
        
        # 初始化各个模块
        self.call_graph_analyzer = CallGraphAnalyzer(self)
        self.structure_analyzer = ProjectStructureAnalyzer(self)
        self.ast_walker = ASTWalker(self)
        self.type_inference = TypeInferenceEngine(self)
        self.import_resolver = ImportResolver(self)
        self.llm_analyzer = LlmAnalyzer(self)
        self.function_extractor = FunctionBodyExtractor(self)
        self.neo4j_wrapper = Neo4jManager(self, neo4j_uri, neo4j_username, neo4j_password)
        self.dependency_analyzer = DependencyAnalyzer(self)
        
        # 共享状态
        self.packages = {}
        self.modules = {}
        self.call_graph = nx.DiGraph()
        self.package_exports = {}
        self.export_aliases = {}
        self.wildcard_imports = {}
        
        # 当前分析状态
        self.current_module_path = "N/A"
        self.current_module_name = "N/A"

        self.language = language

    def __enter__(self):
        """上下文管理器入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口，自动关闭Neo4j连接"""
        self.neo4j_wrapper.close()

    def upload_call_graph(self, force_reupload=False):
        """生成项目调用图并上传到Neo4j
        
        基于现有的类型信息构建函数调用关系图，并上传到Neo4j数据库
        """
        # logger.info("开始生成调用图")
        logger.info("Starting call graph generation")
        
        # 统计调用图信息
        total_nodes = self.call_graph.number_of_nodes()
        total_edges = self.call_graph.number_of_edges()
        
        # logger.info(f"调用图生成完成: 节点数量={total_nodes}, 边数量={total_edges}")
        logger.info(f"Call graph generation completed: nodes={total_nodes}, edges={total_edges}")
        
        # 统计调用类型
        call_types = {}
        for _, _, data in self.call_graph.edges(data=True):
            call_type = data.get('call_type', 'unknown_call')
            call_types[call_type] = call_types.get(call_type, 0) + 1
        
        # logger.debug(f"调用类型统计: {call_types}")
        logger.debug(f"Call type statistics: {call_types}")
        
        # 上传到Neo4j数据库
        # logger.info("开始上传调用图到Neo4j")
        logger.info("Starting call graph upload to Neo4j")
        
        # 检查Neo4j连接
        if not self.neo4j_wrapper.driver:
            # logger.warning("Neo4j连接未初始化，跳过上传")
            logger.warning("Neo4j connection not initialized, skipping upload")
            return self.call_graph
        
        try:
            # 使用 upload_project_data_with_check 方法上传数据
            # 该方法会自动检查项目是否已上传，并处理数据收集和上传
            success = self.neo4j_wrapper.upload_project_data_with_check(force_reupload=force_reupload)
            
            if success:
                # logger.info("调用图数据成功上传到Neo4j数据库")
                logger.info("Call graph data successfully uploaded to Neo4j database")
                
                # 获取Neo4j统计信息
                neo4j_stats = self.neo4j_wrapper.get_statistics()
                if neo4j_stats:
                    # logger.debug(f"Neo4j数据库统计: 节点类型={neo4j_stats.get('nodes', {})}, 关系类型={neo4j_stats.get('relationships', {})}, 调用类型={neo4j_stats.get('call_types', {})}")
                    logger.debug(f"Neo4j database statistics: node types={neo4j_stats.get('nodes', {})}, relationship types={neo4j_stats.get('relationships', {})}, call types={neo4j_stats.get('call_types', {})}")
            else:
                # logger.error("调用图数据上传到Neo4j失败")
                logger.error("Call graph data upload to Neo4j failed")
                
        except Exception as e:
            # logger.error(f"上传调用图到Neo4j时发生错误: {e}", exc_info=True)
            logger.error(f"Error occurred while uploading call graph to Neo4j: {e}", exc_info=True)
        
        return self.call_graph

    def call_graph_analyze(self):
        """执行完整分析
        
        Args:
            use_dependency_order: 是否使用依赖顺序进行分析
        """
        # 1. 分析项目结构
        self.structure_analyzer.analyze_project_structure()
        
        # 使用依赖顺序进行分析
        # logger.info("使用依赖顺序进行分析")
        logger.info("Using dependency order for analysis")
        # 构建依赖图
        self.dependency_analyzer.build_dependency_graph()
        # 获取分析顺序
        analysis_order = self.dependency_analyzer.get_analysis_order()
        # 按依赖顺序分析模块
        for module_name in analysis_order:
            if module_name in self.modules:
                module_path = self.modules[module_name]["path"]
                # logger.debug(f"分析模块: {module_name}")
                logger.debug(f"Analyzing module: {module_name}")
                self.structure_analyzer.analyze_module(module_name, module_path, quickmode=True)

            # 对package进行特殊的处理，处理过程采取和module一致的形式进行信息存储
            elif module_name in self.packages:
                pkg_init_path = self.packages[module_name]["init_file"]
                # logger.debug(f"分析包: {module_name}")
                logger.debug(f"Analyzing package: {module_name}")
                self.structure_analyzer.analyze_package(module_name, pkg_init_path, quickmode=True)

        # 按依赖顺序分析模块
        for module_name in analysis_order:
            if module_name in self.modules:
                module_path = self.modules[module_name]["path"]
                # logger.debug(f"分析模块: {module_name}")
                logger.debug(f"Analyzing module: {module_name}")
                self.structure_analyzer.analyze_module(module_name, module_path, quickmode=False)

            # 对package进行特殊的处理，处理过程采取和module一致的形式进行信息存储
            elif module_name in self.packages:
                pkg_init_path = self.packages[module_name]["init_file"]
                # logger.debug(f"分析包: {module_name}")
                logger.debug(f"Analyzing package: {module_name}")
                self.structure_analyzer.analyze_package(module_name, pkg_init_path, quickmode=False)
    
    def get_statistics(self):
        """获取统计信息"""
        # 统计不同类型的调用
        call_types = {}
        for _, _, data in self.call_graph.edges(data=True):
            call_type = data.get('call_type', 'unknown_call')
            call_types[call_type] = call_types.get(call_type, 0) + 1
        
        # 统计函数和类数量
        total_functions = 0
        total_classes = 0
        for module_name, module_info in self.modules.items():
            total_functions += len(module_info["functions"])
            total_classes += len(module_info["classes"])
        
        return {
            'packages': len(self.packages),
            'modules': len(self.modules),
            'functions': total_functions,
            'classes': total_classes,
            'call_relationships': self.call_graph.number_of_edges(),
            'call_types': call_types
        }
    
    def check_project_uploaded(self) -> Tuple[bool, Dict]:
        """检查项目是否已经上传过"""
        return self.neo4j_wrapper.check_project_uploaded()
    
    def upload_project_data_with_check(self, force_reupload: bool = False):
        """带检查的上传项目数据"""
        return self.neo4j_wrapper.upload_project_data_with_check(force_reupload)
    
    def get_current_classes(self):
        return self.modules[self.current_module_name]["classes"]

    def get_current_functions(self):
        return self.modules[self.current_module_name]["functions"]

    def get_current_import_aliases(self):
        return self.modules[self.current_module_name]["import_aliases"]

    def get_current_variable_types(self):
        return self.modules[self.current_module_name]["variable_types"]

    def ensure_module_analyzed(self, full_module_name):
        if(self.modules[full_module_name]["analyzed"] == False):
            ocm = self.current_module_name
            ocp = self.current_module_path
            # logger.debug(f"在分析{ocm}的过程中，发现{full_module_name}未被分析，优先完成后者的分析")
            logger.debug(f"During analysis of {ocm}, found {full_module_name} not analyzed, prioritizing its analysis")
            self.structure_analyzer.analyze_module(full_module_name, self.modules[full_module_name]["path"])
            self.current_module_name = ocm
            self.current_module_path = ocp

    def get_varaible_types_in_module(self, full_module_name):
        if(full_module_name not in self.modules):
            return None
        self.ensure_module_analyzed(full_module_name)
        return self.modules[full_module_name]["variable_types"]

    def get_functions_in_module(self, full_module_name):
        if(full_module_name not in self.modules):
            return None
        self.ensure_module_analyzed(full_module_name)
        return self.modules[full_module_name]["functions"]
    
    def get_classes_in_module(self, full_module_name):
        if(full_module_name not in self.modules):
            return None
        self.ensure_module_analyzed(full_module_name)
        return self.modules[full_module_name]["classes"]

    def get_module(self, module_name):
        self.ensure_module_analyzed(module_name)
        return self.modules[module_name]

    def find_func_info(self, full_func_name):
        spls = full_func_name.split(".")
        spls_len = len(spls)
        for i in range(1, spls_len):
            module_parts = spls[0: spls_len - i]
            full_module_name = ".".join(module_parts)
            func_list = self.get_functions_in_module(full_module_name)
            if func_list:
                return func_list.get(full_func_name, None)
        return None
    
    def find_class_info(self, full_class_name):
        spls = full_class_name.split(".")
        spls_len = len(spls)
        for i in range(1, spls_len):
            module_parts = spls[0: spls_len - i]
            full_module_name = ".".join(module_parts)
            class_list = self.get_classes_in_module(full_module_name)
            if class_list:
                return class_list.get(full_class_name, None)
        return None
    
    def find_container_module(self, full_target_name):
        spls = full_target_name.split(".")
        spls_len = len(spls)
        for i in range(1, spls_len):
            module_parts = spls[0: spls_len - i]
            full_module_name = ".".join(module_parts)
            if full_module_name in self.modules:
                return full_module_name
        return None

    def find_potential_attack_paths(self):
        return self.neo4j_wrapper.potential_attack_paths()
