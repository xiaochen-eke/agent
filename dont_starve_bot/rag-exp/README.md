# RAG 技术实验 —— 饥荒游戏知识库检索增强生成

## 实验目的
1. 掌握 RAG 技术的基本原理与实现流程
2. 评估不同检索策略对生成结果准确性的影响
3. 探索多模型协作在知识密集型任务中的应用潜力

## 实验原理
RAG（Retrieval-Augmented Generation）结合信息检索与文本生成。用户问题 → 向量数据库/BM25检索 → 混合排序(α=0.7) → GLM生成答案，有效缓解大模型"幻觉"问题。

## 项目结构

```
rag_experiment/
├── README.md                          # 项目说明
├── requirements.txt                   # Python 依赖
├── config/
│   └── settings.py                    # 全局配置（chunk_size, overlap, α, Top-K等）
├── data/
│   └── knowledge_base/                # 知识库文档（.md格式）
│       ├── game_basics.md             # 饥荒基础知识
│       ├── survival_guide.md          # 高级生存指南
│       ├── advanced_tactics.md        # 高级战术与优化
│       ├── recipe_database.md         # 完整配方数据库
│       └── seasonal_guide.md          # 四季完整攻略
├── src/
│   ├── __init__.py
│   ├── chunker/
│   │   └── document_chunker.py        # 5.2 文档分块器（Markdown感知分块）
│   ├── retrieval/
│   │   ├── bm25_retriever.py          # 5.2 BM25关键词检索器
│   │   ├── vector_retriever.py        # 5.2 向量语义检索器（ChromaDB + Embedding）
│   │   └── hybrid_retriever.py        # 5.3 混合检索器（语义70% + 关键词30%）
│   ├── generation/
│   │   └── glm_generator.py           # 5.3 GLM生成器（纯模型 / RAG增强）
│   └── experiment/
│       ├── runner.py                  # 实验编排器（主控）
│       └── metrics.py                 # 评测指标计算
├── notebooks/
│   └── experiment_report.ipynb        # 实验报告Notebook（含运行截图）
├── results/
│   └── experiment_output.txt          # 实验输出日志
└── main.py                            # 入口：一键运行完整实验
```

## 核心配置参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| CHUNK_SIZE | 200 | 文本分块最大字符数 |
| CHUNK_OVERLAP | 50 | 相邻chunk重叠字符数 |
| EMBEDDING_MODEL | embedding-3 | GLM Embedding模型 |
| EMBEDDING_DIM | 1024 | 向量维度 |
| HYBRID_ALPHA | 0.7 | 混合检索语义权重（关键词=0.3） |
| TOP_K | 3 | 检索返回Top-K文档 |
| GLM_MODEL | glm-4-flash | RAG生成模型 |
| GLM_PURE_MODEL | glm-5 | 纯模型对比（无知识库） |

## 混合检索融合公式

```
score_final = α × score_semantic + (1-α) × score_keyword
其中 α = 0.7（语义70%，关键词30%）
```

融合流程：
1. 分别调用 BM25 和 Vector 检索，各取 Top-K×2 候选
2. 分数归一化到 [0, 1]
3. 加权融合: final_score = α × vec_norm + (1-α) × keyword_norm
4. 去重: 同一 chunk_id 取最高融合分
5. 排序返回 Top-K

## 实验对比维度

| 对比项 | 方案A | 方案B |
|--------|-------|-------|
| 检索策略 | 纯语义检索 (Vector Only) | 混合检索 (Semantic 70% + Keyword 30%) |
| 生成方式 | 纯GLM（无知识库） | GLM + RAG（知识增强） |

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 初始化知识库
python ../backend/init_knowledge_base.py

# 运行完整实验
python main.py

# 自定义参数
python main.py --chunk-size 300 --overlap 80 --alpha 0.6 --top-k 5
```
