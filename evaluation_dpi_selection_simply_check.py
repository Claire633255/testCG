import os
import json
import matplotlib.pyplot as plt
import extract_taint_path_from_dot
from fuzzy_match import fuzzy_match

# 已知的优化方法名列表
VALID_METHODS = {'dense', 'changeCharactor', 'locate', 'withNode', 'onlyFuncName'}

# 最初版本 检查识别是否完全准确
def check_single_file(file_path: str, all_node_list: list, all_edge_list: list, save_folder: str=""):
    decode_error_lines = []
    results = {}

    with open(file_path) as f:
        lines = [line.strip() for line in f if line]
    
    for line in lines:
        try:
            each_analyse_result = json.loads(line)
            current_dpi = int(each_analyse_result['currentDpi'])

            # 读取结果
            figure_analyse_result = json.loads(each_analyse_result['response'].replace('```json', '').replace('```', ''))

        except json.decoder.JSONDecodeError as e:
            decode_error_lines.append(line)
            continue

        # 开始检查
        # 构建检查结果字典
        current_check_result_dict = {
            "node_result": {
                'Counts_byVLM': None,
                'Counts_actual': len(all_node_list),
                'Precision': None,
                'Recall': None,
                'F1Score': None,
                'missingNodes': None,
                'hallucination': None,
            },

            'edge_result': {
                'Counts_byVLM': None,
                'Counts_actual': len(all_edge_list),
                'Precision': None,
                'Recall': None,
                'F1Score': None,
                'missingEdges': None,
                'hallucination': None,
            }
        }

        if 'withNode' not in os.path.basename(file_path):
            # 检查node是否正确
            node_check_result_by_VLM = figure_analyse_result['all_nodes']
            current_check_result_dict["node_result"]['Counts_byVLM'] = figure_analyse_result['node_counts']

            node_true_positive = 0
            for node in node_check_result_by_VLM:
                if node in all_node_list:
                    node_true_positive += 1

            missing_nodes = set(all_node_list).difference(set(node_check_result_by_VLM))
            hallucinated_nodes = set(node_check_result_by_VLM).difference(set(all_node_list))

            node_false_positive = len(hallucinated_nodes)
            node_false_negative = len(missing_nodes)

            current_check_result_dict['node_result']['Precision'] = round(node_true_positive / (node_true_positive + node_false_positive), 4) if node_true_positive + node_false_positive > 0 else 0
            current_check_result_dict['node_result']['Recall'] = round(node_true_positive / (node_true_positive + node_false_negative), 4) if (node_true_positive + node_false_negative) > 0 else 0
            current_check_result_dict['node_result']['F1Score'] = round(2 * current_check_result_dict['node_result']['Precision'] * current_check_result_dict['node_result']['Recall'] / (current_check_result_dict['node_result']['Precision'] + current_check_result_dict['node_result']['Recall']), 4) if current_check_result_dict['node_result']['Precision'] + current_check_result_dict['node_result']['Recall'] > 0 else 0
            current_check_result_dict['node_result']['missingNodes'] = sorted(list(missing_nodes))
            current_check_result_dict['node_result']['hallucination'] = sorted(list(hallucinated_nodes))

        # 相同方式检查edges
        edge_check_result_by_VLM = figure_analyse_result['all_edges']
        current_check_result_dict["edge_result"]['Counts_byVLM'] = figure_analyse_result['edge_counts']
        # 统一边的表示方式
        for index in range(len(edge_check_result_by_VLM)):
            edge_check_result_by_VLM[index] = '->'.join([x.strip() for x in edge_check_result_by_VLM[index].split('->')])

        edge_true_positive = 0
        for edge in edge_check_result_by_VLM:
            if edge in all_edge_list:
                edge_true_positive += 1
                
        edge_false_positive = len(set(edge_check_result_by_VLM).difference(set(all_edge_list)))
        edge_false_negative = len(set(all_edge_list).difference(set(edge_check_result_by_VLM)))

        current_check_result_dict['edge_result']['Precision'] = round(edge_true_positive / (edge_true_positive + edge_false_positive), 4) if (edge_true_positive + edge_false_positive) > 0 else 0
        current_check_result_dict['edge_result']['Recall'] = round(edge_true_positive / (edge_true_positive + edge_false_negative), 4) if (edge_true_positive + edge_false_negative) > 0 else 0
        current_check_result_dict['edge_result']['F1Score'] = round(2 * current_check_result_dict['edge_result']['Precision'] * current_check_result_dict['edge_result']['Recall'] / (current_check_result_dict['edge_result']['Precision'] + current_check_result_dict['edge_result']['Recall']) if (current_check_result_dict['edge_result']['Precision'] + current_check_result_dict['edge_result']['Recall']) > 0 else 0, 4)
        current_check_result_dict['edge_result']['missingEdges'] = sorted(list(set(all_edge_list).difference(set(edge_check_result_by_VLM))))
        current_check_result_dict['edge_result']['hallucination'] = sorted(list(set(edge_check_result_by_VLM).difference(set(all_edge_list))))
    
        results[current_dpi] = current_check_result_dict
    
    results['decodeErrorLines'] = decode_error_lines

    if save_folder:
        os.makedirs(os.path.dirname(save_folder), exist_ok=True)

        base_name = '.'.join(os.path.basename(file_path).split('.')[:-1])

        save_file = f"{save_folder}/{base_name}.json"
        with open(save_file, 'w') as f:
            json.dump(results, f, ensure_ascii=False, indent=4)
        print(f"Save to {save_file}")

        # 可视化
        save_figure = f"{save_folder}/{base_name}.png"
        plot_dpi_metrics(save_file, save_figure)
    else:
        print("Not save")

    return results


