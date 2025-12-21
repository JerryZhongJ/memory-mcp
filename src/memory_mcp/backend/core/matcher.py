"""关键字匹配器 - 负责关键字模糊匹配和排序"""

from thefuzz import fuzz

from ..config import FUZZY_MATCH_THRESHOLD


def fuzzy_match(keyword1: str, keyword2: str) -> float:
    return fuzz.ratio(keyword1.lower(), keyword2.lower()) / 100.0


def score_match(query_keywords: list[str], file_keywords: frozenset) -> int:
    match_count = 0
    file_keywords_list = list(file_keywords)

    for query_kw in query_keywords:
        for file_kw in file_keywords_list:
            if (
                query_kw == file_kw
                or fuzzy_match(query_kw, file_kw) >= FUZZY_MATCH_THRESHOLD
            ):
                match_count += 1

    return match_count
