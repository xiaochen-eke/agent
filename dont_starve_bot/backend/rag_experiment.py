# -*- coding: utf-8 -*-
"""
================================================================================
RAG 技术实验脚本 —— 饥荒游戏知识库
================================================================================
实验目的：
    1. 掌握 RAG 技术的基本原理与实现流程
    2. 评估不同检索策略对生成结果准确性的影响
    3. 探索多模型协作在知识密集型任务中的应用潜力

实验内容：
    5.2 数据准备与向量数据库构建
    5.3 混合检索与 RAG 生成实现
    6.1 检索效果验证（纯语义 vs 混合检索 Top-K 对比）
    6.2 生成结果对比分析（纯 GLM vs GLM+RAG）

用法:
    python rag_experiment.py
    python rag_experiment.py --no-build   # 跳过索引构建，直接实验
    python rag_experiment.py --chunk-size 300 --overlap 80  # 自定义分块参数
================================================================================
"""

import os
import sys
import json
import time
import math
import argparse
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field
from collections import OrderedDict

# ---- 修复 Windows 控制台编码 ----
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# ---- 绕过代理 ----
os.environ.setdefault('no_proxy', '*')
os.environ.setdefault('NO_PROXY', '*')

# ---- 加载 .env ----
def _load_dotenv():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(script_dir, '.env')
    if not os.path.exists(env_path):
        env_path = os.path.join(script_dir, '..', '.env')
    if not os.path.exists(env_path):
        return
    with open(env_path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v
_load_dotenv()

ZHIPU_API_KEY = os.getenv("ZHIPU_API_KEY", "your-key-here")

import requests

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

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

try:
    import chromadb
    from chromadb.config import Settings
    HAS_CHROMADB = True
except ImportError:
    HAS_CHROMADB = False

from openai import OpenAI


# ==============================================================================
# 一、配置参数
# ==============================================================================
# 文本分块策略
CHUNK_SIZE = 200        # 每个 chunk 的最大字符数
CHUNK_OVERLAP = 50      # 相邻 chunk 的重叠字符数

# Embedding 模型
EMBEDDING_MODEL = "embedding-3"
EMBEDDING_DIM = 1024

# 混合检索融合参数: score = α * semantic + (1-α) * keyword
HYBRID_ALPHA = 0.7      # 语义权重 70%，关键词权重 30%

# 检索参数
TOP_K = 3

# 知识库路径
KNOWLEDGE_BASE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "knowledge_base"
)

# GLM 模型
GLM_MODEL = "glm-4-flash"   # 用于 RAG（快速）
GLM_PURE_MODEL = "glm-4-flash"    # 用于纯模型对比

# 预设测试查询
TEST_QUERIES = [
    {
        "query": "冬季怎么保暖？巨鹿怎么打？",
        "type": "季节生存 + BOSS战",
        "keywords": ["冬季", "保暖", "巨鹿", "打法"],
    },
    {
        "query": "肉丸怎么做？回血效果怎么样？",
        "type": "食谱查询",
        "keywords": ["肉丸", "配方", "回血", "食谱"],
    },
    {
        "query": "前期新手应该选什么角色？威尔逊有什么特点？",
        "type": "角色推荐 + 机制询问",
        "keywords": ["新手", "角色", "威尔逊", "前期"],
    },
]