def check_main(model_name: str, current_png: str, check_all: bool = False, save_in_file: bool = True, method: str=""):
    root_folder = f"evaluations/dpi_selection/{model_name}/{current_png}"
    current_png = current_png.replace(".png", "").replace('.dot', '')

    # check root folder existance
    if not os.path.exists(root_folder):
        print(f"Check {root_folder}")
        return
    

    try:
        # load LLM's result files
        result_files = [x for x in os.listdir(f"{root_folder}") if os.path.isfile(os.path.join(root_folder, x))]
        if not check_all:
            result_files.sort(key=lambda f: os.path.getmtime(os.path.join(root_folder, f)))
            result_files = result_files[-1:]

        continue_check = False
        for x in result_files:
            continue_check = continue_check or (not os.path.exists(f"evaluations/dpi_selection/check_results/{model_name}/{os.path.basename(x)[:-5]}json"))

        if not continue_check:
            print(f"Files {result_files} were already checked")
            return None

        print(f"Check file {result_files}")

        # extract ground truth
        extract_taint_path_from_dot.main(f'outputs/5.dpi_selection/{current_png}.dot')
        extract_result_file = f"evaluations/extracted_paths/{current_png}.json"

        extract_result = load_ground_truth_file(extract_result_file) 
        all_node_list = [x.replace('.', ':').replace('_', '@') for x in extract_result['all_nodes']] if method == 'changeCharactor' else extract_result['all_nodes']
        all_edge_list = [x.replace('.', '::').replace('_', '@') for x in extract_result['all_edges']] if method == 'changeCharactor' else extract_result['all_edges']

        # records
        results = {}

        # check and get static result
        for current_file in result_files:
            print(f"Check {current_file}")
            file_path = os.path.join(root_folder, current_file)

            check_result = check_single_file(file_path, all_node_list, all_edge_list, f"evaluations/dpi_selection/check_results/{model_name}/" if save_in_file else "")

            results[current_file] = check_result

        return results
    except KeyError as e:
        print(e)
        return


def load_result_file(file_path: str):
    if not os.path.exists(file_path):
        return None
    
    with open(file_path) as f:
        lines = [line.strip() for line in f if line][1:-4]
    result = json.loads("".join(lines))

    return result
    

def load_ground_truth_file(file_path: str):
    if not os.path.exists(file_path):
        return None
    
    with open(file_path) as f:
        return json.load(f)


