# -*- coding: utf-8 -*-
"""
向量语义检索器
==============
- 基于 ChromaDB + Embedding 的向量语义检索
- 使用 GLM embedding-3 模型（1024 维）
- ChromaDB 使用 cosine 距离度量
"""

import sys
from typing import List, Dict

from openai import OpenAI

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

try:
    import chromadb
    from chromadb.config import Settings
    HAS_CHROMADB = True
except ImportError:
    HAS_CHROMADB = False

from config.settings import (
    EMBEDDING_MODEL, EMBEDDING_DIM, TOP_K, ZHIPU_BASE_URL
)


class VectorRetriever:

    def __init__(self, api_key: str):
        self.api_key = api_key
        _timeout = httpx.Timeout(30.0, connect=10.0) if HAS_HTTPX else 30.0
        self.client = OpenAI(
            api_key=api_key,
            base_url=ZHIPU_BASE_URL,
            timeout=_timeout,
            max_retries=0,
        )
        self.chunks: List[Dict] = []
        self.collection = None

    def _embed(self, texts: List[str]) -> List[List[float]]:
        """批量向量化"""
        all_embeddings = []
        batch_size = 16
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            try:
                response = self.client.embeddings.create(
                    model=EMBEDDING_MODEL,
                    input=batch,
                    timeout=30.0,
                )
                all_embeddings.extend([item.embedding for item in response.data])
            except Exception as e:
                print(f"⚠️ Embedding 调用失败 ({e})，使用零向量")
                all_embeddings.extend([[0.0] * EMBEDDING_DIM for _ in batch])
        return all_embeddings

    def _embed_single(self, text: str) -> List[float]:
        """单条向量化"""
        try:
            response = self.client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=[text],
                timeout=15.0,
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"⚠️ Embedding 调用失败 ({e})")
            return [0.0] * EMBEDDING_DIM

    def build_index(self, chunks: List[Dict]):
        """构建向量索引（使用 ChromaDB）"""
        self.chunks = chunks

        if not HAS_CHROMADB:
            print("⚠️ ChromaDB 不可用")
            return

        self.client_chroma = chromadb.Client(Settings(anonymized_telemetry=False))
        try:
            self.collection = self.client_chroma.create_collection(
                name="rag_experiment",
                metadata={"hnsw:space": "cosine"}
            )
        except Exception:
            self.client_chroma.delete_collection("rag_experiment")
            self.collection = self.client_chroma.create_collection(
                name="rag_experiment",
                metadata={"hnsw:space": "cosine"}
            )

        print(f"🧮 正在向量化 {len(chunks)} 个chunk (embedding-3, {EMBEDDING_DIM}维)...")
        contents = [c['content'][:1000] for c in chunks]  # 截断长文本
        embeddings = self._embed(contents)

        batch_size = 100
        total = 0
        for i in range(0, len(chunks), batch_size):
            batch_chunks = chunks[i:i + batch_size]
            batch_embs = embeddings[i:i + batch_size]
            self.collection.add(
                ids=[c['chunk_id'] for c in batch_chunks],
                embeddings=batch_embs,
                documents=[c['content'][:500] for c in batch_chunks],
                metadatas=[c['metadata'] for c in batch_chunks],
            )
            total += len(batch_chunks)
            print(f"   🚀 已入库 {total}/{len(chunks)} chunks", end='\r')
        print(f"\n✅ 向量索引构建完成: {self.collection.count()} 个向量")

    def retrieve(self, query: str, k: int = TOP_K) -> List[Dict]:
        """语义检索"""
        if self.collection is None or self.collection.count() == 0:
            return []

        query_emb = self._embed_single(query)
        try:
            results = self.collection.query(
                query_embeddings=[query_emb],
                n_results=k,
            )
        except Exception as e:
            print(f"⚠️ 向量检索失败: {e}")
            return []

        documents = []
        if results.get('documents'):
            for i, doc in enumerate(results['documents'][0]):
                dist = results['distances'][0][i] if results.get('distances') else 1.0
                sim = max(0.0, 1.0 - dist)
                documents.append({
                    'content': doc,
                    'metadata': results['metadatas'][0][i] if results.get('metadatas') else {},
                    'score': round(sim, 4),
                    'chunk_id': results['ids'][0][i] if results.get('ids') else '',
                })
        return documents
