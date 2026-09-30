# -*- coding: utf-8 -*-
"""
混合检索器（语义 70% + 关键词 30%）
=====================================
融合公式: score_final = α × score_semantic + (1-α) × score_keyword

融合流程:
  1. 分别调用 BM25 和 Vector 检索各取 Top-K*2 候选
  2. 分数归一化到 [0,1]
  3. 加权融合: final_score = α × vec_norm + (1-α) × keyword_norm
  4. 去重: 同一 chunk_id 的多次出现取最高融合分
  5. 排序返回 Top-K
"""

from typing import List, Dict

from config.settings import HYBRID_ALPHA, TOP_K
from .bm25_retriever import BM25Retriever
from .vector_retriever import VectorRetriever


class HybridRetriever:
    def __init__(self, bm25: BM25Retriever, vector: VectorRetriever,
                 alpha: float = HYBRID_ALPHA):
        self.bm25 = bm25
        self.vector = vector
        self.alpha = alpha

    def retrieve(self, query: str, k: int = TOP_K) -> List[Dict]:
        # 并行获取候选（多取一些候选以便融合）
        candidates = 2 * k
        bm25_results = self.bm25.retrieve(query, k=candidates)
        vec_results = self.vector.retrieve(query, k=k)
        merged = {}  # chunk_id → scores

        # 向量检索结果
        for r in vec_results:
            cid = r.get('chunk_id', '')
            if cid:
                merged[cid] = {
                    'content': r['content'],
                    'metadata': r.get('metadata', {}),
                    'chunk_id': cid,
                    'semantic_score': r['score'],
                    'keyword_score': 0.0,
                }

        # BM25 结果（同一 chunk_id 合并分数）
        for r in bm25_results:
            cid = r['chunk']['chunk_id']
            kw_score = r['score']
            if cid in merged:
                merged[cid]['keyword_score'] = max(merged[cid]['keyword_score'], kw_score)
            else:
                merged[cid] = {
                    'content': r['chunk']['content'],
                    'metadata': r['chunk']['metadata'],
                    'chunk_id': cid,
                    'semantic_score': 0.0,
                    'keyword_score': kw_score,
                }   

        #加权融合
        for cid, info in merged.items():
            info['fusion_score'] = round(
                self.alpha * info['semantic_score'] + (1 - self.alpha) * info['keyword_score'],
                4
            )
        # 排序取 top-k
        ranked = sorted(merged.values(),
                        key=lambda x: x['fusion_score'],
                        reverse=True)[:k]
        return ranked
