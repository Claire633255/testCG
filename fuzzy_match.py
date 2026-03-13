from difflib import SequenceMatcher


def fuzzy_match(query: str, target_list: list, threshold: float = 0.85) -> str | None:
    """
    模糊匹配功能。

    Args:
        query: 当前要匹配的字符串
        target_list: 目标字符串列表
        threshold: 匹配阈值，默认为 0.95 (95%)

    Returns:
        - 如果当前字符串在列表中（100%匹配），返回该字符串（str）
        - 如果有匹配度超过 threshold 的，返回匹配的字符串列表（list）
        - 如果匹配失败，返回 None
    """
    if not query or not target_list:
        return query

    # 首先检查是否完全匹配（100%）
    if query in target_list:
        return query

    # 计算与每个目标字符串的相似度
    matches = []
    for target in target_list:
        similarity = SequenceMatcher(None, query, target).ratio()
        if similarity >= threshold:
            matches.append((target, similarity))

    # 如果有超过阈值的匹配，返回匹配列表
    if matches:
        matches.sort(key=lambda x: x[1], reverse=True)
        return matches[0][0]

    # 匹配失败
    return query


if __name__ == "__main__":
    # 测试示例
    test_list = [
        "megatron.training.checkpointing.load_checkpoint",
        "megatron.training.checkpointing._load_base_checkpoint",
        "megatron.training.checkpointing.load_args_from_checkpoint",
        "megatron.training.training.initialize_megatron",
        "torch.load",
        "tasks.main.<module>"
    ]

    # 测试1：完全匹配
    result1 = fuzzy_match("torch.load", test_list)
    print(f"测试1 (完全匹配): {result1}")

    # 测试2：模糊匹配
    result2 = fuzzy_match("megatron.training.checkpointing.load_checkpoints", test_list)
    print(f"测试2 (模糊匹配): {result2}")
    result2 = fuzzy_match("megatron.training.initialize_megatron", test_list)
    print(f"测试2 (模糊匹配): {result2}")

    # 测试3：匹配失败
    result3 = fuzzy_match("random.function.name", test_list)
    print(f"测试3 (匹配失败): {result3}")