def plot_dpi_metrics(check_result_json: str, output_png: str = None):
    """
    读取评估生成的 JSON 文件，绘制 DPI 与 Node/Edge 识别指标的变化曲线图。
    """
    if not os.path.exists(check_result_json):
        print(f"Error: 找不到结果文件 {check_result_json}")
        return

    # 读取 JSON 数据
    with open(check_result_json, 'r', encoding='utf-8') as f:
        results = json.load(f)

    # 你的 JSON 结构最外层是 LLM 跑出的 result_files 的文件名
    # 我们遍历最外层（通常里面只有一个文件，除非开启了 check_all）
    dpis =[]
    
    # 提取所有的 DPI 档位（过滤掉 'decodeErrorLines' 等非数字 key）
    for key in results.keys():
        if key.isdigit():
            dpis.append(int(key))
        
    # 确保 DPI 从小到大排序
    dpis.sort()

    # 我们需要绘制的三大指标
    metrics = ['Precision', 'Recall', 'F1Score']
    
    # 存放绘图数据
    node_data = {m:[] for m in metrics}
    edge_data = {m:[] for m in metrics}

    for dpi in dpis:
        dpi_str = str(dpi)
        
        for m in metrics:
            # 获取数据，如果遇到异常的 None 值，将其替换为 0 防止画图报错
            n_val = results[dpi_str]['node_result'].get(m, 0)
            e_val = results[dpi_str]['edge_result'].get(m, 0)
            
            node_data[m].append(n_val if n_val is not None else 0)
            edge_data[m].append(e_val if e_val is not None else 0)

    # ==================== 开始使用 matplotlib 绘图 ====================
    # 创建 1行3列 的画布，尺寸稍微拉长一点
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    result_file = os.path.basename(check_result_json)
    fig.suptitle(f'DPI Impact on Node & Edge Recognition ({result_file})', fontsize=16, fontweight='bold', y=1.05)

    # 遍历三个指标分别画在三个子图上
    for i, metric in enumerate(metrics):
        ax = axes[i]
        
        # 画 Node 曲线：蓝色实线 + 圆形数据点
        ax.plot(dpis, node_data[metric], marker='o', linestyle='-', color='#42A5F5', linewidth=2, markersize=8, label=f'Node')
        
        # 画 Edge 曲线：橙色虚线 + 三角数据点
        ax.plot(dpis, edge_data[metric], marker='^', linestyle='--', color='#FFA726', linewidth=2, markersize=8, label=f'Edge')
        
        # 设置图表元素
        ax.set_title(f'{metric} vs DPI', fontsize=14)
        ax.set_xlabel('DPI', fontsize=12)
        ax.set_ylabel(metric, fontsize=12)
        
        # 强制让 X 轴仅显示测试过的 DPI 刻度（防止出现 110, 130 这种没测过的无意义网格线）
        ax.set_xticks(dpis)
        
        # 由于指标是百分比，把 Y 轴固定在 0 到 1.05 之间，对比更直观
        ax.set_ylim(-0.05, 1.05)
        
        # 添加浅色虚线网格，方便对齐看数据
        ax.grid(True, linestyle=':', alpha=0.7, color='gray')
        
        # 将图例放在右下角（通常 0 点在左下，线往右上走，右下角最空）
        ax.legend(loc='lower right', fontsize=10)

    # 自动调整子图间距防重叠
    plt.tight_layout()
    
    # 保存或展示
    if output_png:
        os.makedirs(os.path.dirname(output_png), exist_ok=True)
        plt.savefig(output_png, dpi=300, bbox_inches='tight')
        print(f"可视化图表已保存至: {output_png}")
    else:
        plt.show()

# 第二版本：聚合检查v1的所有内容

def extract_method_from_filename(filename: str) -> str:
    """
    从文件名中提取优化方法后缀。
    注意：只有单个短横线 "-name" 才是方法名，
    三个短横线 "---name" 不是方法名，视为无后缀。

    只有已知的优化方法名才被视为有效方法：
    changeCharactor, locate, withNode, onlyFuncName

    例如:
    - "torch.load-changeCharactor_1772455088.json" → "changeCharactor"
    - "torch.load_1772452993.json" → "default" (因为是 --- 不是 -)
    - "torch.load-torch_xxx.json" → "default" (torch 不是有效方法名)
    """
    import re

    # 找到所有匹配项，取最后一个（因为方法名在最后）
    matches = re.findall(r'-([a-zA-Z]+)(?:_|\.)', filename)
    if matches:
        # 取最后一个匹配
        method = matches[-1]
        # 只有在已知方法列表中的才视为有效方法
        if method in VALID_METHODS:
            return method
    return "default"


