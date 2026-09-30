# 演示 runbook —— DST 控制角色 agent（Dify 版）

照着这个跑，就能演示「agent 自主控制角色，靠数据库/联网搜索做决策」的完整闭环。

## 0. 前置

- 游戏：`Don't Starve Together`（本地主机开档），`dst_mod/` 已复制到游戏 `mods/DifyCollector/` 并在 `modsettings.lua` 用 `ForceEnableMod("DifyCollector")` 启用。
- Dify：本地 Docker 已起，`DIFY_API_KEY` 指向的活链是 `饥荒生存规划-Demo-v3(接真实后端)`（app `3ff0efd8`，36 节点），start 已声明 `goal/memory/last_action/voice_query/vision_summary/image`、end 输出 `final_advice`+`plan`，**记忆/语音/视觉接线已生效，无需重导**（`difybanbe/dify_workflow.yml` 是过时的 8 节点导出，别用它重导）。
- 环境变量：`live_agent/.env`（复制自 `.env.example`）至少填 `ZHIPU_API_KEY`、`DIFY_API_KEY`。

## 1. 环境变量（.env）

```bash
ZHIPU_API_KEY=你的智谱key        # GLM 动作决策（search_db/web_search/read_webpage）必填
DIFY_API_KEY=app-xxxx            # Dify 工作流鉴权（dify_brain 已有默认值兜底）
DST_GOAL=我想活到冬天
DST_RULE_ACTIONS=0               # 0=LLM 大脑唯一动作源（演示用）；1=回退到规则兜底动作
```

## 2. 启动顺序（4 个进程，各开一个终端）

```bash
# ① 游戏知识库 API :5001
cd C:\DLdata\git\dont_starve_bot && python game_data_api.py

# ② 状态中枢 + 面板 :5002
cd C:\DLdata\git\dont_starve_bot\live_agent && python state_api.py

# ③ 日志↔HTTP 桥接
cd C:\DLdata\git\dont_starve_bot\live_agent && python bridge.py

# ④ Dify 版大脑（常驻轮询）
cd C:\DLdata\git\dont_starve_bot\live_agent && python dify_brain.py
```

> ④ 可用 `--once` 单次联调；`--once --voice a.wav` / `--once --vision screen.png` 测语音/视觉。

## 3. 进游戏

1. 开档进入（主机身份）。
2. 确认桥接日志出现 `[bridge] 监听日志: ...master_server_log.txt`，且 `GET http://127.0.0.1:5002/current_state` 能看到三围/背包/附近。
3. 打开面板 `http://127.0.0.1:5002/panel`。

## 4. 演示剧本（自主闭环）

1. 让角色处于一个**会触发告警**的状态——例如饿了（饥饿 < 25）或生命低，面板状态栏会出现 `⚠️ 状态告警`。
2. 观察 `dify_brain` 终端，依次应出现：
   - `[dify_brain] 触发 Dify 工作流…`（段1：Dify 链规划+检索百科）
   - `[dify_brain] ✅ 已回灌: <一句话建议>`（建议 → bridge 写 `dify_advice.json` → 游戏内公屏播报）
   - `🔍/🌐/📄`（若 GLM 决策时调用了 search_db/web_search/read_webpage 工具）
   - `[dify_brain] ✅ 已推动作: <verb> <prefab>`（段2：GLM 决策出动作 → bridge 写 `dify_action.json`）
3. 游戏内：角色执行动作（吃/合成/砍树…），`[DIFY_ACT_RESULT]` 回传执行结果。
4. 面板时间线显示三段：**建议 → 动作 → 结果**。

> 想让动作更容易命中：给角色背包里放点食物/工具（浆果、肉丸、斧头、镐子），或在附近放棵树/矿/草丛。GLM 决策有 verb 白名单 + prefab 必须在背包/附近 的校验，材料越齐全，动作越容易产生。

## 5. 手动通道（可选）

- 面板底部输入「帮我找点吃的」→ 发送 → 同样走一遍「Dify 建议 → GLM 动作 → 执行」，且**不带 45s 冷却**（玩家主动输入优先）。
- 面板右侧 10 个动作按钮可手动触发单条动作（高风险如「攻击」会弹 Y/N 确认）。

## 6. 故障排查

| 现象 | 排查 |
|---|---|
| `暂无游戏状态` | 先起游戏/mod，确认 bridge 抓到了 `[DIFY_STATE]` 行 |
| Dify 返回 503/失败 | Dify 服务过载，会自动重试；或检查 `DIFY_API_KEY` |
| 有建议但无动作 | `ZHIPU_API_KEY` 没填、或状态里无可执行素材（背包/附近没有匹配 prefab） |
| 动作重复执行 | 确认 `DST_RULE_ACTIONS=0`（关闭了 state_api 规则动作） |
| Dify 返回 `Variable #xxx# not found` | 链图有悬空变量引用（活链历史 bug：`reflect.text` 已修为 `self_correct.final_advice`）——见 `memory/dst-dify-db-edit.md` 用 DB 直改 |
