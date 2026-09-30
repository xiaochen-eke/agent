#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
state_api.py — 实时游戏状态服务 (Flask, 端口 5002)

职责：
  1. POST /state        接收 mod 上传的状态快照（由 bridge.py 转发）
  2. GET  /current_state 返回最新状态 + 可读摘要（供 Dify 工具调用）
  3. GET  /advice       弹出下一条待播报建议（由 bridge.py 轮询）
  4. 阈值检测：状态突变时生成建议（默认规则兜底，可选接 Dify webhook）

设计说明（面试可讲）：
  - 静态百科 API（game_data_api.py:5001）与实时状态服务（本文件:5002）分离，
    避免"静态数据"和"高频状态流"互相干扰。
  - 用"事件驱动 + 阈值去噪"：不是每秒调 LLM，只有关键状态穿越阈值才生成建议，
    省 token、降延迟、避免刷屏。
"""
import os
import sys
import time
from collections import deque

# 修复 Windows 控制台 GBK 编码问题
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from flask import Flask, request, jsonify, send_file

import game_meta  # 物品元数据（可合成/稀有度/配方）
import skills     # 技能注册表（动作白名单单一数据源）

app = Flask(__name__)

# ============ 配置 ============
# Dify webhook 地址。留空则用内置规则兜底；填了则阈值触发时调 Dify（见 README）。
DIFY_WEBHOOK_URL = os.environ.get("DIFY_WEBHOOK_URL", "")

# 阈值（穿越才触发，避免每个周期重复提醒）
THRESHOLDS = {
    "sanity": 30,   # 精神值低于 30
    "hunger": 25,   # 饥饿值低于 25
    "health": 30,   # 生命值低于 30
}
ALERT_COOLDOWN = 30  # 同一类提醒的冷却秒数

# 可执行动作白名单（单一数据源在 skills.ACTION_VERBS）
ACTION_VERBS = skills.ACTION_VERBS

SEASON_CN = {"autumn": "秋季", "winter": "冬季", "spring": "春季", "summer": "夏季"}
PHASE_CN = {"day": "白天", "dusk": "黄昏", "night": "夜晚"}

# ============ 内存存储 ============
latest_state = None
recent_states = deque(maxlen=60)  # 最近 60 条，供趋势分析
advice_outbox = deque()           # 待播报建议 FIFO
advice_seq = 0
action_outbox = deque()           # 待执行动作 FIFO（{id, verb, prefab}）
action_seq = 0
event_history = deque(maxlen=300)  # 面板统一时间线：user/advice/action/result
query_outbox = deque()             # 面板待消费消息（dify_brain 轮询）
_cooldowns = {}                   # key -> 上次提醒时间戳
_last_season = None


# ============ 建议生成（规则兜底） ============
def rule_based_advice(player, world):
    """根据单玩家状态 + 世界状态生成中文建议列表。纯规则，无 LLM 依赖。"""
    advices = []
    now = time.time()
    season = (world or {}).get("season")
    phase = (world or {}).get("phase")

    def cooled(key):
        if now - _cooldowns.get(key, 0) < ALERT_COOLDOWN:
            return False
        _cooldowns[key] = now
        return True

    health = player.get("health")
    hunger = player.get("hunger")
    sanity = player.get("sanity")
    temperature = player.get("temperature")

    if health is not None and health < THRESHOLDS["health"] and cooled("health"):
        advices.append(f"生命值只剩 {health}，先脱离战斗、吃回血食物或睡觉回血！")

    if hunger is not None and hunger < THRESHOLDS["hunger"] and cooled("hunger"):
        advices.append(f"饥饿值只剩 {hunger}，尽快进食（推荐肉丸/炖肉），否则会持续掉血。")

    if sanity is not None and sanity < THRESHOLDS["sanity"] and cooled("sanity"):
        advices.append(f"精神值只剩 {sanity}，采绿/蓝蘑菇烤着吃，或睡草席/帐篷恢复。")

    if phase == "dusk" and cooled("dusk"):
        advices.append("天快黑了，查理快来了——尽快备好光源（火把/营火）！")

    if phase == "night" and cooled("night"):
        advices.append("现在是夜晚，待在光源范围内，别摸黑乱走。")

    if temperature is not None:
        if season == "winter" and temperature < 5 and cooled("cold"):
            advices.append(f"体温只有 {temperature}，快烤火/穿保暖衣物，避免冻伤。")
        if season == "summer" and temperature > 60 and cooled("hot"):
            advices.append(f"体温 {temperature} 过高，快降温，避免过热掉血。")

    if season and season != _last_season and cooled("season"):
        advices.append(f"季节进入{SEASON_CN.get(season, season)}，注意调整生存策略。")

    return advices


def detect_and_advise(state):
    """遍历玩家，生成建议并入队。返回本次生成的建议条数。"""
    global _last_season
    produced = 0
    world = state.get("world", {})
    players = state.get("players", [])
    if isinstance(players, dict):
        players = list(players.values())

    for player in players:
        for text in rule_based_advice(player, world):
            _enqueue_advice(text)
            produced += 1

    season = world.get("season")
    if season and season != _last_season:
        _last_season = season
    return produced


# ============ 动作生成（反射层：确定性规则 → 可执行动作） ============
# 与 rule_based_advice 对称：advice 是「说什么」，action 是「做什么」。
# 白名单 prefab 先硬编码一小套常见物品，后续可换成 game_data_api 的分类接口。
FOOD_PREFABS = [
    "meatballs", "carrot", "berries", "cookedmeat", "monstermeat_cooked",
    "frogglebunwich", "baconeggs", "honey", "seeds_cooked", "pumpkin_cooked",
    "corn_cooked", "butterflywings", "petals", "meat",
]
HEALING_FOOD = ["honey", "butterflywings", "spidergland", "healingsalve"]
LIGHT_PREFABS = ["torch", "lantern", "minerhat"]
ENEMY_PREFABS = ["spider", "spiderwarrior", "hound", "frog", "tallbird", "spiderqueen", "merm"]

# —— 风险分级清单（丢弃/合成哪些算 high）已迁到 game_meta.py ——
# game_meta.get_meta() 返回动态版：硬编码兜底 ∪ game_data_api 稀有度/配方数据。

# 各动作的冷却（秒）：攻击是高风险，冷却拉长避免反复弹确认
ACTION_COOLDOWN = {"eat": 20, "equip": 30, "attack": 120}
_action_cooldowns = {}


def _first_in(mapping, candidates):
    """在 {prefab: count} 里按候选顺序取第一个存在的 prefab。"""
    for prefab in candidates:
        if mapping.get(prefab):
            return prefab
    return None


def rule_based_action(player, world):
    """把状态信号转成一条可执行动作（反射层，纯规则，无 LLM）。返回 {verb,prefab} 或 None。

    优先级：饥饿→吃 → 生命→回血 → 夜晚→光源 → 附近敌对→攻击（高风险，mod 会弹确认）。
    只有穿越阈值才产生动作，且带冷却，避免每个周期重复触发刷屏。
    """
    inv = player.get("inventory") or {}
    nearby = player.get("nearby") or {}
    health = player.get("health")
    hunger = player.get("hunger")
    phase = (world or {}).get("phase")
    now = time.time()

    def cooled(verb):
        if now - _action_cooldowns.get(verb, 0) < ACTION_COOLDOWN.get(verb, 20):
            return False
        _action_cooldowns[verb] = now
        return True

    if hunger is not None and hunger < 50 and cooled("eat"):
        food = _first_in(inv, FOOD_PREFABS) or _first_in(inv, HEALING_FOOD)
        if food:
            return {"verb": "eat", "prefab": food}

    if health is not None and health < 60 and cooled("eat"):
        heal = _first_in(inv, HEALING_FOOD)
        if heal:
            return {"verb": "eat", "prefab": heal}

    if phase == "night" and cooled("equip"):
        light = _first_in(inv, LIGHT_PREFABS)
        if light:
            return {"verb": "equip", "prefab": light}

    if health is not None and health > 60 and cooled("attack"):
        enemy = _first_in(nearby, ENEMY_PREFABS)
        if enemy:
            return {"verb": "attack", "prefab": enemy}

    return None


def _sleep_unsafe(state):
    """判断当前环境睡觉是否危险：夜晚没光源 / 太冷 / 附近有敌对。"""
    world = (state or {}).get("world", {})
    players = (state or {}).get("players", [])
    if isinstance(players, dict):
        players = list(players.values())
    if not players:
        return False
    p = players[0]
    phase = world.get("phase")
    temp = p.get("temperature")
    inv = p.get("inventory") or {}
    nearby = p.get("nearby") or {}
    has_light = any(l in inv for l in LIGHT_PREFABS)
    has_enemy = any(e in nearby for e in ENEMY_PREFABS)
    if phase in ("night", "dusk") and not has_light:
        return True
    if temp is not None and temp < 5:
        return True
    if has_enemy:
        return True
    return False


def classify_risk(verb, prefab, state=None):
    """动作风险分级：low 自动 / medium 自动+警告 / high 需 Y/N 确认。

    默认风险来自 skills 注册表（DEFAULT_RISK）；下面是几个「上下文敏感」的覆盖：
      sleep → 危险环境 high，否则 medium
      craft → 烧稀有材料 high，便宜货 low
      drop  → 丢关键物品 high，丢垃圾 low
    """
    if verb == "sleep":
        return "high" if _sleep_unsafe(state) else "medium"
    meta = game_meta.get_meta()  # 动态风险清单（硬编码 ∪ game_data_api 稀有度）
    if verb == "craft":
        return "high" if prefab in meta["expensive_craft"] else "low"
    if verb == "drop":
        return "high" if prefab in meta["critical_drop"] else "low"
    return skills.DEFAULT_RISK.get(verb, "low")


def _enqueue_action(action, risk="low"):
    global action_seq
    action_seq += 1
    aid = str(action_seq)
    action_outbox.append({"id": aid, "verb": action["verb"], "prefab": action["prefab"], "risk": risk, "ts": time.time()})
    event_history.append({"type": "action", "ts": time.time(), "id": aid, "verb": action["verb"], "prefab": action["prefab"], "risk": risk, "status": "queued"})


def detect_and_act(state):
    """遍历玩家生成动作并入队（反射层）。返回本次生成的动作条数。

    反射层动作默认关闭（DST_RULE_ACTIONS=0）：此时 LLM 大脑（dify_brain 的 extract_action）
    是唯一动作源，避免「规则动作 + LLM 动作」重复执行（如饥饿时吃两次）。
    需要纯规则兜底（Dify/GLM 全挂时仍能自动吃/攻击/装备）时设 DST_RULE_ACTIONS=1。
    """
    if os.getenv("DST_RULE_ACTIONS", "0") == "0":
        return 0
    world = state.get("world", {})
    players = state.get("players", [])
    if isinstance(players, dict):
        players = list(players.values())
    produced = 0
    for player in players:
        action = rule_based_action(player, world)
        if action:
            _enqueue_action(action, risk=classify_risk(action["verb"], action["prefab"], state))
            produced += 1
    return produced


def _enqueue_advice(message, source="rule"):
    global advice_seq
    advice_seq += 1
    advice_outbox.append({"id": str(advice_seq), "message": message, "source": source, "ts": time.time()})
    event_history.append({"type": "advice", "ts": time.time(), "source": source, "text": message})


# ============ 可读摘要 ============
def _fmt(v):
    """数值格式化：整数原样，浮点保留 1 位（去掉多余 0），None 显示 ?。"""
    if v is None:
        return "?"
    if isinstance(v, float):
        return f"{v:.1f}".rstrip("0").rstrip(".")
    return str(v)


def player_alerts(p):
    """把裸数值转成「状态告警」，帮 LLM 一眼识别危险（阈值去噪的轻量版）。"""
    alerts = []
    health = p.get("health")
    maxhealth = p.get("maxhealth")
    if health is not None:
        if health < THRESHOLDS["health"]:
            alerts.append(f"生命值危急 {_fmt(health)}/{_fmt(maxhealth)}")
        elif maxhealth and health < maxhealth * 0.5:
            alerts.append(f"生命值偏低 {_fmt(health)}/{_fmt(maxhealth)}")
    hunger = p.get("hunger")
    if hunger is not None and hunger < 50:
        alerts.append(f"饥饿偏低 {_fmt(hunger)}")
    sanity = p.get("sanity")
    if sanity is not None and sanity < 50:
        alerts.append(f"精神偏低 {_fmt(sanity)}")
    return alerts


def summarize(state):
    """把最新状态压成一段中文摘要，便于 LLM/Dify 工具直接消费。"""
    world = state.get("world", {})
    season = SEASON_CN.get(world.get("season"), world.get("season"))
    phase = PHASE_CN.get(world.get("phase"), world.get("phase"))
    day = world.get("day")
    lines = [f"季节:{season} 第{day}天 {phase}"]

    players = state.get("players", [])
    if isinstance(players, dict):
        players = list(players.values())
    for p in players:
        inv = p.get("inventory") or {}
        inv_s = "、".join(f"{k}x{v}" for k, v in list(inv.items())[:12]) or "空"
        nearby = p.get("nearby") or {}
        nearby_s = "、".join(f"{k}x{v}" for k, v in list(nearby.items())[:10]) or "无"
        lines.append(
            f"玩家[{p.get('prefab')}] 生命{_fmt(p.get('health'))}/{_fmt(p.get('maxhealth'))} "
            f"饥饿{_fmt(p.get('hunger'))} 精神{_fmt(p.get('sanity'))} 体温{_fmt(p.get('temperature'))} "
            f"| 背包:{inv_s} | 附近:{nearby_s}"
        )
        alerts = player_alerts(p)
        if alerts:
            lines.append(f"⚠️ 状态告警: {'；'.join(alerts)}")
    return "\n".join(lines)


# ============ 路由 ============
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "has_state": latest_state is not None})


@app.route("/state", methods=["POST"])
def receive_state():
    global latest_state
    data = request.get_json(force=True)
    latest_state = data
    recent_states.append(data)
    produced = detect_and_advise(data)
    acted = detect_and_act(data)
    return jsonify({"status": "ok", "advice_produced": produced, "action_produced": acted})


@app.route("/current_state", methods=["GET"])
def current_state():
    if latest_state is None:
        return jsonify({"status": "empty", "summary": "尚未收到游戏状态"}), 200
    return jsonify({"status": "ok", "state": latest_state, "summary": summarize(latest_state)})


@app.route("/advice", methods=["GET"])
def pop_advice():
    if advice_outbox:
        return jsonify(advice_outbox.popleft())
    return jsonify({})


@app.route("/advice", methods=["POST"])
def push_advice():
    """外部大脑（如 Dify 工作流 / native_agent）把建议推入播报队列。

    bridge.py 轮询 GET /advice 时会把它写进游戏内 dify_advice.json，由 mod 播报。
    这样「规则兜底」和「LLM 大脑」共用同一条出队链路，闭环只依赖这一个接口。
    """
    data = request.get_json(force=True, silent=True) or {}
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"status": "error", "message": "缺少 message 字段"}), 400
    source = (data.get("source") or "external").strip()
    _enqueue_advice(message, source=source)
    return jsonify({"status": "ok"}), 200


@app.route("/action", methods=["POST"])
def push_action():
    """外部大脑把「可执行动作」推入动作队列，由 mod 读取并执行（半自动控制角色）。

    动作格式：{"verb": "eat|equip|attack", "prefab": "游戏内 prefab 名"}。
    bridge.py 轮询 GET /action 时写进游戏内 dify_action.json，mod 读后执行。
    """
    data = request.get_json(force=True, silent=True) or {}
    verb = (data.get("verb") or "").strip()
    prefab = (data.get("prefab") or "").strip()
    if verb not in ACTION_VERBS:
        return jsonify({"status": "error", "message": f"非法 verb: {verb}"}), 400
    risk = classify_risk(verb, prefab, latest_state)
    _enqueue_action({"verb": verb, "prefab": prefab}, risk=risk)
    return jsonify({"status": "ok", "id": str(action_seq), "risk": risk}), 200


@app.route("/action", methods=["GET"])
def pop_action():
    """弹出下一条待执行动作（FIFO），供 bridge 轮询。"""
    if action_outbox:
        return jsonify(action_outbox.popleft())
    return jsonify({})


# ============ Web 控制面板（单文件 HTML + 数据接口） ============

@app.route("/panel", methods=["GET"])
def panel():
    """托管单文件控制面板（live_agent/panel.html）。"""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "panel.html")
    return send_file(path, mimetype="text/html")


@app.route("/panel/snapshot", methods=["GET"])
def panel_snapshot():
    """面板一次性拿到：最新状态 + 可读摘要 + 统一时间线。"""
    return jsonify({
        "now": time.time(),
        "state": latest_state,
        "summary": summarize(latest_state) if latest_state else "",
        "events": list(event_history),
    })


@app.route("/panel/message", methods=["POST"])
def panel_message():
    """面板「发送消息」：写入 query_outbox 供 dify_brain 轮询，并记入时间线。"""
    data = request.get_json(force=True, silent=True) or {}
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"status": "error", "message": "缺少 message 字段"}), 400
    query_outbox.append({"id": f"{time.time():.3f}", "text": message, "ts": time.time()})
    event_history.append({"type": "user", "ts": time.time(), "text": message})
    return jsonify({"status": "ok"}), 200


@app.route("/panel/query", methods=["GET"])
def panel_query():
    """dify_brain 轮询：弹出下一条待处理的面板消息。"""
    if query_outbox:
        return jsonify(query_outbox.popleft())
    return jsonify({})


@app.route("/action/result", methods=["POST"])
def action_result():
    """mod 执行结果回传（bridge 解析 [DIFY_ACT_RESULT] 后转发）。"""
    data = request.get_json(force=True, silent=True) or {}
    aid = str(data.get("id") or "")
    ok = bool(data.get("ok"))
    reason = (data.get("reason") or "").strip()
    verb = (data.get("verb") or "").strip()
    prefab = (data.get("prefab") or "").strip()
    for ev in event_history:
        if ev.get("type") == "action" and ev.get("id") == aid:
            ev["status"] = "done" if ok else "failed"
            break
    event_history.append({"type": "result", "ts": time.time(), "id": aid, "verb": verb, "prefab": prefab, "ok": ok, "reason": reason})
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    print("实时状态服务启动: http://127.0.0.1:5002")
    print("   POST /state        接收快照（含反射层建议+动作）")
    print("   GET  /current_state 最新状态")
    print("   GET  /advice       弹出建议")
    print("   POST /action       推入动作   GET /action 弹出动作")
    app.run(host="0.0.0.0", port=5002, debug=False)