def aggregate_all_results(model_name: str, save_result: bool = True, output_png: str = None):
    """
    整合统计 evaluation/dpi_selection/check_results/{model} 目录下所有 JSON 文件的结果。
    按不同的优化方法（后缀）分别统计，生成综合统计结果并绘制图表。

    Args:
        model_name: 模型名称，如 "qwen-vl-max"
        save_result: 是否保存聚合结果到 JSON 文件
        output_png: 输出图表路径，默认为 "evaluations/dpi_selection/check_results/{model}_aggregate.png"

    Returns:
        聚合后的统计结果字典，格式: {method: {dpi: {'node': {...}, 'edge': {...}}}}
    """
    check_results_dir = f"evaluations/dpi_selection/check_results/{model_name}"

    if not os.path.exists(check_results_dir):
        print(f"Error: 目录 {check_results_dir} 不存在")
        return None

    # 获取所有 JSON 文件
    json_files = [f for f in os.listdir(check_results_dir) if f.endswith('.json')]
    if not json_files:
        print(f"Error: 目录 {check_results_dir} 中没有 JSON 文件")
        return None

    print(f"找到 {len(json_files)} 个 JSON 文件")

    # 按方法分组聚合: {method: {dpi: {'node': {...}, 'edge': {...}}}}
    aggregated_by_method = {}

    # 统计每个方法、每个 DPI 的文件数量
    method_dpi_count = {}

    for json_file in json_files:
        # 提取方法名
        method = extract_method_from_filename(json_file)

        if method not in aggregated_by_method:
            aggregated_by_method[method] = {}
            method_dpi_count[method] = {}

        file_path = os.path.join(check_results_dir, json_file)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            print(f"读取文件 {json_file} 失败: {e}")
            continue

        # 遍历文件中的每个 DPI
        for dpi_key, dpi_data in data.items():
            if dpi_key == 'decodeErrorLines' or not dpi_key.isdigit():
                continue

            dpi = int(dpi_key)

            if dpi not in aggregated_by_method[method]:
                aggregated_by_method[method][dpi] = {
                    'node': {
                        'Precision': 0.0,
                        'Recall': 0.0,
                        'F1Score': 0.0,
                        'total_files': 0
                    },
                    'edge': {
                        'Precision': 0.0,
                        'Recall': 0.0,
                        'F1Score': 0.0,
                        'total_files': 0
                    }
                }
                method_dpi_count[method][dpi] = 0

            method_dpi_count[method][dpi] += 1
            aggregated_by_method[method][dpi]['node']['total_files'] += 1
            aggregated_by_method[method][dpi]['edge']['total_files'] += 1

            # 累加 Node 指标
            node_result = dpi_data.get('node_result', {})
            if node_result:
                aggregated_by_method[method][dpi]['node']['Precision'] += node_result.get('Precision', 0) or 0
                aggregated_by_method[method][dpi]['node']['Recall'] += node_result.get('Recall', 0) or 0
                aggregated_by_method[method][dpi]['node']['F1Score'] += node_result.get('F1Score', 0) or 0

            # 累加 Edge 指标
            edge_result = dpi_data.get('edge_result', {})
            if edge_result:
                aggregated_by_method[method][dpi]['edge']['Precision'] += edge_result.get('Precision', 0) or 0
                aggregated_by_method[method][dpi]['edge']['Recall'] += edge_result.get('Recall', 0) or 0
                aggregated_by_method[method][dpi]['edge']['F1Score'] += edge_result.get('F1Score', 0) or 0

    # 计算每个方法的平均值
    for method in aggregated_by_method:
        for dpi in aggregated_by_method[method]:
            file_count = method_dpi_count[method].get(dpi, 1)
            if file_count > 0:
                aggregated_by_method[method][dpi]['node']['Precision'] = round(
                    aggregated_by_method[method][dpi]['node']['Precision'] / file_count, 4)
                aggregated_by_method[method][dpi]['node']['Recall'] = round(
                    aggregated_by_method[method][dpi]['node']['Recall'] / file_count, 4)
                aggregated_by_method[method][dpi]['node']['F1Score'] = round(
                    aggregated_by_method[method][dpi]['node']['F1Score'] / file_count, 4)
                aggregated_by_method[method][dpi]['edge']['Precision'] = round(
                    aggregated_by_method[method][dpi]['edge']['Precision'] / file_count, 4)
                aggregated_by_method[method][dpi]['edge']['Recall'] = round(
                    aggregated_by_method[method][dpi]['edge']['Recall'] / file_count, 4)
                aggregated_by_method[method][dpi]['edge']['F1Score'] = round(
                    aggregated_by_method[method][dpi]['edge']['F1Score'] / file_count, 4)

    # 添加汇总信息
    all_dpis = set()
    for method in aggregated_by_method:
        all_dpis.update(aggregated_by_method[method].keys())

    aggregated_by_method['_summary'] = {
        'total_files': len(json_files),
        'methods': list(aggregated_by_method.keys()),
        'method_counts': {m: len(aggregated_by_method[m]) for m in aggregated_by_method if m != '_summary'},
        'all_dpi_values': sorted(all_dpis)
    }

    # 保存结果
    if save_result:
        output_json = f"evaluations/dpi_selection/check_result/{model_name}_aggregate.json"
        os.makedirs(os.path.dirname(output_json), exist_ok=True)
        with open(output_json, 'w', encoding='utf-8') as f:
            json.dump(aggregated_by_method, f, ensure_ascii=False, indent=4)
        print(f"聚合结果已保存至: {output_json}")

    # 绘制图表（按方法分组）
    plot_aggregated_metrics_by_method(aggregated_by_method, model_name, output_png)

    return aggregated_by_method


