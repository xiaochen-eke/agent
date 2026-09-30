# -*- coding: utf-8 -*-
"""
评测指标计算
============
用于评估检索效果和生成质量
"""

from typing import List, Dict


def calc_retrieval_precision(retrieved_sources: List[str], relevant_sources: List[str]) -> float:
    """检索精确率: 检索结果中相关文档的比例"""
    if not retrieved_sources:
        return 0.0
    hits = sum(1 for s in retrieved_sources if any(r in s for r in relevant_sources))
    return hits / len(retrieved_sources)


def calc_retrieval_recall(retrieved_sources: List[str], relevant_sources: List[str]) -> float:
    """检索召回率: 相关文档中被检索到的比例"""
    if not relevant_sources:
        return 1.0
    hits = sum(1 for r in relevant_sources if any(r in s for s in retrieved_sources))
    return hits / len(relevant_sources)


def calc_mrr(retrieved_sources: List[str], relevant_sources: List[str]) -> float:
    """MRR (Mean Reciprocal Rank): 第一个相关文档排名的倒数"""
    for i, s in enumerate(retrieved_sources):
        if any(r in s for r in relevant_sources):
            return 1.0 / (i + 1)
    return 0.0


def source_diversity(semantic_sources: List[str], hybrid_sources: List[str]) -> Dict:
    """检索结果来源多样性分析"""
    sem_set = set(semantic_sources)
    hyb_set = set(hybrid_sources)

    return {
        "semantic_only": list(sem_set - hyb_set),
        "hybrid_only": list(hyb_set - sem_set),
        "overlap": list(sem_set & hyb_set),
        "semantic_count": len(sem_set),
        "hybrid_count": len(hyb_set),
        "overlap_count": len(sem_set & hyb_set),
    }
