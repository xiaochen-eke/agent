# -*- coding: utf-8 -*-
"""
BM25 关键词检索器
==================
- 使用 jieba 分词
- 使用 rank_bm25 的 BM25Okapi 算法
- 返回归一化后的分数 (0~1)
"""

import re
from typing import List, Dict, Optional

try:
    import jieba
    HAS_JIEBA = True
except ImportError:
    HAS_JIEBA = False

try:
    from rank_bm25 import BM25Okapi
    HAS_BM25 = True
except ImportError:
    HAS_BM25 = False

from config.settings import TOP_K


class BM25Retriever:

    def __init__(self):
        self.chunks: List[Dict] = []
        self.tokenized_corpus: List[List[str]] = []
        self.bm25: Optional[BM25Okapi] = None

    def _tokenize(self, text: str) -> List[str]:
        """中文分词"""
        if HAS_JIEBA:
            clean = re.sub(r'[^一-鿿\w]', ' ', text)
            return [w for w in jieba.cut(clean) if w.strip()]
        else:
            return list(text)

    def build_index(self, chunks: List[Dict]):
        """构建 BM25 索引"""
        self.chunks = chunks
        self.tokenized_corpus = [self._tokenize(c['content']) for c in chunks]
        if HAS_BM25 and self.tokenized_corpus:
            self.bm25 = BM25Okapi(self.tokenized_corpus)
            print(f"🔤 BM25 索引已构建: {len(self.tokenized_corpus)} 个文档")
        else:
            print(f"⚠️ BM25Okapi 不可用，将使用简单词汇匹配")
            self.bm25 = None

    def retrieve(self, query: str, k: int = TOP_K) -> List[Dict]:
        """
        BM25 关键词检索
        返回: [{'chunk': dict, 'score': float}, ...]
        """
        if not self.chunks:
            return []

        tokens = self._tokenize(query)

        if self.bm25 is not None:
            scores = self.bm25.get_scores(tokens)
            max_score = max(scores) if max(scores) > 0 else 1.0
            normalized = [s / max_score for s in scores]
        else:
            normalized = []
            for chunk in self.chunks:
                content = chunk['content'].lower()
                matches = sum(1 for t in tokens if t in content)
                normalized.append(matches / max(len(tokens), 1))

        ranked = sorted(
            enumerate(normalized),
            key=lambda x: x[1],
            reverse=True
        )[:k]

        results = []
        for idx, score in ranked:
            if score > 0:
                results.append({
                    'chunk': self.chunks[idx],
                    'score': round(score, 4),
                })
        return results