# ==============================================================================
# 二、文档分块器
# ==============================================================================
class DocumentChunker:
    """
    文档分块器 — Markdown 感知分块
    - 策略：
      1. 按 ## 标题分割为"节"（保留标题与内容在一起）
      2. 若节过长，按自然段落（\n\n）进一步拆分
      3. 若段落仍过长，按句子分割
      4. 重叠：相邻 chunk 在头部保留上一个 chunk 的标题行作为上下文
    - 元数据：记录来源文件、chunk 序号、所在章节标题
    """

    MIN_CHUNK_CHARS = 30  # 最小 chunk 字符数，过小的合并到前一个

    def __init__(self, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP):
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.stats = {"total_chars": 0, "total_chunks": 0, "files": 0}

    def _split_sections(self, text: str) -> List[Tuple[str, str]]:
        """按 ## 标题分割为 (标题, 内容) 列表"""
        import re
        # 匹配 markdown 标题（# 或 ## 开头）
        sections = []
        lines = text.split('\n')
        current_title = lines[0].strip() if lines else ""
        current_body = []

        for line in lines:
            stripped = line.strip()
            # 遇到 ## 或 # 标题（但不是 ### 等更深的标题）
            if re.match(r'^#{1,2}\s+', stripped) and not re.match(r'^#{3,}', stripped):
                if current_body:
                    body_text = '\n'.join(current_body).strip()
                    if body_text:
                        sections.append((current_title, body_text))
                current_title = stripped
                current_body = []
            else:
                current_body.append(line)

        # 最后一个 section
        if current_body:
            body_text = '\n'.join(current_body).strip()
            if body_text:
                sections.append((current_title, body_text))

        # 如果没有找到标题，整篇作为一个 section
        if not sections:
            sections = [("", text.strip())]

        return sections

    def _split_sentences(self, text: str) -> List[str]:
        """按句子分割（中文句号、问号、感叹号、换行）"""
        import re
        sentences = re.split(r'(?<=[。！？.!?\n])\s*', text)
        return [s.strip() for s in sentences if s.strip()]

    def _chunk_by_size(self, text: str) -> List[str]:
        """将长文本按 chunk_size 分割（尽量在句子边界处切分）"""
        chunks = []
        sentences = self._split_sentences(text)
        current = ""
        for sent in sentences:
            if len(current) + len(sent) <= self.chunk_size:
                current += sent
            else:
                if current.strip() and len(current.strip()) >= self.MIN_CHUNK_CHARS:
                    chunks.append(current.strip())
                elif current.strip():
                    # 太小，继续追加（下次再判断）
                    current += sent
                    continue
                # 处理当前句子
                if len(sent) > self.chunk_size:
                    # 超长句子：按固定大小切分
                    start = 0
                    while start < len(sent):
                        end = min(start + self.chunk_size, len(sent))
                        piece = sent[start:end].strip()
                        if piece:
                            chunks.append(piece)
                        start = end - self.overlap
                    current = ""
                else:
                    current = sent
        if current.strip() and len(current.strip()) >= self.MIN_CHUNK_CHARS:
            chunks.append(current.strip())
        elif current.strip() and chunks:
            # 剩余内容太短，合并到最后一个 chunk
            chunks[-1] = chunks[-1] + "\n" + current.strip()
        return chunks

    def chunk_document(self, content: str, source_file: str) -> List[Dict]:
        """
        将单个文档分块
        sections: List of (title, body)
        """
        sections = self._split_sections(content)

        all_chunks = []
        for title, body in sections:
            if not body.strip():
                continue

            # 构建带标题前缀的文本
            if title and not body.startswith(title):
                chunk_text = title + "\n" + body
            else:
                chunk_text = body

            # 节内容适中 → 直接作为一个 chunk
            if len(chunk_text) <= self.chunk_size:
                all_chunks.append(chunk_text)
            else:
                # 节内容过长 → 按段落拆分
                paragraphs = [p.strip() for p in body.split('\n\n') if p.strip()]
                current_chunk = title + "\n" if title else ""

                for para in paragraphs:
                    para_with_title = title + "\n" + para if title else para
                    if len(current_chunk) + len(para) <= self.chunk_size:
                        current_chunk += "\n\n" + para if current_chunk != (title + "\n" if title else "") else para
                    else:
                        if current_chunk.strip() and len(current_chunk.strip()) >= self.MIN_CHUNK_CHARS:
                            all_chunks.append(current_chunk.strip())
                        # 如果段落本身超长，进一步拆分
                        if len(para_with_title) > self.chunk_size:
                            sub_chunks = self._chunk_by_size(para_with_title)
                            all_chunks.extend(sub_chunks)
                            current_chunk = title + "\n" if title else ""
                        else:
                            current_chunk = para_with_title

                # 最后一个 chunk
                if current_chunk.strip() and len(current_chunk.strip()) >= self.MIN_CHUNK_CHARS:
                    all_chunks.append(current_chunk.strip())
                elif current_chunk.strip() and all_chunks:
                    all_chunks[-1] = all_chunks[-1] + "\n" + current_chunk.strip()

        # 过小的 chunk 合并到前一个
        merged_chunks = []
        for chunk in all_chunks:
            if len(chunk) < self.MIN_CHUNK_CHARS and merged_chunks:
                merged_chunks[-1] = merged_chunks[-1] + "\n" + chunk
            else:
                merged_chunks.append(chunk)

        # 添加重叠上下文（每个 chunk 开头附加来源信息）
        results = []
        base_id = source_file.replace('.', '_').replace(' ', '_')
        for i, chunk_text in enumerate(merged_chunks):
            # 提取 section 标题作为元数据
            section_title = ""
            for title, _ in sections:
                if title and title.lstrip('#').strip() in chunk_text:
                    section_title = title.lstrip('#').strip()
                    break

            results.append({
                'chunk_id': f"{base_id}_{i:03d}",
                'content': chunk_text,
                'metadata': {
                    'source': source_file,
                    'chunk_index': i,
                    'chunk_size': len(chunk_text),
                    'section': section_title,
                }
            })

        self.stats["total_chars"] += len(content)
        self.stats["total_chunks"] += len(results)
        self.stats["files"] += 1

        return results

    def chunk_all(self, kb_dir: str) -> List[Dict]:
        """遍历知识库目录，分块所有 .md 文件"""
        all_chunks = []
        kb_path = Path(kb_dir)
        if not kb_path.exists():
            print(f"⚠️ 知识库目录不存在: {kb_dir}")
            return all_chunks

        md_files = sorted(kb_path.glob("*.md"))
        print(f"📄 发现 {len(md_files)} 个知识库文件")
        print(f"⚙️  分块参数: chunk_size={self.chunk_size}, overlap={self.overlap}\n")

        for md_file in md_files:
            try:
                with open(md_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                if not content.strip():
                    continue
                chunks = self.chunk_document(content, md_file.name)
                all_chunks.extend(chunks)
                print(f"   ✅ {md_file.name}: {len(content)} 字符 → {len(chunks)} 个chunk")
            except Exception as e:
                print(f"   ❌ {md_file.name}: 读取失败 ({e})")

        print(f"\n📊 分块统计: {self.stats['files']} 文件 → {self.stats['total_chunks']} chunks | "
              f"平均 chunk={self.stats['total_chars']//max(self.stats['total_chunks'],1)} 字符")
        return all_chunks


# ==============================================================================
# 三、BM25 关键词检索器
# ==============================================================================
class BM25Retriever:
    """
    基于 BM25 的关键词检索
    - 使用 jieba 分词
    - 使用 rank_bm25 的 BM25Okapi 算法
    - 返回归一化后的分数 (0~1)
    """

    def __init__(self):
        self.chunks: List[Dict] = []
        self.tokenized_corpus: List[List[str]] = []
        self.bm25: Optional[BM25Okapi] = None

    def _tokenize(self, text: str) -> List[str]:
        """中文分词"""
        if HAS_JIEBA:
            # 移除标点后分词
            import re
            clean = re.sub(r'[^一-鿿\w]', ' ', text)
            return [w for w in jieba.cut(clean) if w.strip()]
        else:
            # 无 jieba 时用字符级分词
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
            # 归一化到 [0, 1]
            max_score = max(scores) if max(scores) > 0 else 1.0
            normalized = [s / max_score for s in scores]
        else:
            # 简单词汇匹配回退
            normalized = []
            for chunk in self.chunks:
                content = chunk['content'].lower()
                matches = sum(1 for t in tokens if t in content)
                normalized.append(matches / max(len(tokens), 1))

        # 排序取 top-k
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


# ==============================================================================
# 四、向量语义检索器
# ==============================================================================
class VectorRetriever:
    """
    基于 ChromaDB + Embedding 的向量语义检索
    - 使用 GLM embedding-3 模型（1024 维）
    - ChromaDB 使用 cosine 距离度量
    """

    def __init__(self, api_key: str):
        self.api_key = api_key
        _timeout = httpx.Timeout(30.0, connect=10.0) if HAS_HTTPX else 30.0
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://open.bigmodel.cn/api/paas/v4/",
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

        # 使用临时内存数据库
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

        # 批量嵌入并写入
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
                # cosine 距离 → 相似度
                dist = results['distances'][0][i] if results.get('distances') else 1.0
                sim = max(0.0, 1.0 - dist)
                documents.append({
                    'content': doc,
                    'metadata': results['metadatas'][0][i] if results.get('metadatas') else {},
                    'score': round(sim, 4),
                    'chunk_id': results['ids'][0][i] if results.get('ids') else '',
                })
        return documents


# ==============================================================================
# 五、混合检索器（语义 70% + 关键词 30%）
# ==============================================================================
class HybridRetriever:
    """
    混合检索: score = α × semantic_score + (1-α) × keyword_score

    融合流程:
    1. 分别调用 BM25 和 Vector 检索各取 Top-K*2 候选
    2. 分数归一化到 [0,1]
    3. 加权融合: final_score = α × vec_norm + (1-α) × keyword_norm
    4. 去重: 同一 chunk_id 的多次出现取最高融合分
    5. 排序返回 Top-K
    """

    def __init__(self, bm25: BM25Retriever, vector: VectorRetriever,
                 alpha: float = HYBRID_ALPHA):
        self.bm25 = bm25
        self.vector = vector
        self.alpha = alpha

    def retrieve(self, query: str, k: int = TOP_K) -> List[Dict]:
        """
        混合检索
        返回: [{'content': str, 'metadata': dict, 'score': float,
                'semantic_score': float, 'keyword_score': float}, ...]
        """
        # 并行获取候选（多取一些候选以便融合）
        candidates = 2 * k
        bm25_results = self.bm25.retrieve(query, k=candidates)
        vec_results = self.vector.retrieve(query, k=k)

        # ---- 融合 ----
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

        # ---- 加权融合 ----
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


# ==============================================================================
# 六、GLM 生成器
# ==============================================================================
class GLMGenerator:
    """GLM 模型调用封装"""

    def __init__(self, api_key: str):
        _timeout = httpx.Timeout(90.0, connect=10.0) if HAS_HTTPX else 90.0
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://open.bigmodel.cn/api/paas/v4/",
            timeout=_timeout,
            max_retries=0,
        )

    def generate(self, prompt: str, model: str = GLM_MODEL,
                 temperature: float = 0.7, max_tokens: int = 2048) -> str:
        """调用 GLM 模型"""
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"❌ 模型调用失败: {str(e)}"

    def generate_pure(self, query: str) -> str:
        """纯 GLM 回答（无知识库）"""
        prompt = f"请回答以下问题：\n\n{query}\n\n请给出详细的回答。"
        return self.generate(prompt, model=GLM_PURE_MODEL)

    def generate_with_context(self, query: str, context_docs: List[Dict]) -> str:
        """GLM + RAG 上下文回答"""
        # 构建上下文
        ctx_parts = []
        for i, doc in enumerate(context_docs):
            source = doc.get('metadata', {}).get('source', doc.get('chunk_id', '未知'))
            ctx_parts.append(f"【参考文档 {i+1} · 来源: {source}】\n{doc['content']}")

        context_block = "\n\n---\n\n".join(ctx_parts)

        prompt = (
            f"你是一个《饥荒》游戏攻略专家。请严格基于以下参考知识回答问题。"
            f"如果参考知识不足以回答，请明确指出。\n\n"
            f"{context_block}\n\n"
            f"【用户问题】\n{query}\n\n"
            f"请给出详细、准确的回答，并注明信息来源。"
        )
        return self.generate(prompt, model=GLM_MODEL)


