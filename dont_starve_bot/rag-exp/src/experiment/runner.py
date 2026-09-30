# -*- coding: utf-8 -*-
"""
实验编排器
==========
RAG 对比实验主控：
  ① 纯语义检索 vs 混合检索（Top-K 对比）
  ② 纯 GLM vs GLM+RAG（生成结果对比）
"""

import time
from typing import List, Dict
from dataclasses import dataclass, field

from config.settings import (
    KNOWLEDGE_BASE_DIR, CHUNK_SIZE, CHUNK_OVERLAP, HYBRID_ALPHA, TOP_K,
    GLM_MODEL, GLM_PURE_MODEL, TEST_QUERIES
)
from src.chunker.document_chunker import DocumentChunker
from src.retrieval.bm25_retriever import BM25Retriever
from src.retrieval.vector_retriever import VectorRetriever
from src.retrieval.hybrid_retriever import HybridRetriever
from src.generation.glm_generator import GLMGenerator


@dataclass
class ExperimentResult:
    """单条查询的实验结果"""
    query: str
    query_type: str
    semantic_topk: List[Dict] = field(default_factory=list)
    hybrid_topk: List[Dict] = field(default_factory=list)
    pure_glm_answer: str = ""
    rag_answer: str = ""
    semantic_retrieval_ms: float = 0
    hybrid_retrieval_ms: float = 0
    pure_glm_ms: float = 0
    rag_ms: float = 0


