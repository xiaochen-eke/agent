# Agent 全栈项目集合

个人 AI / 全栈项目仓库，包含四个子系统：

| 目录 | 说明 | 端口 | 技术栈 |
|------|------|------|--------|
| `Agent/` | 多模态 Agent（图片搜索 / 网络搜索 / 角色人格） | — | Python |
| `agent_versions/` | Agent 控制台（showcase 前端 + Dify / LangGraph / 原生大脑） | 5100 | Flask + 原生 JS |
| `blog/` | 个人动态博客（标签 / 分类 / 全文搜索 / 评论 / 后台） | 5200 | Flask + Jinja + SQLite |
| `dont_starve_bot/` | 饥荒（Don't Starve）游戏 AI 助手 | 多服务 | Flask + React + RAG + LoRA |

## 目录结构

```
Agent/              # 多模态 Agent
agent_versions/     # Agent 控制台（含 showcase 画布滑块验证码）
blog/               # 个人博客
dont_starve_bot/    # 饥荒 AI 助手（backend / frontend / live_agent / rag-exp）
```

## 快速开始

各子项目独立运行，详细说明见各自目录内的 README / 文档。

### blog（个人博客）

```bash
cd blog
cp .env.example .env          # 按需修改 ADMIN_USER / ADMIN_PASS / SITE_TITLE
pip install -r requirements.txt
python app.py                  # 默认 http://localhost:5200
```

### agent_versions/showcase（Agent 控制台）

```bash
cd agent_versions/showcase
cp .env.example .env          # 配置 Dify / 数据库连接
pip install -r requirements.txt
python app.py                  # 默认 http://localhost:5100
```

### dont_starve_bot（饥荒 AI 助手）

```bash
cd dont_starve_bot
# 分别启动 backend / frontend / live_agent，见 SYSTEM_README.md
```

## 安全说明

- 所有 `.env`（含密钥）、数据库文件（`*.db` / `chroma_db/`）、模型权重（`lora_model/`）均已通过 `.gitignore` 排除，不会进入版本库。
- 配置示例见各目录的 `.env.example`，复制为 `.env` 后填入你自己的密钥。