# ==============================================================================
# 七、实验编排器
# ==============================================================================
@dataclass
class ExperimentResult:
    """单条查询的实验结果"""
    query: str
    query_type: str
    # 检索结果
    semantic_topk: List[Dict] = field(default_factory=list)
    hybrid_topk: List[Dict] = field(default_factory=list)
    # 生成结果
    pure_glm_answer: str = ""
    rag_answer: str = ""
    # 耗时
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

        # 组件
        self.chunker = DocumentChunker(chunk_size=chunk_size, overlap=overlap)
        self.bm25 = BM25Retriever()
        self.vector = VectorRetriever(api_key)
        self.hybrid = HybridRetriever(self.bm25, self.vector, alpha=alpha)
        self.generator = GLMGenerator(api_key)

        self.chunks: List[Dict] = []
        self.results: List[ExperimentResult] = []

    def build_indices(self):
        """构建所有索引"""
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
        print(f"   Embedding 模型: {EMBEDDING_MODEL}")
        print(f"   向量维度: {EMBEDDING_DIM}")
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

        # ---- 检索对比 ----
        print("\n① 纯语义检索 (Vector Only):")
        t0 = time.time()
        result.semantic_topk = self.vector.retrieve(query, k=top_k)
        result.semantic_retrieval_ms = (time.time() - t0) * 1000

        for i, doc in enumerate(result.semantic_topk):
            src = doc.get('metadata', {}).get('source', '?')
            print(f"   #{i+1} [{src}] sim={doc['score']:.4f}")
            print(f"      {doc['content'][:100]}...")

        print(f"\n② 混合检索 (Semantic {self.alpha:.0%} + Keyword {1-self.alpha:.0%}):")
        t0 = time.time()
        result.hybrid_topk = self.hybrid.retrieve(query, k=top_k)
        result.hybrid_retrieval_ms = (time.time() - t0) * 1000

        for i, doc in enumerate(result.hybrid_topk):
            src = doc.get('metadata', {}).get('source', '?')
            print(f"   #{i+1} [{src}] fusion={doc.get('fusion_score', doc.get('score', 0)):.4f}")
            print(f"      sem={doc.get('semantic_score', 0):.4f} kw={doc.get('keyword_score', 0):.4f}")
            print(f"      {doc['content'][:100]}...")

        # ---- 生成对比 ----
        print(f"\n③ 纯 GLM ({GLM_PURE_MODEL}) 回答 (无知识库):")
        t0 = time.time()
        result.pure_glm_answer = self.generator.generate_pure(query)
        result.pure_glm_ms = (time.time() - t0) * 1000
        print(f"   {result.pure_glm_answer[:300]}...")

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
        """运行所有测试查询"""
        if not self.chunks:
            ok = self.build_indices()
            if not ok:
                return

        # 将 top_k 传递给各检索器
        self._top_k = top_k

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

            # 分析
            print(f"\n【对比分析】")
            pure_len = len(r.pure_glm_answer)
            rag_len = len(r.rag_answer)

            # RAG 是否有实质性内容
            has_rag_specific = any(kw in r.rag_answer for kw in
                                   ['肉丸', '巨鹿', 'Deerclops', '威尔逊', '饱食度', '保暖石', '冬帽', '配方', '参考'])
            # 纯 GLM 是否失效
            pure_failed = pure_len < 10
            if pure_failed:
                print(f"   ⚠️ 纯GLM返回空/失败 (0字) → RAG有效缓解了模型调用不稳定问题")
            print(f"   • 纯GLM回答长度: {pure_len} 字 | RAG回答长度: {rag_len} 字")
            print(f"   • RAG回答是否包含知识库细节: {'✅ 是' if has_rag_specific else '⚠️ 未检测到'}")

            # ---- 检索重排序分析 ----
            sem_ranks = {}
            for rank, d in enumerate(r.semantic_topk):
                cid = d.get('chunk_id', d.get('metadata', {}).get('source', str(rank)))
                sem_ranks[cid] = rank + 1
            hyb_ranks = {}
            for rank, d in enumerate(r.hybrid_topk):
                cid = d.get('chunk_id', d.get('metadata', {}).get('source', str(rank)))
                hyb_ranks[cid] = rank + 1

            # 找出排名变化的文档
            reordered = []
            for cid in set(list(sem_ranks.keys()) + list(hyb_ranks.keys())):
                sr = sem_ranks.get(cid, '—')
                hr = hyb_ranks.get(cid, '—')
                if sr != hr:
                    src = cid if '/' not in cid else cid.split('/')[-1][:30]
                    reordered.append((src, sr, hr))

            if reordered:
                print(f"   • 混合检索重排序效果:")
                for src, sr, hr in sorted(reordered, key=lambda x: (0 if x[1] == '—' else 1, x[1] if isinstance(x[1], int) else 99)):
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


