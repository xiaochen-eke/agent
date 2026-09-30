# 三版本 Agent 对比：饥荒物品顾问（原生 / LangGraph / Dify）

用**同一个极简任务**（饥荒物品问答：查配方 / 查属性 / 无关问题），分别用三种编排方式实现，
直观对比「手写 / 代码建图 / 可视化平台」三条路线的差异。适合面试讲解、选型参考。

## 功能

```
用户问："草帽怎么合成？" / "木甲防御多少？" / "今天天气如何？"
   ↓
① 意图识别（LLM）→ {"intent": "recipe"|"stats"|"other", "item": "草帽"}
   ↓
② 条件分支：
     recipe/stats → 工具查物品库 lookup(item, intent) → ③ 汇总回答（LLM）
     other        → 直接回答（跳过工具）
```

三个对比点：**顺序编排**、**条件分支**、**工具调用**。

## 三版本对照

| 维度 | 原生版 `native/` | LangGraph 版 `langgraph/` | Dify 版 `dify/` |
|---|---|---|---|
| 编排方式 | 手写 Python 控制流（`if/elif`） | `StateGraph` 图（节点 + 边） | 可视化工作流（拖节点） |
| LLM 接入 | `requests` 直调智谱 OpenAI 端点 | `ChatOpenAI`（langchain-openai） | 平台模型供应商 `glm-4-flash` |
| 条件分支 | `if intent == "other"` 显式判断 | `add_conditional_edges` + `route` 函数 | `if-else` 节点 |
| 工具调用 | 直接 `import lookup()` | 节点函数内调 `lookup()` | HTTP 节点调 `items_server:5099` |
| JSON 解析 | `json.loads` | 节点函数内 `json.loads` | 显式 Code 节点 |
| 依赖 | 仅 `requests` | `langgraph` + `langchain` | Docker + Dify 平台 |
| 适用场景 | 简单、可控、零依赖 | 复杂多步、需状态流转 | 可视化、非开发可维护 |

## 目录结构

```
agent_versions/
├── README.md              # 本文件
├── shared/
│   ├── items_db.py        # 物品库 dict + lookup(item, intent)（三版共用）
│   ├── items_server.py    # Flask :5099，GET /lookup，供 Dify HTTP 节点调用
│   └── .env.example       # 复制为 .env，填 ZHIPU_API_KEY
├── native/
│   └── agent.py           # 原生版：requests + if/elif（零框架）
├── langgraph/
│   ├── agent.py           # LangGraph 版：StateGraph + add_conditional_edges
│   └── requirements.txt
├── dify/
│   ├── workflow.yml         # Dify 工作流 DSL（glm-4-flash 版，需配智谱）
│   ├── workflow.deepseek.yml# Dify 工作流 DSL（deepseek 变体，复用现有供应商）
│   ├── 配置指南.md          # Docker 启动 → 配模型 → 手搭/导入 → 测试
│   ├── import_to_dify.py    # 命令行导入 DSL 到 Dify（console API 自签 JWT）
│   ├── run_test.py          # 跑一次 draft 工作流，打印节点链 + 最终输出
│   ├── docker-compose.yml   # 自托管 Dify（精简参考版）
│   └── nginx/               # Dify 反代配置
└── showcase/
    ├── app.py               # 全栈展示后端：统一 /api/chat，路由三引擎
    ├── requirements.txt     # flask / requests / PyJWT
    └── static/              # 主页三卡片 + 每引擎对话页（index.html/style.css/app.js）
```

## 快速开始

### 0. 准备 Key

```bash
cd agent_versions/shared
copy .env.example .env       # 或手动创建 .env
# 编辑 .env：ZHIPU_API_KEY=你的key
```

### 1. 原生版

```bash
cd agent_versions/native
python agent.py "草帽怎么合成？"    # recipe → 查库 → "12×干草" → 中文回答
python agent.py "木甲防御多少？"    # stats → "减免 80% 伤害"
python agent.py "今天天气如何？"    # other → 跳过工具，直接回答
```

### 2. LangGraph 版

```bash
cd agent_versions/langgraph
pip install -r requirements.txt
python agent.py "草帽怎么合成？"
python agent.py "今天天气如何？"    # route 返回 "answer"，跳过 tool 节点
```

### 3. Dify 版

见 [`dify/配置指南.md`](dify/配置指南.md)：起 Dify → 配 GLM → 导入 `workflow.yml`（或手搭）→ 运行测试。

### 4. 全栈展示（一个主页跳转三个 agent）

```bash
cd agent_versions/showcase
pip install -r requirements.txt
python app.py            # 打开 http://localhost:5100
```

主页三张卡片（原生版 / LangGraph 版 / Dify 版），点击进入对应对话页；后端把三个引擎统一成
`POST /api/chat`（`{"engine": "native|langgraph|dify", "query": "..."}`）。
主页另有「🆚 三版并排对比」：同一问题同时问三个引擎，一屏并排展示差异与各自耗时。

Dify 卡片现在接的是**真实游戏大脑**（`dont_starve_bot/live_agent/dify_brain.py`，Dify 链 app `3ff0efd8`），
不再是物品问答：点击进入「游戏大脑控制台」，输入指令 → Dify 链规划/建议 → GLM 决策动作 →
回灌 `state_api`（`:5002`）。后端新增 `POST /api/brain`（跑一轮）和 `GET /api/brain/state`（读状态）。
实际在游戏里执行动作，还需 game + `dst_mod` + `bridge.py` 在跑（state_api 队列只是暂存）。
「在 Dify 打开 ↗」跳转到已发布应用（需 Dify 容器在跑）。

## 验证一致性

对同一输入（如 `草帽怎么合成？`），三版本输出**语义等价**的回答 → 证明「同一功能，三种编排」。
