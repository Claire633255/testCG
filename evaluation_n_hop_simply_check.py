import os
import json
import matplotlib.pyplot as plt

from fuzzy_match import fuzzy_match

PRINT_OUTPUT = False
TRICKY_FIX_UNDERLINE = False


def aggregate_n_hop_results(model_name: str, use_text: bool = False, save_result: bool = True, run_check: bool = True, fuzzy_match_flag: bool = False):
    """
    聚合统计指定 model 的所有 n_hop 测试结果。

    目录结构:
    - 新数据: evaluations/image_vs_text/n_hop/{model_name}/{image|text}/{png_name}/*.jsonl

    Args:
        model_name: 模型名称，如 "qwen-vl-max"
        use_text: 是否使用 text 模式（否则使用 image）
        save_result: 是否保存结果到 JSON 文件
        run_check: 是否先运行 check_main 进行检查

    Returns:
        统计结果字典
    """
    input_format = "text" if use_text else "image"
    root_folder = f"evaluations/image_vs_text/n_hop/{model_name}/{input_format}"

    if not os.path.exists(root_folder):
        print(f"Error: 目录 {root_folder} 不存在")
        return None

    # 获取所有测试文件目录
    test_dirs = [d for d in os.listdir(root_folder)
                 if os.path.isdir(os.path.join(root_folder, d))]
    print(f"找到 {len(test_dirs)} 个测试文件目录")

    # 汇总统计
    stats = {
        'total_files': len(test_dirs),
        'total_results': 0,
        'overall_check': {'correct': 0, 'total': 0},
        'by_hop': {},
    }

    # 遍历每个测试文件目录，先运行 check_main，然后读取结果
    for i, test_dir in enumerate(test_dirs):
        current_png = test_dir.replace(".png", "")

        # 先调用 check_main 进行检查
        if run_check:
            print(f"[{i+1}/{len(test_dirs)}] 运行 check_main for {current_png}")
            file_result = check_main(model_name=model_name, use_text=use_text, current_png=current_png, check_all=True, save_in_file=True, fuzzy_match_flag=fuzzy_match_flag)

        try:
            # 从 correctResultCount 提取（格式如 "22 / 22 = 1.0"）
            hop_correct_str = file_result.get('correctResultCount', {})
            for hop_str, accuracy_str in hop_correct_str.items():
                try:
                    # 解析 "correct / total = accuracy"
                    parts = accuracy_str.split('=')[0].strip().split('/')
                    correct = int(parts[0].strip())
                    total = int(parts[1].strip())
                except:
                    continue
                stats['total_results'] += total
                stats['overall_check']['total'] += total
                stats['overall_check']['correct'] += correct

                hop = int(hop_str)
                if hop not in stats['by_hop']:
                    stats['by_hop'][hop] = {'correct': 0, 'total': 0}
                stats['by_hop'][hop]['correct'] += correct
                stats['by_hop'][hop]['total'] += total

        except Exception as e:
            print(f"Error reading result for {current_png}: {e}")
            continue

    # 计算准确率
    stats['overall_check']['accuracy'] = round(
        stats['overall_check']['correct'] / stats['overall_check']['total'], 4
    ) if stats['overall_check']['total'] > 0 else 0

    for hop in stats['by_hop']:
        stats['by_hop'][hop]['accuracy'] = round(
            stats['by_hop'][hop]['correct'] / stats['by_hop'][hop]['total'], 4
        ) if stats['by_hop'][hop]['total'] > 0 else 0

    # 保存结果
    if save_result:
        output_json = f"evaluations/image_vs_text/n_hop/check_results/{model_name}_{input_format}_aggregate{'-fuzzyMatch' if fuzzy_match_flag else ''}.json"
        os.makedirs(os.path.dirname(output_json), exist_ok=True)
        with open(output_json, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=4)
        print(f"聚合结果已保存至: {output_json}")

        # 绘制图表
        plot_n_hop_accuracy(stats, model_name, input_format, output_json.replace('.json', '.png'))

    return stats

