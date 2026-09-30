# -*- coding: utf-8 -*-
"""
================================================================================
RAG 实验全局配置
================================================================================
"""

# ---- 文本分块策略 ----
CHUNK_SIZE = 200        # 每个 chunk 的最大字符数
CHUNK_OVERLAP = 50      # 相邻 chunk 的重叠字符数

# ---- Embedding 模型 ----
EMBEDDING_MODEL = "embedding-3"
EMBEDDING_DIM = 1024

# ---- 混合检索融合参数 ----
# score = α × semantic + (1-α) × keyword
HYBRID_ALPHA = 0.7      # 语义权重 70%，关键词权重 30%

# ---- 检索参数 ----
TOP_K = 3

#GLM 模型 
GLM_MODEL = "glm-4-flash"   # 用于 RAG（快速）
GLM_PURE_MODEL = "glm-4-flash"    # 用于纯模型对比

# API 配置 
import os
ZHIPU_API_KEY = os.getenv("ZHIPU_API_KEY", "your-key-here")
ZHIPU_BASE_URL = "https://open.bigmodel.cn/api/paas/v4/"

# ---- 知识库路径 ----
import sys
from pathlib import Path
_THIS_DIR = Path(__file__).resolve().parent.parent
KNOWLEDGE_BASE_DIR = str(_THIS_DIR / "data" / "knowledge_base")
# 如果 data/knowledge_base 为空，回退到项目根目录的 knowledge_base
_ROOT_DIR = _THIS_DIR.parent
if not Path(KNOWLEDGE_BASE_DIR).exists() or not list(Path(KNOWLEDGE_BASE_DIR).glob("*.md")):
    KNOWLEDGE_BASE_DIR = str(_ROOT_DIR / "knowledge_base")

# ---- 测试查询 ----
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
