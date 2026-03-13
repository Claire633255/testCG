import graphviz
from collections import defaultdict, deque
import os
import json

def extract_all_paths_from_dot(dot_file_path: str, max_paths_per_pair: int = 50):
    """
    从DOT文件中提取每个节点到达其他任意节点的所有路径
    
    参数:
        dot_file_path: DOT文件路径
        max_paths_per_pair: 每对节点间最大返回路径数
        
    返回:
        tuple: (reachable_dict, all_paths_dict)
            - reachable_dict: 每个节点能到达的所有节点列表
            - all_paths_dict: 每个节点到其他节点的所有路径字典
    """
    try:
        with open(dot_file_path, 'r', encoding='utf-8') as f:
            dot_content = f.read()
        
        print(f"开始分析DOT文件: {dot_file_path}")
        
        # 使用正则表达式解析DOT内容
        import re
        
        # 预处理：移除注释
        lines = dot_content.split('\n')
        cleaned_lines = []
        for line in lines:
            if '//' in line:
                line = line.split('//')[0]
            cleaned_lines.append(line.strip())
        
        # 合并多行
        dot_text = ' '.join(cleaned_lines)
        # 颜色转换映射：hex -> color name
        hex_to_color = {
            '#FFFF00': 'Yellow',
            '#EF5350': 'Red',
            '#66BB6A': 'Green',
            '#EEEEEE': 'Gray',
            '#0000FF': 'Blue',

            '#FFA500': 'Orange',
            '#800080': 'Purple',
            '#FFC0CB': 'Pink',
            '#A52A2A': 'Brown',
            '#00FFFF': 'Cyan',
            '#FF00FF': 'Magenta',
            '#000000': 'Black',
            '#FFFFFF': 'White',
        }

        # 提取所有带引号的节点标识符
        # 节点定义通常有 [label= 或 [shape= 等属性
        node_pattern = r'"([^"\\]*(?:\\.[^"\\]*)*)"\s*\[[^\]]*\]'
        node_matches = re.findall(node_pattern, dot_text)

        # 提取节点背景颜色
        node_color_pattern = r'"([^"\\]*(?:\\.[^"\\]*)*)"\s*\[[^\]]*BGCOLOR="([^"]+)"[^\]]*\]'
        node_color_matches = re.findall(node_color_pattern, dot_text)

        # 构建节点颜色字典 {node: [color1, color2, ...]}
        node_colors = {}
        for node_name, bg_color in node_color_matches:
            # 跳过 white 背景
            if bg_color.lower() == 'white':
                continue
            # 转换为颜色名称
            color_name = hex_to_color.get(bg_color, bg_color)
            if node_name not in node_colors:
                node_colors[node_name] = []
            node_colors[node_name].append(color_name)
        
        # 边模式
        edge_pattern = r'"([^"\\]*(?:\\.[^"\\]*)*)"\s*->\s*"?([^"\s\[]+)"?\s*\[[^\]]*(?:label|shape|color)[^\]]*\]'
        edge_matches = re.findall(edge_pattern, dot_text)
        
        # 构建节点集合（从节点定义和边中收集）
        nodes = set(node_matches)
        for src, dst in edge_matches:
            nodes.add(src)
            nodes.add(dst)
        
        # 构建邻接表
        adjacency = defaultdict(list)
        for src, dst in edge_matches:
            adjacency[src].append(dst)
        
        print(f"  解析完成: {len(nodes)} 个节点, {len(edge_matches)} 条边")

        # 处理相邻边
        for index in range(len(edge_matches)):
            edge_matches[index] = '->'.join(edge_matches[index])

        
        # 计算每个节点的可达节点和所有路径
        reachable_dict = {}
        all_paths_dict = defaultdict(lambda: defaultdict(list))
        
        # 对每个节点进行路径搜索
        for i, start_node in enumerate(nodes):
            reachable_nodes = set()
            
            # 使用BFS查找所有路径
            # 队列元素: (当前节点, 当前路径)
            queue = deque([(start_node, [start_node])])
            
            while queue:
                current_node, current_path = queue.popleft()
                
                # 如果不是起始节点，记录可达性和路径
                if current_node != start_node:
                    reachable_nodes.add(current_node)
                    
                    # 记录这条路径（检查是否已存在）
                    if current_path not in all_paths_dict[start_node][current_node]:
                        all_paths_dict[start_node][current_node].append(current_path.copy())
                
                # 如果已经找到足够多的路径，可以提前停止
                if len(all_paths_dict[start_node].get(current_node, [])) >= max_paths_per_pair:
                    continue
                
                # 探索邻居
                for neighbor in adjacency.get(current_node, []):
                    # 避免循环：确保邻居不在当前路径中
                    if neighbor not in current_path:
                        new_path = current_path + [neighbor]
                        queue.append((neighbor, new_path))
            
            # 存储可达节点
            reachable_dict[start_node] = sorted(list(reachable_nodes))
            
            # 进度显示
            if (i + 1) % 10 == 0 or i == len(nodes) - 1:
                print(f"  已处理 {i + 1}/{len(nodes)} 个节点")
        
        print(f"分析完成: 共找到 {sum(len(paths) for paths_dict in all_paths_dict.values() for paths in paths_dict.values())} 条路径")

        # 将defaultdict转换为普通dict以便序列化
        serializable_all_paths = {}
        for start_node, target_dict in all_paths_dict.items():
            serializable_all_paths[start_node] = dict(target_dict)

        return reachable_dict, serializable_all_paths, edge_matches, node_colors
        
    except Exception as e:
        print(f"提取路径时出错: {e}")
        import traceback
        traceback.print_exc()
        return {}, {}