def plot_n_hop_accuracy(stats: dict, model_name: str, input_format: str, output_png: str):
    """绘制 n_hop 准确率折线图"""
    if not stats.get('by_hop'):
        print("没有按 hop 数统计的数据")
        return

    hops = sorted(stats['by_hop'].keys())
    accuracies = [stats['by_hop'][h]['accuracy'] for h in hops]
    totals = [stats['by_hop'][h]['total'] for h in hops]

    fig, ax = plt.subplots(figsize=(10, 6))

    ax.plot(hops, accuracies, marker='o', linestyle='-', color='#42A5F5', linewidth=2, markersize=8)
    ax.set_xlabel('Passed Hop', fontsize=12)
    ax.set_ylabel('Accuracy', fontsize=12)
    ax.set_title(f'N-Hop Path Accuracy - {model_name} ({input_format})', fontsize=14)
    ax.set_xticks(hops)
    ax.set_ylim(0, 1.05)
    ax.grid(True, linestyle=':', alpha=0.7)

    # 在点上显示准确率和数量
    for h, acc, total in zip(hops, accuracies, totals):
        ax.annotate(f'{acc:.2f}\n(n={total})', (h, acc), textcoords="offset points", xytext=(0,10), ha='center', fontsize=8)

    plt.tight_layout()

    os.makedirs(os.path.dirname(output_png), exist_ok=True)
    plt.savefig(output_png, dpi=300, bbox_inches='tight')
    print(f"图表已保存至: {output_png}")

def compare_models(model_name: str, input_formats: list = None, fuzzy_match_flag: bool = False):
    """
    将多个 model 的 text 和 image 结果画在一张图上进行对比。

    Args:
        model_names: 模型名称列表，如 ["qwen-vl-max", "qwen-vl-plus"]
        input_formats: 输入格式列表，默认为 ["image", "text"]
    """
    if input_formats is None:
        input_formats = ["image", "text"]

    # 定义颜色
    colors = {
        'image': '#1f77b4',   # 蓝色
        'text': '#ff7f0e',  # 橙色
    }

    # 收集所有数据
    all_data = {}
    all_hops = set()

    all_data[model_name] = {}
    for input_format in input_formats:
        # 读取聚合结果文件
        result_file = f"evaluations/image_vs_text/n_hop/check_results/{model_name}_{input_format}_aggregate{'-fuzzyMatch' if fuzzy_match_flag else ''}.json"
        if os.path.exists(result_file):
            with open(result_file, 'r', encoding='utf-8') as f:
                stats = json.load(f)
                all_data[model_name][input_format] = stats
                all_hops.update(stats.get('by_hop', {}).keys())
        else:
            print(f"Warning: 结果文件不存在 {result_file}")

    if not all_hops:
        print("没有找到任何统计数据")
        return

    sorted_hops = sorted(all_hops)

    # 绘制折线图
    fig, ax = plt.subplots(figsize=(12, 7))

    for input_format in input_formats:
        if model_name not in all_data or input_format not in all_data[model_name]:
            continue

        stats = all_data[model_name][input_format]
        by_hop = stats.get('by_hop', {})

        accuracies = [by_hop.get(h, {}).get('accuracy', 0) for h in sorted_hops]
        color = colors.get(input_format, '#333333')
        label = f"{model_name} ({input_format})"

        ax.plot(sorted_hops, accuracies, marker='o', linestyle='-',
                color=color, linewidth=2, markersize=6, label=label)

    ax.set_xlabel('Passed Hop', fontsize=12)
    ax.set_ylabel('Accuracy', fontsize=12)
    ax.set_title('N-Hop Path Accuracy Comparison', fontsize=14)
    ax.set_xticks(sorted_hops)
    ax.set_ylim(0, 1.05)
    ax.grid(True, linestyle=':', alpha=0.7)
    ax.legend(loc='lower left', fontsize=10)

    plt.tight_layout()

    output_png = f"evaluations/image_vs_text/n_hop/check_results/comparison_{model_name}{'-fuzzyMatch' if fuzzy_match_flag else ''}.png"
    os.makedirs(os.path.dirname(output_png), exist_ok=True)
    plt.savefig(output_png, dpi=300, bbox_inches='tight')
    print(f"对比图表已保存至: {output_png}")

