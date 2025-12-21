"""关键字匹配器 - 负责关键字模糊匹配和排序"""

from thefuzz import fuzz

from ..config import FUZZY_MATCH_THRESHOLD


def fuzzy_match(keyword1: str, keyword2: str) -> float:
    """计算两个关键词的相似度（使用 Levenshtein Distance）

    Args:
        keyword1: 第一个关键词
        keyword2: 第二个关键词

    Returns:
        相似度分数 (0-1)
    """
    return fuzz.ratio(keyword1.lower(), keyword2.lower()) / 100.0


def score_match(query_keywords: list[str], file_keywords: frozenset) -> int:
    """计算匹配分数（匹配到的关键字个数）

    Args:
        query_keywords: 查询关键词列表
        file_keywords: 文件的 keywords set

    Returns:
        匹配分数（匹配到的关键字个数）
    """
    match_count = 0
    file_keywords_list = list(file_keywords)

    for query_kw in query_keywords:
        # 检查是否有精确匹配或模糊匹配
        for file_kw in file_keywords_list:
            if (
                query_kw == file_kw
                or fuzzy_match(query_kw, file_kw) >= FUZZY_MATCH_THRESHOLD
            ):
                match_count += 1
                break  # 每个查询关键词最多匹配一次

    return match_count