class RAGExperiment:
    """RAG 对比实验编排器"""

    def __init__(self, api_key: str, kb_dir: str = KNOWLEDGE_BASE_DIR,
                 chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP,
                 alpha: float = HYBRID_ALPHA):
        self.api_key = api_key
        self.kb_dir = kb_dir
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.alpha = alpha

        self.chunker = DocumentChunker(chunk_size=chunk_size, overlap=overlap)
        self.bm25 = BM25Retriever()
        self.vector = VectorRetriever(api_key)
        self.hybrid = HybridRetriever(self.bm25, self.vector, alpha=alpha)
        self.generator = GLMGenerator(api_key)

        self.chunks: List[Dict] = []
        self.results: List[ExperimentResult] = []

    def build_indices(self):
        """构建所有索引（第一阶段）"""  
        print("\n" + "=" * 70)
        print("📚 第一阶段：数据准备与索引构建")
        print("=" * 70)

        # 1. 文档分块
        print("\n--- 5.2.1 文本分块 ---")
        self.chunks = self.chunker.chunk_all(self.kb_dir)
        if not self.chunks:
            print("❌ 没有可用的知识库文档！请先运行 init_knowledge_base.py")
            return False

        # 2. BM25 索引
        print("\n--- 5.2.2 BM25 关键词索引 ---")
        self.bm25.build_index(self.chunks)

        # 3. 向量索引
        print("\n--- 5.2.3 向量语义索引 ---")
        self.vector.build_index(self.chunks)
        print(f"   Embedding 模型: embedding-3")
        print(f"   向量维度: 1024")
        print(f"   距离度量: cosine")
        return True

    def run_single(self, query: str, query_type: str = "",
                   top_k: int = TOP_K) -> ExperimentResult:
        """对单条查询运行完整对比实验"""
        result = ExperimentResult(query=query, query_type=query_type)
        print(f"\n{'─' * 70}")
        print(f"🔍 查询: {query}")
        print(f"   类型: {query_type}")
        print(f"{'─' * 70}")

        # ---- ① 纯语义检索 ----
        print("\n① 纯语义检索 (Vector Only):")
        t0 = time.time()
        result.semantic_topk = self.vector.retrieve(query, k=top_k)
        result.semantic_retrieval_ms = (time.time() - t0) * 1000

        for i, doc in enumerate(result.semantic_topk):
            src = doc.get('metadata', {}).get('source', '?')
            print(f"   #{i+1} [{src}] sim={doc['score']:.4f}")
            print(f"      {doc['content'][:100]}...")

        # ---- ② 混合检索 ----
        print(f"\n② 混合检索 (Semantic {self.alpha:.0%} + Keyword {1-self.alpha:.0%}):")
        t0 = time.time()
        result.hybrid_topk = self.hybrid.retrieve(query, k=top_k)
        result.hybrid_retrieval_ms = (time.time() - t0) * 1000

        for i, doc in enumerate(result.hybrid_topk):
            src = doc.get('metadata', {}).get('source', '?')
            print(f"   #{i+1} [{src}] fusion={doc.get('fusion_score', doc.get('score', 0)):.4f}")
            print(f"      sem={doc.get('semantic_score', 0):.4f} kw={doc.get('keyword_score', 0):.4f}")
            print(f"      {doc['content'][:100]}...")

        # ---- ③ 纯 GLM（无知识库） ----
        print(f"\n③ 纯 GLM ({GLM_PURE_MODEL}) 回答 (无知识库):")
        t0 = time.time()
        result.pure_glm_answer = self.generator.generate_pure(query)
        result.pure_glm_ms = (time.time() - t0) * 1000
        print(f"   {result.pure_glm_answer[:300]}...")

        # ---- ④ GLM + RAG（知识增强） ----
        print(f"\n④ GLM + RAG ({GLM_MODEL}) 回答 (混合检索上下文):")
        t0 = time.time()
        result.rag_answer = self.generator.generate_with_context(query, result.hybrid_topk)
        result.rag_ms = (time.time() - t0) * 1000
        print(f"   {result.rag_answer[:300]}...")

        print(f"\n⏱ 耗时: 语义检索{result.semantic_retrieval_ms:.0f}ms | "
              f"混合检索{result.hybrid_retrieval_ms:.0f}ms | "
              f"纯GLM {result.pure_glm_ms:.0f}ms | "
              f"RAG {result.rag_ms:.0f}ms")

        return result

    def run_all(self, top_k: int = TOP_K):
        """运行所有测试查询（完整实验）"""
        if not self.chunks:
            ok = self.build_indices()
            if not ok:
                return

        print("\n" + "=" * 70)
        print("🧪 第二阶段：对比实验")
        print("=" * 70)

        for tq in TEST_QUERIES:
            result = self.run_single(tq["query"], tq["type"], top_k=top_k)
            self.results.append(result)

        self.print_summary(top_k=top_k)

    def print_summary(self, top_k: int = TOP_K):
        """打印实验总结报告"""
        print("\n\n" + "=" * 70)
        print("📊 实验总结报告")
        print("=" * 70)

        for i, r in enumerate(self.results):
            print(f"\n{'━' * 70}")
            print(f"实验 #{i+1}: {r.query}")
            print(f"{'━' * 70}")

            # 检索结果对比表
            print(f"\n【检索结果对比 (Top-{top_k})】")
            print(f"{'排名':<6} {'纯语义检索':<35} {'相似度':<10} │ {'混合检索':<35} {'融合分':<10}")
            print(f"{'─' * 6} {'─' * 35} {'─' * 10} ┼ {'─' * 35} {'─' * 10}")
            for j in range(top_k):
                sem_src = r.semantic_topk[j]['metadata'].get('source', '?') if j < len(r.semantic_topk) else ''
                sem_score = r.semantic_topk[j]['score'] if j < len(r.semantic_topk) else 0
                hyb_src = r.hybrid_topk[j]['metadata'].get('source', '?') if j < len(r.hybrid_topk) else ''
                hyb_score = r.hybrid_topk[j].get('fusion_score', 0) if j < len(r.hybrid_topk) else 0
                print(f"{j+1:<6} {sem_src:<35} {sem_score:<10.4f} │ {hyb_src:<35} {hyb_score:<10.4f}")

            # 生成结果对比
            print(f"\n【生成结果对比】")
            print(f"\n▶ 纯 GLM ({GLM_PURE_MODEL}) — 无知识库:")
            print(f"   {r.pure_glm_answer}")
            print(f"\n▶ GLM + RAG ({GLM_MODEL}) — 混合检索增强:")
            print(f"   {r.rag_answer}")

            # 对比分析
            print(f"\n【对比分析】")
            pure_len = len(r.pure_glm_answer)
            rag_len = len(r.rag_answer)

            has_rag_specific = any(kw in r.rag_answer for kw in
                                   ['肉丸', '巨鹿', 'Deerclops', '威尔逊', '饱食度',
                                    '保暖石', '冬帽', '配方', '参考'])
            pure_failed = pure_len < 10
            if pure_failed:
                print(f"   ⚠️ 纯GLM返回空/失败 → RAG有效缓解了模型调用不稳定问题")
            print(f"   • 纯GLM回答长度: {pure_len} 字 | RAG回答长度: {rag_len} 字")
            print(f"   • RAG回答是否包含知识库细节: {'✅ 是' if has_rag_specific else '⚠️ 未检测到'}")

            # 检索重排序分析
            sem_ranks = {}
            for rank, d in enumerate(r.semantic_topk):
                cid = d.get('chunk_id', d.get('metadata', {}).get('source', str(rank)))
                sem_ranks[cid] = rank + 1
            hyb_ranks = {}
            for rank, d in enumerate(r.hybrid_topk):
                cid = d.get('chunk_id', d.get('metadata', {}).get('source', str(rank)))
                hyb_ranks[cid] = rank + 1

            reordered = []
            for cid in set(list(sem_ranks.keys()) + list(hyb_ranks.keys())):
                sr = sem_ranks.get(cid, '—')
                hr = hyb_ranks.get(cid, '—')
                if sr != hr:
                    src = cid if '/' not in cid else cid.split('/')[-1][:30]
                    reordered.append((src, sr, hr))

            if reordered:
                print(f"   • 混合检索重排序效果:")
                for src, sr, hr in sorted(reordered,
                    key=lambda x: (0 if x[1] == '—' else 1,
                                   x[1] if isinstance(x[1], int) else 99)):
                    if sr == '—':
                        print(f"     🆕 {src}: 仅混合检索命中 (排名#{hr})")
                    elif hr == '—':
                        print(f"     ⬇ {src}: 混合检索中掉出Top-{top_k}")
                    else:
                        arrow = '⬆' if hr < sr else '⬇' if hr > sr else '='
                        print(f"     {arrow} {src}: 语义#{sr} → 混合#{hr}")

            # 检索互补性分析
            sem_sources = {d.get('metadata', {}).get('source', '') for d in r.semantic_topk}
            hyb_sources = {d.get('metadata', {}).get('source', '') for d in r.hybrid_topk}
            only_hyb = hyb_sources - sem_sources
            only_sem = sem_sources - hyb_sources
            print(f"   • 仅语义检索命中: {only_sem if only_sem else '无'}")
            print(f"   • 仅混合检索命中: {only_hyb if only_hyb else '无'}")
            if only_hyb:
                print(f"     → 混合检索通过关键词匹配补充了新来源！")