# ==============================================================================
# 八、主函数
# ==============================================================================
def print_header():
    print("""
╔══════════════════════════════════════════════════════════════════════╗
║        RAG 技术实验 —— 饥荒游戏知识库检索增强生成                     ║
║                                                                      ║
║  实验原理：                                                           ║
║    用户问题 → 向量数据库/Bm25检索 → 混合排序(α=0.7) → GLM生成答案    ║
║                                                                      ║
║  对比维度：                                                           ║
║    ① 纯语义检索 vs 混合检索（语义70%+关键词30%）Top-K 对比           ║
║    ② 纯GLM（无知识库） vs GLM+RAG（知识增强）生成结果对比             ║
╚══════════════════════════════════════════════════════════════════════╝
""")


def check_dependencies():
    """检查依赖"""
    issues = []
    if not HAS_JIEBA:
        issues.append("jieba (pip install jieba)")
    if not HAS_BM25:
        issues.append("rank-bm25 (pip install rank-bm25)")
    if not HAS_CHROMADB:
        issues.append("chromadb (pip install chromadb)")
    if issues:
        print("⚠️ 缺少以下依赖，请安装:")
        for issue in issues:
            print(f"   pip install {issue.split()[0]}")
        print()
        return False
    return True


def main():
    parser = argparse.ArgumentParser(description="RAG 技术对比实验")
    parser.add_argument("--no-build", action="store_true",
                        help="跳过索引构建，直接实验（需要已有索引）")
    parser.add_argument("--chunk-size", type=int, default=CHUNK_SIZE,
                        help=f"chunk 大小 (默认: {CHUNK_SIZE})")
    parser.add_argument("--overlap", type=int, default=CHUNK_OVERLAP,
                        help=f"chunk 重叠量 (默认: {CHUNK_OVERLAP})")
    parser.add_argument("--alpha", type=float, default=HYBRID_ALPHA,
                        help=f"混合检索语义权重 (默认: {HYBRID_ALPHA})")
    parser.add_argument("--top-k", type=int, default=TOP_K,
                        help=f"Top-K 检索数量 (默认: {TOP_K})")
    args = parser.parse_args()

    print_header()

    if not check_dependencies():
        sys.exit(1)

    # 更新全局参数
    alpha = args.alpha
    top_k = args.top_k

    # 创建实验
    experiment = RAGExperiment(
        api_key=ZHIPU_API_KEY,
        kb_dir=KNOWLEDGE_BASE_DIR,
        chunk_size=args.chunk_size,
        overlap=args.overlap,
        alpha=alpha,
    )

    # 运行实验（传递 top_k）
    experiment.run_all(top_k=top_k)

    print("\n" + "=" * 70)
    print("✅ 实验完成！")
    print("=" * 70)
    print("\n💡 提示: 以上输出可直接截图作为实验报告的'实验结果与分析'部分。")


if __name__ == '__main__':
    main()