def check_main(model_name: str, use_text: bool, current_png: str, check_all: bool = False, fuzzy_match_flag: bool = False, save_in_file: bool = True):
    root_folder = f"evaluations/image_vs_text/n_hop/{model_name}/"
    input_format = "image" if not use_text else "text"
    root_folder = f"{root_folder}{input_format}/{current_png}"

    # check root folder existance
    if not os.path.exists(root_folder):
        print(f"No such folder: {root_folder}")
        return
    current_png = current_png.replace(".png", "").replace('.dot', '')

    ground_truth_file = f"evaluations/image_vs_text/n_hop/ground_truth/{current_png}.json"
    corresponding_extract_result_file = f"evaluations/extracted_paths/{current_png}.json"
    ground_truth_result_dict = load_ground_truth_file(ground_truth_file)
    if not ground_truth_result_dict:
        corresponding_extract_result_file = f"evaluations/extracted_paths/{current_png}.json"
        ground_truth_result_dict = simply_get_ground_truth_from_extract_file(corresponding_extract_result_file, save_in_file=True)
        if not ground_truth_result_dict:
            print(f"Error: 无法从 {corresponding_extract_result_file} 中获取 ground truth")
            return

    # all_node_list = list(ground_truth_result_dict.keys())

    try:
        all_node_list = load_ground_truth_file(corresponding_extract_result_file)['all_nodes']
    except TypeError:
        import extract_taint_path_from_dot
        dot_folder = 'outputs/4.n_hop_evaluation'
        all_node_list = extract_taint_path_from_dot.main(os.path.join(dot_folder, f"{current_png}.dot"))

    # if "all_paths" in ground_truth_result_dict:
    #     ground_truth_result_dict = ground_truth_result_dict["all_paths"]
    
    # load LLM's result files
    result_files = [x for x in os.listdir(f"{root_folder}") if os.path.isfile(os.path.join(root_folder, x)) and "--" in x]
    if not check_all:
        result_files.sort()
        result_files = result_files[-1:]
    print(f"Check file {result_files}")

    # records
    decode_error_lines = []
    wrong_results = {}
    node_not_in_results = []
    correct_results = {}
    hop_correct_percent = {}
    total_counts = 0
    correct_count = 0
    is_true_count = 0
    is_false_count = 0

    # check and get static result
    for current_file in result_files:
        file_path = os.path.join(root_folder, current_file)

        with open(file_path) as f:
            lines = [line.strip() for line in f if line]
            total_counts = len(lines)
        
        for line in lines:
            try:
                each_analyse_result = json.loads(line)
                passed_hop = int(each_analyse_result['passedHop'])

                # 读取结果并修复一些格式问题
                # TODO 尝试tricky得修复下划线问题？
                taint_analyse_result = json.loads(each_analyse_result['response'].replace('```json', '').replace('```', '')) if not TRICKY_FIX_UNDERLINE else json.loads(each_analyse_result['response'].replace('```json', '').replace('```', '')
                                                  .replace('megatron.training.checkpointing.load_base_checkpoint', 'megatron.training.checkpointing._load_base_checkpoint'))
                
                if fuzzy_match_flag:
                    taint_analyse_result['start'] = fuzzy_match(taint_analyse_result['start'], all_node_list)
                    taint_analyse_result['end'] = fuzzy_match(taint_analyse_result['end'], all_node_list)

                # 尝试修正给出路径中可能不存在空格等问题
                taint_analyse_result['taint_path'] = ' -> '.join([x.strip() if not fuzzy_match_flag else fuzzy_match(x.strip(), all_node_list) for x in taint_analyse_result['taint_path'].split('->')])
            except json.decoder.JSONDecodeError as e:
                decode_error_lines.append(line)
                continue

            if passed_hop not in hop_correct_percent:
                hop_correct_percent[passed_hop] = [0, 0]
            hop_correct_percent[passed_hop][-1] += 1

            # 开始检查
            # 首先检查LLM给出的两个node是否正确
            node_check_flag = (taint_analyse_result['start'] in all_node_list) and (taint_analyse_result['end'] in all_node_list)

            # 看是否真的有满足n hop的路径存在
            actual_n_hop_paths = []
            try:
                actual_n_hop_paths = [' -> '.join(x) for x in ground_truth_result_dict[taint_analyse_result['start']][taint_analyse_result['end']] if passed_hop == (len(x)-1)]
            except:
                pass

            current_check_result_dict = {
                    'isCapable_byLLM': taint_analyse_result['is_capable'],
                    'isCapable_actual': bool(actual_n_hop_paths),

                    'passedHop': passed_hop,
                    'hopCount_byLLM': taint_analyse_result['target_hops'],
                    'taintPathHopCount_byLLM': max(0, len(taint_analyse_result['taint_path'].split('->')) - 1),

                    'taintPathResult_byLLM': taint_analyse_result['taint_path'],
                    'taintPathResult_actual': actual_n_hop_paths,

                    'reason_byLLM': taint_analyse_result['reason'] if "reason" in taint_analyse_result else ''
                }
            # if 'reason' not in taint_analyse_result:
            #     print("No 'reason' in response")
            #     print(taint_analyse_result)

            if not node_check_flag:
                node_not_in_results.append(current_check_result_dict)
                continue

            if (
                # (not (bool(actual_n_hop_paths) ^ taint_analyse_result["is_capable"]))  # 两个的结果需要是一致的，即都是true/false
                (bool(actual_n_hop_paths) == taint_analyse_result['is_capable'] == False)  # 都没有就对
                or (
                    (bool(actual_n_hop_paths) == taint_analyse_result['is_capable'] == True)  # 都有得出正确分析结果
                    and (taint_analyse_result['taint_path'] in actual_n_hop_paths)  # 给出的路径要存在
                    and (passed_hop == taint_analyse_result['target_hops'] == (len(taint_analyse_result['taint_path'].split('->')) - 1))
                  )  # 要查询的跳数 == LLM判断的跳数 == LLM给出路径的跳数
                ):
                correct_count += 1
                is_true_count += taint_analyse_result['is_capable']
                is_false_count += (not taint_analyse_result['is_capable'])

                # add to right_results
                if passed_hop not in correct_results:
                    correct_results[passed_hop] = {}
                if taint_analyse_result['start'] not in correct_results[passed_hop]:
                    correct_results[passed_hop][taint_analyse_result['start']] = {}
                if taint_analyse_result['end'] not in correct_results[passed_hop][taint_analyse_result['start']]:
                    correct_results[passed_hop][taint_analyse_result['start']][taint_analyse_result['end']] = []

                correct_results[passed_hop][taint_analyse_result['start']][taint_analyse_result['end']].append(current_check_result_dict)

                hop_correct_percent[passed_hop][0] += 1
            else:
                # add to wrong_results
                if passed_hop not in wrong_results:
                    wrong_results[passed_hop] = {}
                if taint_analyse_result['start'] not in wrong_results[passed_hop]:
                    wrong_results[passed_hop][taint_analyse_result['start']] = {}
                if taint_analyse_result['end'] not in wrong_results[passed_hop][taint_analyse_result['start']]:
                    wrong_results[passed_hop][taint_analyse_result['start']][taint_analyse_result['end']] = []

                wrong_results[passed_hop][taint_analyse_result['start']][taint_analyse_result['end']].append(current_check_result_dict)


    # 按照跳数整理
    # 统计正确的结果
    correct_count_results = {}
    for item in list(hop_correct_percent.keys()):
        if item not in correct_count_results:
            correct_count_results[item] = f"{hop_correct_percent[item][0]} / {hop_correct_percent[item][-1]} = {round(hop_correct_percent[item][0]/hop_correct_percent[item][1], 4)}"
        else:
            print(f"[ERROR] hop count repeat -- {item}")

    # sort
    correct_count_results = {k: v for k, v in sorted(correct_count_results.items(), key=lambda item: item[0])}
    wrong_results = {k: v for k, v in sorted(wrong_results.items(), key=lambda item: item[0])}
    

    check_result = {
        'modelName': model_name,
        'inputFormat': input_format,
        'currentPng': current_png,
        'correctCount': correct_count,
        'checkTrueCount': is_true_count,
        'checkFalseCount': is_false_count,
        'totalCounts': total_counts,
        'accuracy': round(correct_count / total_counts, 4),
        'correctResultCount': correct_count_results,
        'correctResultLines': correct_results,
        'wrongResultLines': wrong_results,
        'nodeNotInResults': node_not_in_results,
        'decodeErrorLines': decode_error_lines
    }

    if PRINT_OUTPUT:
        print(json.dumps(check_result, indent=4))

    if save_in_file:
        save_file = f"evaluations/image_vs_text/n_hop/check_results/{model_name}/{input_format}/{current_png if check_all else result_files[0]}{'-tricky修复下划线问题' if TRICKY_FIX_UNDERLINE else ''}{'-fuzzyMatch' if fuzzy_match_flag else ''}.json"
        os.makedirs(os.path.dirname(save_file), exist_ok=True)
        with open(save_file, 'w') as f:
            json.dump(check_result, f, ensure_ascii=False, indent=4)
        print(f"Save to {save_file}")
    else:
        print("Not save")

    return check_result

