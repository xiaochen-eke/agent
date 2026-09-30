# Agent 全栈项目集合

个人 AI / 全栈项目仓库。围绕「大模型应用」这一主线，从**最简 Agent** 一路做到 **游戏内闭环 Co-pilot**，覆盖：多模态工具调用、三种 Agent 编排范式对比、动态博客全栈、以及一个接进真实游戏的饥荒 AI 助手（RAG + 微调 + 多智能体）。

> 四个子系统彼此独立可跑，也可串成一条完整的技术成长路线。

## 总览

| 目录 | 是什么 | 端口 | 技术栈 | 一句话亮点 |
|------|--------|------|--------|-----------|
| [`Agent/`](#1-agent--多模态智能体) | 多模态智能体（联网搜索 / 图片识别 / 角色人格） | — | Python + requests + 智谱 GLM | 从 0 手写 tool-calling，自带「小 A」人设 |
| [`agent_versions/`](#2-agent_versions--三种-agent-编排范式对比) | 同一任务用**原生 / LangGraph / Dify** 三种编排实现 + 全栈控制台 | 5100 / 5099 | Flask + 原生 JS + LangGraph + Dify | 面试讲「为什么选平台 / 为什么手写」的现成案例 |
| [`blog/`](#3-blog--个人动态博客) | 个人动态博客 | 5200 | Flask + Jinja + SQLite | 标签 / 全文搜索 / 评论 / 后台，赛博终端风 |
| [`dont_starve_bot/`](#4-dont_starve_bot--饥荒游戏-ai-助手) | 饥荒游戏 AI 助手（攻略问答 + 游戏内实时决策） | 5000 / 5001 / 5002 | Flask + React + RAG + LoRA + Dify | RAG / 微调 / 多智能体 / 游戏闭环一应俱全 |

## 它们怎么串起来

```
Agent/                ← 最基础：一个会调工具、带人设的智能体
   │  （工具调用、联网搜索、图片识别）
   ▼
agent_versions/       ← 进阶：同一功能，三种编排范式对比 + 前端控制台
   │  （native / langgraph / dify  →  showcase 统一 /api/chat）
   │
   ├── dify 卡片接的是 ↓
   ▼
dont_starve_bot/      ← 落地：把 agent 接进真实游戏，RAG + 微调 + 多智能体闭环
   ├── backend     攻略问答（RAG + 领域微调）
   ├── live_agent  游戏内实时决策（原生 / Dify 两套大脑 + GLM 动作决策）
   └── rag-exp     RAG 检索策略实验（BM25 vs 向量 vs 混合）
```

## 1. `Agent/` — 多模态智能体

从零手写的最小可用 Agent，学习/演示「工具调用」这条主线的起点。

| 文件 | 作用 |
|------|------|
| `search_agent.py` | 联网搜索 Agent：`web_search` / `search_files` / `search_content` / `search_images` / `read_file` 等工具 |
| `image_agent.py` · `image_search_agent.py` | 图片识别与「以图搜图」 |
| `extract_cifar10.py` · `imagenet_classes.txt` | 图像分类（CIFAR-10 / ImageNet 1000 类） |
| `agent_web.py` · `agent_web_server.py` · `agent_web.html` | Web 版 Agent |
| `persona_*.md` | 角色人格（「小 A」电脑管家等），演示人设注入 |
| `step01.py` … `step13.py` | 循序渐进的构建步骤（从调 API 到完整 Agent） |
| `Agent.md` · `Agent_v2.md` | 设计说明文档 |

```bash
cd Agent
pip install requests
python search_agent.py        # 交互式联网搜索
```

## 2. `agent_versions/` — 三种 Agent 编排范式对比

用**同一个极简任务**（饥荒物品问答：查配方 / 查属性 / 无关问题），分别用三种编排方式实现，直观对比「手写 / 代码建图 / 可视化平台」三条路线。

```
用户问："草帽怎么合成？"
   ↓ ① 意图识别（LLM）→ {"intent": "recipe"|"stats"|"other", "item": "草帽"}
   ↓ ② 条件分支：recipe/stats → 查物品库 lookup() → ③ 汇总回答；other → 直接回答
```

| 维度 | `native/` 原生版 | `langgraph/` LangGraph 版 | `dify/` Dify 版 |
|------|------------------|---------------------------|-----------------|
| 编排方式 | 手写 `if/elif` 控制流 | `StateGraph` 图（节点 + 边） | 可视化工作流（拖节点） |
| LLM 接入 | `requests` 直调智谱 | `ChatOpenAI`（langchain-openai） | 平台模型供应商 `glm-4-flash` |
| 条件分支 | `if intent == "other"` | `add_conditional_edges` | `if-else` 节点 |
| 工具调用 | 直接 `import lookup()` | 节点函数内调 `lookup()` | HTTP 节点调 `items_server:5099` |
| 依赖 | 仅 `requests` | `langgraph` + `langchain` | Docker + Dify 平台 |

- `shared/` 三版共用的物品库（`items_db.py` 数据 + `items_server.py` Flask `:5099`）
- `showcase/` 全栈展示后端：统一 `POST /api/chat` 路由三引擎，前端三卡片 + 「三版并排对比」
- showcase 的 **Dify 卡片接的是真实游戏大脑**（`/api/brain` + `/api/brain/state`），指向 `dont_starve_bot/live_agent/dify_brain.py`

```bash
cd agent_versions/native && python agent.py "草帽怎么合成？"     # 原生版
cd agent_versions/langgraph && pip install -r requirements.txt && python agent.py "草帽怎么合成？"
cd agent_versions/showcase && pip install -r requirements.txt && python app.py   # http://localhost:5100
# Dify 版见 agent_versions/dify/配置指南.md
```

## 3. `blog/` — 个人动态博客

服务端渲染的轻量博客，赛博终端主题（霓虹绿 / 等宽 / 扫描线 / CRT / 闪烁光标）。

- **内容**：Markdown 渲染、标签、分类、全文搜索、归档、关于页、上一篇 / 下一篇、404
- **互动**：评论系统（默认待审核），honeypot + IP 限流反垃圾
- **后台**：`/admin` 登录后发文、编辑、发布/隐藏、审核评论
- 数据存 SQLite，零外部依赖即可跑

```bash
cd blog
cp .env.example .env        # 改 ADMIN_USER / ADMIN_PASS / SITE_TITLE / SITE_SUBTITLE
pip install -r requirements.txt
python app.py               # http://localhost:5200
```

## 4. `dont_starve_bot/` — 饥荒游戏 AI 助手

四个子模块，构成「攻略问答 + 游戏内实时决策 + 实验」三层：

| 子模块 | 端口 | 说明 |
|--------|------|------|
| `backend/` | 5000 | 攻略问答：RAG（ChromaDB）+ 领域微调（意图识别 / 实体提取 / 响应增强） |
| `frontend/` | — | React 前端（聊天页 + Agent 页） |
| `live_agent/` | 5002 / 5001 | 游戏内实时决策：采集 → 分析 → 决策 → 回灌游戏 |
| `rag-exp/` | — | RAG 检索策略实验（BM25 / 向量 / 混合检索） |

### backend — 攻略问答

```
用户查询 → 意图识别 → RAG 检索（ChromaDB）→ 提示词优化 → GLM 生成 → 响应增强 → SQLite 存历史
```

```bash
cd dont_starve_bot/backend
python init_knowledge_base.py    # 生成知识库文档
pip install -r requirements.txt
python app.py                     # http://localhost:5000  (POST /api/chat)
```

### live_agent — 游戏内闭环 Co-pilot

采集游戏状态 → 触发大脑 → 给出建议 / 半自动执行动作（吃 / 装备 / 攻击 / 采集 / 合成 / 砍树等），一套采集层上挂了**两套大脑**：

```
[DST 游戏] → dst_mod 采集(每2s) → bridge.py 桥接 → state_api.py :5002 状态中枢
                    ├── 原生版 native_agent.py：规划→检索→执行→反思（纯 Python 多智能体）
                    └── Dify 版 dify_brain.py：Dify 链规划 + GLM 动作决策（function-calling）
```

两段式分工（Dify 版）：**段1** Dify 工作流（DeepSeek）「规划→检索→反思」输出建议；**段2** GLM-4-flash 用 function-calling 把建议映射成可执行动作 `{verb, prefab}`，不确定时主动 `search_db` / `web_search` / `read_webpage`。

> 启动步骤见 [`dont_starve_bot/live_agent/README.md`](dont_starve_bot/live_agent/README.md)，演示 runbook 见 `DEMO.md`。

### rag-exp — RAG 检索实验

对比纯语义检索 vs **混合检索**（语义 70% + 关键词 30%，α=0.7），评估不同检索策略对生成准确性的影响。

```bash
cd dont_starve_bot/rag-exp
pip install -r requirements.txt
python main.py                 # 一键跑完整实验
```

## 端口速查

| 端口 | 服务 | 位置 |
|------|------|------|
| 5000 | 饥荒攻略问答后端 | `dont_starve_bot/backend/app.py` |
| 5001 | 游戏百科检索 API | `dont_starve_bot/live_agent/game_data_api.py` |
| 5002 | 实时状态中枢 / 面板 | `dont_starve_bot/live_agent/state_api.py` |
| 5099 | 物品库查询服务 | `agent_versions/shared/items_server.py` |
| 5100 | Agent 控制台 | `agent_versions/showcase/app.py` |
| 5200 | 个人博客 | `blog/app.py` |

## 面试 / 技术亮点

- **「同一功能，三种编排」**：native / LangGraph / Dify 三版语义等价，可讲清各自取舍。
- **工具调用是真工具**：检索先改写搜索词、再 HTTP 查库，不是把知识塞进 prompt。
- **多智能体职责拆分**：规划（做什么）/ 检索（查什么）/ 执行（怎么做）/ 反思（对不对）——职责单一、可独立测试、可换模型。
- **反思 = 结果校验**：对执行结果做可行性校验，抑制幻觉、输出带置信度。
- **RAG 混合检索**：`α·语义 + (1-α)·关键词`，有量化实验对比。
- **工程细节**：文件桥接、事件驱动、阈值去噪、静态/实时分离。

## 安全说明

- 所有密钥（`.env`）、数据库（`*.db` / `chroma_db/`）、模型权重（`lora_model/`）、前端依赖（`node_modules/`）均已 `.gitignore` 排除，不会进入版本库。
- 配置模板见各目录 `.env.example`，复制为 `.env` 后填入你自己的密钥。
- 博客后台默认账密仅为本地演示用，**部署到公网前务必修改**。

## License

个人学习 / 演示项目，代码仅供参考。
