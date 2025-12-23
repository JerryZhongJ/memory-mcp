def score_match(query_keywords: list[str], mem_keywords: frozenset) -> float:
    score = 0.0
    mem_keywords_list = list(mem_keywords)

    for query_kw in query_keywords:
        for mem_kw in mem_keywords_list:
            if query_kw in mem_kw:
                score += len(query_kw) / len(mem_kw)

    return score
