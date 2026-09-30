#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""skills.py — 游戏技能注册表（动作系统的单一数据源）。

每个「技能」= 一个动作 verb，在这里声明它的 Python 侧元数据：

  verb    动作名（必须与 dst_mod/modmain.lua 的 exec_action 分支一一对应，用 check_verbs.py 校验）
  cn      中文显示名（showcase 面板 / 结果播报用）
  source  prefab 来源：inventory=背包 / nearby=附近 / craftable=可合成 / buildable=可建造 / none=无需
  risk    默认风险：low=自动 / medium=自动+警告 / high=需 Y/N 确认
  sample  一个能通过校验的示例 prefab（test_verbs.py 自动回归用）
  desc    决策 prompt 里的一句话描述

新增技能只需两步：
  1. 往 SKILLS 里加一条（含 sample）；
  2. 在 dst_mod/modmain.lua 的 exec_action 里加一个实现分支。
然后跑 `python test_verbs.py`，它会自动校验「校验逻辑 + source 合法性 + Python↔Lua 一致性」。

本模块是纯数据，不 import 其它业务模块，避免循环依赖。
"""

SKILLS = [
    # —— 原有 10 个 ——
    {"verb": "eat",     "cn": "吃",   "source": "inventory", "risk": "low",    "sample": "meatballs",
     "desc": "吃背包里的食物（prefab 从「背包」选）"},
    {"verb": "equip",   "cn": "装备", "source": "inventory", "risk": "low",    "sample": "torch",
     "desc": "装备背包里的物品（prefab 从「背包」选）"},
    {"verb": "attack",  "cn": "攻击", "source": "nearby",    "risk": "high",   "sample": "spider",
     "desc": "攻击附近敌对生物（prefab 从「附近」选）"},
    {"verb": "drop",    "cn": "丢弃", "source": "inventory", "risk": "low",    "sample": "carrot",
     "desc": "丢弃背包里不要的东西（prefab 从「背包」选）"},
    {"verb": "pickup",  "cn": "拾取", "source": "nearby",    "risk": "low",    "sample": "cutgrass",
     "desc": "拾取附近的物品（prefab 从「附近」选）"},
    {"verb": "craft",   "cn": "合成", "source": "craftable", "risk": "low",    "sample": "axe",
     "desc": "合成一件物品（prefab 从「可合成」列表选）"},
    {"verb": "sleep",   "cn": "睡觉", "source": "none",      "risk": "medium", "sample": "",
     "desc": "在附近的床/帐篷睡觉（无需 prefab，留空）"},
    {"verb": "chop",    "cn": "砍",   "source": "nearby",    "risk": "medium", "sample": "evergreen",
     "desc": "砍附近的树（prefab 从「附近」选，需要斧头）"},
    {"verb": "mine",    "cn": "挖",   "source": "nearby",    "risk": "low",    "sample": "rocks",
     "desc": "挖附近的矿（prefab 从「附近」选，需要镐子）"},
    {"verb": "harvest", "cn": "采集", "source": "nearby",    "risk": "low",    "sample": "berrybush",
     "desc": "采集附近的草/浆果/花（prefab 从「附近」选）"},
    # —— 新增 4 个 ——
    {"verb": "cook",    "cn": "烹饪", "source": "inventory", "risk": "low",    "sample": "meatballs",
     "desc": "烹饪背包里的食材（prefab 从「背包」选，附近需有火源）"},
    {"verb": "plant",   "cn": "种植", "source": "inventory", "risk": "low",    "sample": "pinecone",
     "desc": "种植背包里的种子/树苗（prefab 从「背包」选）"},
    {"verb": "build",   "cn": "建造", "source": "buildable", "risk": "low",    "sample": "campfire",
     "desc": "建造/放置建筑（prefab 从「可建造」列表选）"},
    {"verb": "explore", "cn": "探索", "source": "none",      "risk": "medium", "sample": "",
     "desc": "朝随机方向移动探索地图（无需 prefab，留空）"},
]

# —— 派生数据（下面这些都从 SKILLS 算出来，别手写，避免不一致）——
ACTION_VERBS = tuple(s["verb"] for s in SKILLS)
VERB_CN = {s["verb"]: s["cn"] for s in SKILLS}
DEFAULT_RISK = {s["verb"]: s["risk"] for s in SKILLS}
SOURCE_OF = {s["verb"]: s["source"] for s in SKILLS}
VERB_LIST = "|".join(ACTION_VERBS)  # 决策 prompt 的 JSON 格式串里用


def prompt_lines():
    """决策 prompt 里「动作动词及 prefab 来源」段落，一行一个技能。"""
    return [f"  {s['verb']:<8s}{s['desc']}" for s in SKILLS]