def load_ground_truth_file(file_path: str):
    if not os.path.exists(file_path):
        return None
    
    with open(file_path) as f:
        return json.load(f)


def simply_get_ground_truth_from_extract_file(extract_file_path: str, save_in_file: bool=True):
    extract_content = load_ground_truth_file(extract_file_path)
    if not extract_content:
        print("Not exist")
        return None
    
    ground_truth_candidate = extract_content.get('all_paths', {})
    if not ground_truth_candidate:
        print("No ")
        return None

    node_color_dict = extract_content.get('node_colors', {})
    if not node_color_dict:
        print("No node_color_dict")
        return None
    
    result = {}

    for start_node, end_node_paths in ground_truth_candidate.items():
        for end_node, paths in end_node_paths.items():
            if start_node not in result:
                result[start_node] = {}
            if end_node not in result[start_node]:
                result[start_node][end_node] = []
            
            for each_path in paths:
                corrent_path_color_list = [node_color_dict[node][0] for node in each_path]
                if "Gray" in corrent_path_color_list or "Green" in corrent_path_color_list:
                    continue
                else:
                    result[start_node][end_node].append(each_path)

    if save_in_file:
        save_path = f'evaluations/image_vs_text/n_hop/ground_truth/{os.path.basename(extract_file_path)}'
        with open(save_path, 'w') as f:
            json.dump(result, f, ensure_ascii=False, indent=4)
        
        print(f"Save to: {save_path}")

    return result
            


if __name__ == "__main__":
    check_png = "8__pretrain_t5._module_---torch.load"
    check_model = "qwen-vl-max"

    # 检查单独内容
    # check_main(model_name=check_model, use_text=False, current_png=check_png)

    # 先运行 check_main 再聚合
    aggregate_n_hop_results("qwen-vl-plus", use_text=False, save_result=True, run_check=True, fuzzy_match_flag=True)
    # # 直接聚合已有结果
    # aggregate_n_hop_results("qwen-vl-max", use_text=False, save_result=True, run_check=True, fuzzy_match_flag=True)


    # compare_models("qwen-vl-max")
    # compare_models("qwen-vl-plus")