def save_paths_to_json(all_nodes: list, all_edges: list, reachable_dict: dict, all_paths_dict: dict, node_color_dict: dict, output_file: str):
    """
    将路径分析结果保存为JSON文件
    
    参数:
        reachable_dict: 可达节点字典
        all_paths_dict: 所有路径字典
        output_file: 输出JSON文件路径
    """
    try:
        # 确保目录存在
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        result = {
            'all_nodes': all_nodes,
            'all_edges': all_edges,
            'node_colors': node_color_dict,
            'reachable_nodes': reachable_dict,
            'all_paths': all_paths_dict
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        print(f"路径分析结果已保存到: {output_file}")
        return result
        
    except Exception as e:
        print(f"保存JSON文件时出错: {e}")

def query_paths(all_paths_dict: dict, source_node: str, target_node: str = None):
    """
    查询特定节点间的路径
    
    参数:
        all_paths_dict: 所有路径字典
        source_node: 源节点
        target_node: 目标节点（如果为None，则返回源节点到所有节点的路径）
        
    返回:
        list: 路径列表或路径字典
    """
    if source_node not in all_paths_dict:
        print(f"警告：源节点 '{source_node}' 不在图中")
        return []
    
    if target_node is None:
        # 返回源节点到所有可达节点的路径
        return all_paths_dict[source_node]
    else:
        # 返回特定节点对间的所有路径
        if target_node in all_paths_dict[source_node]:
            paths = all_paths_dict[source_node][target_node]
            print(f"从 '{source_node}' 到 '{target_node}' 找到 {len(paths)} 条路径:")
            for i, path in enumerate(paths, 1):
                print(f"  路径 {i}: {' -> '.join(path)}")
            return paths
        else:
            print(f"警告：未找到从 '{source_node}' 到 '{target_node}' 的路径")
            return []

# 以下是您原来的函数，保持不变...

def robust_extract_reachable_nodes(dot_content):
    """
    健壮的可达节点提取函数，处理各种DOT格式
    
    参数:
        dot_content: DOT文件内容字符串
        
    返回:
        dict: 可达节点字典
    """
    # 预处理：移除注释和多行字符串
    lines = dot_content.split('\n')
    cleaned_lines = []
    
    for line in lines:
        # 移除注释
        if '//' in line:
            line = line.split('//')[0]
        cleaned_lines.append(line.strip())
    
    # 合并多行
    dot_text = ' '.join(cleaned_lines)
    
    # 提取所有带引号的节点标识符
    import re
    
    # 找到所有带引号的标识符（包括节点定义和边引用）
    quoted_pattern = r'"([^"\\]*(?:\\.[^"\\]*)*)"'
    all_quoted = re.findall(quoted_pattern, dot_text)
    
    # 节点定义通常有 [label= 或 [shape= 等属性
    node_pattern = r'"([^"\\]*(?:\\.[^"\\]*)*)"\s*\[[^\]]*(?:label|shape|color)[^\]]*\]'
    node_matches = re.findall(node_pattern, dot_text)
    
    # 边模式
    edge_pattern = r'"([^"\\]*(?:\\.[^"\\]*)*)"\s*->\s*"?([^"\s\[]+)"?\s*\[[^\]]*(?:label|shape|color)[^\]]*\]'
    edge_matches = re.findall(edge_pattern, dot_text)
    
    # 构建节点集合（从节点定义和边中收集）
    nodes = set(node_matches)
    for src, dst in edge_matches:
        nodes.add(src)
        nodes.add(dst)
    
    # 构建邻接表
    adjacency = defaultdict(list)
    for src, dst in edge_matches:
        adjacency[src].append(dst)
    
    # 计算可达节点
    reachable = {}
    for start_node in nodes:
        # 使用DFS计算可达节点
        visited = set()
        stack = [start_node]
        
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            
            for neighbor in adjacency.get(current, []):
                if neighbor not in visited:
                    stack.append(neighbor)
        
        # 移除起始节点
        visited.discard(start_node)
        reachable[start_node] = sorted(list(visited))
    
    return reachable

def main(dot_file: str):
    """
    主函数：读取DOT文件并提取可达节点
    """
    # 从文件中读取DOT内容
    dot_file = dot_file
    
    try:
        with open(dot_file, 'r', encoding='utf-8') as f:
            dot_content = f.read()
        
        # 使用健壮的方法提取可达节点
        reachable_dict = robust_extract_reachable_nodes(dot_content)
        
        print("=" * 80)
        print("节点可达性分析结果")
        print("=" * 80)
        
        # 统计信息
        total_nodes = len(reachable_dict)
        nodes_with_reachable = sum(1 for targets in reachable_dict.values() if targets)
        
        all_nodes = list(reachable_dict.keys())

        print(f"\n总节点数: {total_nodes}")
        print(f"有可达节点的节点数: {nodes_with_reachable}")
        print(f"孤立节点数: {total_nodes - nodes_with_reachable}")
        
        # # 保存为ground_truth文件
        ground_truth_save_folder = "evaluations/image_vs_text/n_hop/ground_truth"
        save_file_name = os.path.basename(dot_file).replace(".dot", ".txt")
        save_file_path = os.path.join(ground_truth_save_folder, save_file_name)
        os.makedirs(ground_truth_save_folder, exist_ok=True)

        # with open(save_file_path, "w", encoding="utf-8") as f:
        #     # 显示每个节点的可达节点
        #     for node, targets in sorted(reachable_dict.items()):
        #         print(f"\n{'='*60}")
        #         print(f"节点: {node}")
        #         print(f"可达节点数: {len(targets)}")
                
        #         if targets:
        #             print("可达节点列表:")
        #             for i, target in enumerate(targets, 1):
        #                 print(f"  {i:2d}. {target}")
        #                 f.write(f"{node} -> {target}\n")
        #         else:
        #             print("没有可达其他节点")
        
        # # 同时提取所有路径并保存
        # print("\n" + "="*80)
        # print("开始提取所有路径")
        # print("="*80)
        
        reachable_dict_paths, all_paths_dict, all_edges, node_colors = extract_all_paths_from_dot(dot_file)
        
        # 保存所有路径到JSON文件
        ground_truth_save_folder = "evaluations/extracted_paths"
        paths_output_file = os.path.join(ground_truth_save_folder, save_file_name.replace(".txt", ".json"))
        result = save_paths_to_json(all_nodes, all_edges, reachable_dict_paths, all_paths_dict, node_colors, paths_output_file)
        return result
        
        
    except FileNotFoundError:
        print(f"错误：找不到文件 {dot_file}")
    except Exception as e:
        print(f"处理文件时出错: {e}")
    

def find_critical_paths(reachable_dict, start, end):
    """
    查找从起始节点到目标节点的关键路径
    
    参数:
        reachable_dict: 可达节点字典
        start: 起始节点
        end: 目标节点
        
    返回:
        list: 路径列表
    """
    # 简化的路径查找（实际应用中可能需要更复杂的图遍历算法）
    paths = []
    
    # 这里使用简单的BFS查找路径
    from collections import deque
    
    # 重建邻接表
    adjacency = {}
    for node, targets in reachable_dict.items():
        for target in targets:
            if node not in adjacency:
                adjacency[node] = []
            adjacency[node].append(target)
    
    # BFS查找所有路径
    queue = deque([(start, [start])])
    
    while queue and len(paths) < 10:  # 限制最大路径数
        current, path = queue.popleft()
        
        if current == end:
            paths.append(path)
            continue
            
        for neighbor in adjacency.get(current, []):
            if neighbor not in path:  # 避免循环
                queue.append((neighbor, path + [neighbor]))
    
    return paths

# 测试新函数
def test_path_extraction():
    """
    测试路径提取功能
    """
    dot_file = "vulnerability_path.dot"  # 替换为您的DOT文件路径
    
    if not os.path.exists(dot_file):
        print(f"测试文件不存在: {dot_file}")
        return
    
    print("测试路径提取功能")
    print("="*60)
    
    # 提取所有路径
    reachable_dict, all_paths_dict = extract_all_paths_from_dot(dot_file)
    
    if not reachable_dict:
        print("路径提取失败")
        return
    
    # 显示一些统计信息
    total_paths = 0
    for start_node, target_dict in all_paths_dict.items():
        for target_node, paths in target_dict.items():
            total_paths += len(paths)
    
    print(f"\n统计信息:")
    print(f"  总节点数: {len(reachable_dict)}")
    print(f"  总路径数: {total_paths}")
    
    # 查找具有最多路径的节点对
    max_paths = 0
    max_pair = None
    
    for start_node, target_dict in all_paths_dict.items():
        for target_node, paths in target_dict.items():
            if len(paths) > max_paths:
                max_paths = len(paths)
                max_pair = (start_node, target_node)
    
    if max_pair:
        print(f"  最多路径的节点对: {max_pair[0]} -> {max_pair[1]} ({max_paths} 条路径)")

if __name__ == "__main__":
    dot_folder = "outputs/5.dpi_selection"
    # target_files = [x for x in os.listdir(dot_folder) if x.endswith('.dot') and "11__" in x]
    target_files = ['7__tasks.main._module_---eval.dot']

    for file in target_files:
        print(file)
        dot_file = os.path.join(dot_folder, file)
        main(dot_file)

    # # 示例查询
    # reachable_dict_paths, all_paths_dict = extract_all_paths_from_dot(dot_file)

    # print("\n" + "="*80)
    # print("示例查询")
    # print("="*80)
    
    # # 查询特定节点对的路径
    # source_node = "examples.post_training.modelopt.export.<module>"
    # target_node = "megatron.post_training.checkpointing.load_modelopt_checkpoint"
    
    # paths = query_paths(all_paths_dict, source_node, target_node)
    
    # 也可以单独测试路径提取功能
    # test_path_extraction()