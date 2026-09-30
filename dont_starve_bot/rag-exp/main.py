#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
RAG 技术实验 —— 饥荒游戏知识库检索增强生成
================================================================================

实验目的：
    1. 掌握 RAG 技术的基本原理与实现流程
    2. 评估不同检索策略对生成结果准确性的影响
    3. 探索多模型协作在知识密集型任务中的应用潜力

实验原理：
    用户问题 → 向量数据库/BM25检索 → 混合排序(α=0.7) → GLM生成答案

对比维度：
    ① 纯语义检索 vs 混合检索（语义70%+关键词30%）Top-K 对比
    ② 纯GLM（无知识库） vs GLM+RAG（知识增强）生成结果对比

用法:
    python main.py
    python main.py --no-build          # 跳过索引构建
    python main.py --chunk-size 300 --overlap 80 --alpha 0.6 --top-k 5
================================================================================
"""

import os
import sys
import argparse

# 修复 Windows 控制台编码
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# 绕过代理
os.environ.setdefault('no_proxy', '*')
os.environ.setdefault('NO_PROXY', '*')

# ---- 加载 .env ----
def _load_dotenv():
    for search_dir in [os.path.dirname(os.path.abspath(__file__)),
                       os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'backend')]:
        env_path = os.path.join(search_dir, '.env')
        if os.path.exists(env_path):
            with open(env_path, encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#') or '=' not in line:
                        continue
                    k, v = line.split('=', 1)
                    k, v = k.strip(), v.strip().strip('"').strip("'")
                    if k and k not in os.environ:
                        os.environ[k] = v
            break

_load_dotenv()
ZHIPU_API_KEY = os.getenv("ZHIPU_API_KEY", "your-key-here")

from config.settings import (
    CHUNK_SIZE, CHUNK_OVERLAP, HYBRID_ALPHA, TOP_K, KNOWLEDGE_BASE_DIR
)
from src.experiment.runner import RAGExperiment


def print_header():
    print("""
╔══════════════════════════════════════════════════════════════════════╗
║        RAG 技术实验 —— 饥荒游戏知识库检索增强生成                     ║
║                                                                      ║
║  实验原理：                                                           ║
║    用户问题 → 向量数据库/BM25检索 → 混合排序(α=0.7) → GLM生成答案    ║
║                                                                      ║
║  对比维度：                                                           ║
║    ① 纯语义检索 vs 混合检索（语义70%+关键词30%）Top-K 对比           ║
║    ② 纯GLM（无知识库） vs GLM+RAG（知识增强）生成结果对比             ║
╚══════════════════════════════════════════════════════════════════════╝
""")


def check_dependencies():
    """检查依赖"""
    issues = []
    try:
        import jieba
    except ImportError:
        issues.append("jieba")
    try:
        from rank_bm25 import BM25Okapi
    except ImportError:
        issues.append("rank-bm25")
    try:
        import chromadb
    except ImportError:
        issues.append("chromadb")
    if issues:
        print("⚠️ 缺少依赖: " + ", ".join(issues))
        print(f"   pip install {' '.join(issues)}")
        print()
        return False
    return True


def main():
    parser = argparse.ArgumentParser(description="RAG 技术对比实验")
    parser.add_argument("--no-build", action="store_true",
                        help="跳过索引构建")
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

    # 创建实验
    experiment = RAGExperiment(
        api_key=ZHIPU_API_KEY,
        kb_dir=KNOWLEDGE_BASE_DIR,
        chunk_size=args.chunk_size,
        overlap=args.overlap,
        alpha=args.alpha,
    )

    # 运行实验
    experiment.run_all(top_k=args.top_k)

    print("\n" + "=" * 70)
    print("✅ 实验完成！")
    print("=" * 70)
    print("\n💡 提示: 以上输出可直接截图作为实验报告的「实验结果与分析」部分。")


if __name__ == '__main__':
    main()