def plot_aggregated_metrics_by_method(aggregated_by_method: dict, model_name: str, output_png: str = None):
    """
    按不同优化方法绘制聚合后的 DPI 评估指标图表。
    每个方法用不同颜色的曲线表示。
    """
    metrics = ['Precision', 'Recall', 'F1Score']

    # 定义不同方法的颜色
    method_colors = {
        'default': '#1f77b4',  # 蓝色
        'changeCharactor': '#ff7f0e',  # 橙色
        'locate': '#2ca02c',  # 绿色
        'withNode': '#d62728',  # 红色
        'onlyFuncName': '#9467bd',  # 紫色
    }

    # 获取所有方法（排除 _summary）
    methods = [m for m in aggregated_by_method.keys() if m != '_summary']
    if not methods:
        print("Error: 没有找到有效的方法数据")
        return

    # 获取所有 DPI 值
    all_dpis = aggregated_by_method.get('_summary', {}).get('all_dpi_values', [])
    if not all_dpis:
        print("Error: 没有找到 DPI 数据")
        return

    # 创建图表：2行3列，Node 和 Edge 分别画
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    fig.suptitle(f'Aggregated DPI Impact by Method - {model_name}', fontsize=16, fontweight='bold', y=1.02)

    # 为每个方法准备数据
    method_data = {}
    for method in methods:
        method_results = aggregated_by_method[method]
        sorted_dpis = sorted(method_results.keys())

        node_data = {m: [] for m in metrics}
        edge_data = {m: [] for m in metrics}

        for dpi in sorted_dpis:
            for m in metrics:
                node_data[m].append(method_results[dpi]['node'].get(m, 0))
                edge_data[m].append(method_results[dpi]['edge'].get(m, 0))

        method_data[method] = {
            'dpis': sorted_dpis,
            'node': node_data,
            'edge': edge_data
        }

    # 绘制每个指标
    for i, metric in enumerate(metrics):
        # Node 行
        ax_node = axes[0, i]
        # Edge 行
        ax_edge = axes[1, i]

        for method in methods:
            color = method_colors.get(method, '#333333')
            data = method_data[method]

            # Node 曲线
            ax_node.plot(data['dpis'], data['node'][metric], marker='o', linestyle='-',
                        color=color, linewidth=2, markersize=6, label=method)

            # Edge 曲线
            ax_edge.plot(data['dpis'], data['edge'][metric], marker='^', linestyle='--',
                        color=color, linewidth=2, markersize=6, label=method)

        # 设置 Node 子图
        ax_node.set_title(f'Node - {metric}', fontsize=12)
        ax_node.set_xlabel('DPI', fontsize=10)
        ax_node.set_ylabel(metric, fontsize=10)
        ax_node.set_xticks(all_dpis)
        ax_node.set_ylim(-0.05, 1.05)
        ax_node.grid(True, linestyle=':', alpha=0.7, color='gray')
        ax_node.legend(loc='lower right', fontsize=8)

        # 设置 Edge 子图
        ax_edge.set_title(f'Edge - {metric}', fontsize=12)
        ax_edge.set_xlabel('DPI', fontsize=10)
        ax_edge.set_ylabel(metric, fontsize=10)
        ax_edge.set_xticks(all_dpis)
        ax_edge.set_ylim(-0.05, 1.05)
        ax_edge.grid(True, linestyle=':', alpha=0.7, color='gray')
        ax_edge.legend(loc='lower right', fontsize=8)

    plt.tight_layout()

    # 保存图表
    if output_png is None:
        output_png = f"evaluations/dpi_selection/check_results/{model_name}_aggregate.png"

    os.makedirs(os.path.dirname(output_png), exist_ok=True)
    plt.savefig(output_png, dpi=300, bbox_inches='tight')
    print(f"聚合图表已保存至: {output_png}")


