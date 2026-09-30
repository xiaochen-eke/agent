# 饥荒实时生存规划 Agent —— 原生版 + Dify 版

一个「游戏内闭环 co-pilot」：**采集 → 分析 → 决策 → 回灌游戏内主动提醒**，并可**半自动控制角色**（吃/装备/攻击/采集/合成/砍树等 10 种动作）。

本目录有两个大脑，共享同一套采集层（mod 采集器 + bridge + state_api）：

- **原生版 `native_agent.py`**：纯 Python 手写多智能体（规划→检索→执行→反思），直接调智谱 GLM。
- **Dify 版 `dify_brain.py`**：大脑换成 Dify 工作流（规划+检索，DeepSeek）+ GLM 动作决策（function-calling 工具）。Dify 链 DSL 见 `C:\DLdata\git\difybanbe\dify_workflow.yml`。

> 面试价值：能同时讲清"手写编排"和"低代码平台"两条路线，并对比其优劣。
> 演示建议走 Dify 版（`dify_brain.py`），步骤见 [DEMO.md](./DEMO.md)。

## 架构（原生版）

```
[DST 游戏] → dst_mod 采集器（每2s读三围/背包/季节/附近实体）
      │ print("[DIFY_STATE]") 打到服务端日志（io 沙箱只读，写不了文件）
      ▼
[bridge.py] 日志↔HTTP 桥接
      │ tail master_server_log.txt 抓 [DIFY_STATE] 行 → POST /state
      │ GET /advice → 写 <游戏>/data/dify_advice.json（mod 只读该文件做游戏内播报）
      ▼
[state_api.py :5002] 状态服务（阈值检测，触发大脑）
      │  /current_state
      ▼
[native_agent.py] 原生多智能体大脑（本版核心）
      规划 → 检索 → 执行 → 反思
      工具：get_current_state (:5002) + search (:5001 静态百科)
      模型：智谱 GLM（glm-4-flash，复用 ZHIPU_API_KEY）
```

## 目录

```
live_agent/
  dst_mod/        采集器（Lua，装进游戏 mods/DifyCollector）
  bridge.py       文件桥接进程
  state_api.py    实时状态服务 :5002（状态中枢 + 规则兜底 + 面板）
  native_agent.py 原生多智能体大脑（纯 Python）
  dify_brain.py   Dify 版大脑（Dify 链规划 + GLM 动作决策）★演示主路径
  game_meta.py    动作白名单/风险清单（硬编码 ∪ game_data_api 动态增强）
  panel.html      控制面板（http://127.0.0.1:5002/panel）
  DEMO.md         演示 runbook
  README.md
```

## 启动步骤

1. **装 mod**：`dst_mod/` 已复制到游戏 `mods/DifyCollector/`，并在 `mods/modsettings.lua` 用 `ForceEnableMod("DifyCollector")` 强制启用。
2. **起状态服务**：`python state_api.py`（:5002）
3. **起桥接**：`python bridge.py`
4. **进游戏**（主机身份），2 秒后 `master_server_log.txt` 应出现 `[DIFY_STATE]` 行，`GET /current_state` 能看到三围/背包/季节/附近实体。
5. **问 agent**：`python native_agent.py "我想活到冬天"`（多智能体链路会逐角色打印）

> 不依赖游戏也能测：先 `POST /state` 塞一条模拟快照，再跑 `native_agent.py`。

## Dify 版（dify_brain.py）—— 两段式

```
[DST 游戏] → dst_mod 采集（每2s读三围/背包/季节/附近）
      │ print("[DIFY_STATE]") 到服务端日志
      ▼
[bridge.py] 抓日志 → POST /state；轮询 /advice、/action 写回游戏目录
      ▼
[state_api.py :5002] 状态中枢：阈值检测生成 ⚠️ 告警 → 触发大脑
      │
      ├── 规则兜底建议（detect_and_advise，保留）
      └── 规则兜底动作（detect_and_act，默认 DST_RULE_ACTIONS=0 关闭）
      ▼
[dify_brain.py] 轮询状态，发现告警/面板消息 → 调 Dify 工作流
      │   段1：Dify 链（DeepSeek）规划→检索百科(game_data_api)→反思 → final_advice + plan
      │   段2：GLM 动作决策（search_db / web_search / read_webpage 工具）→ {verb, prefab}
      ▼
   POST /advice（建议） + POST /action（动作）→ bridge 写文件 → mod 播报/执行
```

**两个决策段分工**（面试可讲）：
- **段1 Dify 链**：低代码编排「规划→检索→执行→反思」四智能体，跑 DeepSeek，检索走 `game_data_api`(:5001) 的 HTTP 接口。
- **段2 GLM**：`extract_action` 用 GLM-4-flash function-calling，把建议映射成可执行动作 verb+prefab；不确定时主动调 `search_db`（查本地库）/ `web_search`（Bing 联网）/ `read_webpage`（抓网页正文）。

**工具清单**（`GAME_TOOLS` → `_execute_tool`）：
| 工具 | 作用 | 后端 |
|---|---|---|
| `search_db` | 查游戏数据库（物品/配方/生物/季节） | game_data_api :5001 |
| `web_search` | 联网搜索（Bing，国内可直连） | cn.bing.com 抓取 |
| `read_webpage` | 抓指定网页正文 | 直接 requests |

**环境变量**（`.env`，见 `.env.example`）：`ZHIPU_API_KEY`（GLM 动作决策必填）、`DIFY_API_KEY`/`DIFY_API_URL`、`DST_GOAL`、`DST_RULE_ACTIONS`（0=LLM 大脑唯一动作源）、`DST_STATE_API`、`DST_GAME_API`。

## 面试可讲的点

- **为什么拆 4 个 agent**：规划负责"做什么"、检索负责"查什么"、执行负责"怎么做"、反思负责"做得对不对"——职责单一、可独立测试、可换模型。
- **检索是真实工具调用**：不是把知识塞进 prompt，而是检索 agent 先改写搜索词、再 HTTP 查静态百科，真正走"工具调用"链路。
- **反思 = 结果校验**：对执行结果做可行性校验（材料够不够/是否安全），抑制幻觉、提高可信度，输出带置信度。
- **文件桥接 / 事件驱动 / 阈值去噪 / 静态实时分离**：见共享层设计（与 Dify 版同源）。