# 第三版本：统计dpi下三个任务的准确率

def get_ground_truth(png_name: str):
    """
    获取对应的 ground truth 文件。
    png_name: 如 "7__examples...---torch.load"
    """
    gt_path = f"evaluations/extracted_paths/{png_name.replace('.json', '')}.json"
    if not os.path.exists(gt_path):
        return None
    with open(gt_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def extract_png_name_from_jsonl(jsonl_path: str) -> str:
    """
    从 jsonl 文件路径中提取 png 名称（去掉 method 后缀）。
    例如: ".../7__examples...---torch.load/xxx---torch.load-onlyFuncName_1772543496.jsonl"
    -> "7__examples.academic_paper_scripts.detxoify_lm.generate_samples_gpt._module_---torch.load"
    """
    # 获取目录名
    dir_name = os.path.basename(os.path.dirname(jsonl_path))
    return dir_name


def aggregate_task_results_by_method(model_name: str, target_method: str='', save_result: bool = True, fuzzy_match_flag: bool = False):
    """
    按方法统计所有 jsonl 文件中的三个任务结果。

    Args:
        model_name: 模型名称，如 "qwen-vl-max"
        save_result: 是否保存结果到 JSON 文件

    Returns:
        统计结果字典，格式: {method: {'Task1': {...}, 'Task2': {...}, 'Task3': {...}}}
    """
    dpi_selection_dir = f"evaluations/dpi_selection/{model_name}"

    if not os.path.exists(dpi_selection_dir):
        print(f"Error: 目录 {dpi_selection_dir} 不存在")
        return None

    # 遍历所有子目录
    subdirs = [d for d in os.listdir(dpi_selection_dir)
               if os.path.isdir(os.path.join(dpi_selection_dir, d))]

    print(f"找到 {len(subdirs)} 个测试文件目录")

    # 按方法分组统计
    method_stats = {}

    for subdir in subdirs:
        subdir_path = os.path.join(dpi_selection_dir, subdir)

        # 获取该目录下的所有 jsonl 文件
        jsonl_files = [f for f in os.listdir(subdir_path) if (f.endswith('.jsonl') and not (target_method and method != target_method))]

        for jsonl_file in jsonl_files:
            # 提取方法名
            method = extract_method_from_filename(jsonl_file)

            if method not in method_stats:
                method_stats[method] = {}

            # 读取 ground truth
            png_name = extract_png_name_from_jsonl(os.path.join(subdir_path, jsonl_file))
            ground_truth = get_ground_truth(png_name)

            if ground_truth is None:
                extract_taint_path_from_dot.main(f'outputs/5.dpi_selection/{png_name}.dot')
                ground_truth = get_ground_truth(png_name)

            # check ground truth
            keys = ['all_edges', 'reachable_nodes', 'node_colors']
            for key in keys:
                if key not in ground_truth:
                    # extract ground truth
                    extract_taint_path_from_dot.main(f'outputs/5.dpi_selection/{png_name}.dot')
                    ground_truth = get_ground_truth(png_name)

            if ground_truth is None:
                print(f"Warning: 找不到 ground truth for {png_name}")
                continue


            # 读取 jsonl 文件
            jsonl_path = os.path.join(subdir_path, jsonl_file)
            try:
                with open(jsonl_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        if not line.strip():
                            continue
                        data = json.loads(line)
                        dpi = data.get('currentDpi')
                        response_str = data.get('response', '')

                        if dpi not in method_stats[method]:
                            method_stats[method][dpi] = {
                                'Task1': {'correct': 0, 'total': 0, 'accuracy': 0, 'static': {'correct': [], 'wrong': []}},
                                'Task2': {'correct': 0, 'total': 0, 'accuracy': 0, 'static': {'correct': [], 'wrong': []}}, 
                                'Task3': {'correct': 0, 'total': 0, 'accuracy': 0, 'static': {'correct': [], 'wrong': []}}
                            }

                        # 解析 response
                        try:
                            response = json.loads(response_str.replace('```json', '').replace('```', ''))
                        except:
                            continue
                        
                        if fuzzy_match_flag:
                            true_all_node_list = ground_truth.get("all_nodes", [])

                        # Task1: Topology - 检查 Target_Node
                        task1 = response.get('Task1_Topology', {})
                        predicted_target = task1.get('Target_Node', '')
                        upstream_nodes = task1.get('Upstream_Nodes', [])
                        downstream_nodes = task1.get('Downstream_Nodes', [])
                        # 模糊匹配
                        if fuzzy_match_flag:
                            upstream_nodes = [fuzzy_match(x, true_all_node_list) for x in upstream_nodes]
                            downstream_nodes = [fuzzy_match(x, true_all_node_list) for x in downstream_nodes]

                        # 获得正确答案
                        true_upstream_nodes = [x.split('->')[0].strip() for x in ground_truth.get('all_edges', []) if x.split('->')[-1].strip() == predicted_target]
                        true_downstream_nodes = [x.split('->')[-1].strip() for x in ground_truth.get('all_edges', []) if x.split('->')[0].strip() == predicted_target]
                        # check
                        method_stats[method][dpi]['Task1']['total'] += 1
                        if (
                            set(upstream_nodes) == set(true_upstream_nodes)
                            and set(downstream_nodes) == set(true_downstream_nodes)
                        ):
                            method_stats[method][dpi]['Task1']['correct'] += 1
                            # method_stats[method][dpi]['Task1']['static']['correct'].append()
                        else:
                            method_stats[method][dpi]['Task1']['static']['wrong'].append({
                                'task': 'Task1',
                                'predicted': predicted_target,
                                'upstream': ','.join(upstream_nodes),
                                'true_upstream': ','.join(true_upstream_nodes),
                                'downstream': ','.join(downstream_nodes),
                                'true_downstream': ','.join(true_downstream_nodes),
                            })

                        # Task2: Color Grounding - 检查颜色标注
                        task2 = response.get('Task2_Color_Grounding', {})
                        node_colors_dict = ground_truth.get('node_colors', {})
                        for node_name, predicted_color in task2.items():
                            method_stats[method][dpi]['Task2']['total'] += 1
                            if predicted_color in node_colors_dict.get(node_name, []):
                                method_stats[method][dpi]['Task2']['correct'] += 1
                            else:
                                method_stats[method][dpi]['Task2']['static']['wrong'].append({
                                    'task': 'Task2',
                                    'node': node_name,
                                    'predicted': predicted_color,
                                    'true': ', '.join(node_colors_dict.get(node_name, []))
                                })

                        # Task3: OCR - 检查函数名转录
                        task3 = response.get('Task3_OCR', {})
                        predicted_func = task3.get('Transcribed_Function_Name', '')
                        # TODO 获得正确答案——先以最终的sink点为例
                        true_end_node = [x for x, reach_list in ground_truth.get('reachable_nodes', {}).items() if len(reach_list) == 0][0]

                        method_stats[method][dpi]['Task3']['total'] += 1
                        # 检查是否匹配
                        if predicted_func == true_end_node:
                            method_stats[method][dpi]['Task3']['correct'] += 1
                            # method_stats[method][dpi]['Task3']['static']['correct'].append()
                        else:
                            method_stats[method][dpi]['Task3']['static']['wrong'].append({
                                'task': 'Task3',
                                'predicted': predicted_func,
                                'true': true_end_node
                            })
                            

            except Exception as e:
                print(f"Error reading {jsonl_file}: {e}")
                continue

    # 计算准确率
    for method in method_stats:
        for task in ['Task1', 'Task2', 'Task3']:
            for dpi in method_stats[method]:
                total = method_stats[method][dpi][task]['total']
                correct = method_stats[method][dpi][task]['correct']
                method_stats[method][dpi][task]['accuracy'] = round(correct / total, 4) if total > 0 else 0

    # 保存结果
    if save_result:
        output_json = f"evaluations/dpi_selection/check_results/{model_name}{'-fuzzyMatch' if fuzzy_match_flag else ''}_task_accuracy.json"
        os.makedirs(os.path.dirname(output_json), exist_ok=True)
        with open(output_json, 'w', encoding='utf-8') as f:
            json.dump(method_stats, f, ensure_ascii=False, indent=4)
        print(f"任务统计结果已保存至: {output_json}")

        # 绘制每个 Task 的准确率折线图
        plot_task_accuracy(method_stats, model_name, output_json.replace('.json', '.png'))

    return method_stats


def plot_task_accuracy(method_stats: dict, model_name: str, output_png: str):
    """
    绘制每个 Task 的准确率折线图。
    横坐标是 DPI，纵坐标是准确率，每条折线是一种 method。
    """
    # 获取所有方法
    methods = list(method_stats.keys())

    # 获取所有 DPI 值
    all_dpis = set()
    for method in methods:
        all_dpis.update(method_stats[method].keys())
    sorted_dpis = sorted([int(d) for d in all_dpis])
    sorted_dpis = [str(d) for d in sorted_dpis]

    # 定义方法颜色
    method_colors = {
        'dense': '#ff7f0e',
        'onlyFuncName': '#2ca02c',
    }

    tasks = ['Task1', 'Task2', 'Task3']
    task_names = {'Task1': 'Topology', 'Task2': 'Color Grounding', 'Task3': 'OCR'}

    # 创建 1行3列 的图表
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    fig.suptitle(f'Task Accuracy by DPI and Method - {model_name}', fontsize=16, fontweight='bold', y=1.02)

    for i, task in enumerate(tasks):
        ax = axes[i]

        for method in methods:
            color = method_colors.get(method, '#333333')
            accuracies = []

            for dpi in sorted_dpis:
                acc = method_stats[method].get(dpi, {}).get(task, {}).get('accuracy', 0)
                accuracies.append(acc)

            ax.plot(sorted_dpis, accuracies, marker='o', linestyle='-',
                   color=color, linewidth=2, markersize=6, label=method)

        ax.set_title(f'{task} - {task_names[task]}', fontsize=12)
        ax.set_xlabel('DPI', fontsize=10)
        ax.set_ylabel('Accuracy', fontsize=10)
        ax.set_xticks(sorted_dpis)
        ax.set_ylim(-0.05, 1.05)
        ax.grid(True, linestyle=':', alpha=0.7, color='gray')
        ax.legend(loc='lower right', fontsize=8)

    plt.tight_layout()

    # 保存图表
    # output_png = f"evaluations/dpi_selection/check_results/{model_name}_task_accuracy.png"
    os.makedirs(os.path.dirname(output_png), exist_ok=True)
    plt.savefig(output_png, dpi=150, bbox_inches='tight')
    print(f"任务准确率图表已保存至: {output_png}")


if __name__ == "__main__":
    check_png = "13__tasks.main._module_---pickle.load"
    check_model = "qwen-vl-max"
    method = 'changeCharactor'

    # check_main(model_name=check_model, current_png=check_png, method=method)

    # 示例：调用聚合统计函数
    # aggregate_all_results("qwen-vl-plus")

    # 示例：按方法统计任务结果
    aggregate_task_results_by_method("qwen-vl-max", save_result=True, fuzzy_match_flag=False)
    aggregate_task_results_by_method("qwen-vl-plus", save_result=True, fuzzy_match_flag=False)
    # print(json.dumps(aggregate_task_results_by_method("qwen-vl-max", save_result=True), indent=4))
