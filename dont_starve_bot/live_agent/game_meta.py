#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
game_meta.py — 游戏元数据（可合成清单 / 稀有度 / 配方），硬编码兜底 + game_data_api 动态增强

为什么需要它（面试可讲）：
  「哪些能造、要什么材料、哪些贵、丢什么会心疼」这类知识不该写死在动作决策代码里，
  而应该来自数据服务（game_data_api:5001）。本模块做两层：
    1. 硬编码兜底：真实 DST prefab 的基础清单，保证 API 挂了/数据不全时也能用
    2. 动态增强：从 game_data_api 拉 rarity/配方，翻译成 DST prefab 后并入基础清单
  这样当数据服务更新（补全真实配方/稀有度）时，动作白名单和风险分级自动跟着变。

注意：game_data_api 当前是「模拟小数据集」，且部分 id 是英文词典名而非 DST prefab
（如 wood→log、grass→cutgrass），所以用 ID_TO_PREFAB 做映射；映射不到的原样保留。
"""
import os
import time

import requests

GAME_API = os.getenv("DST_GAME_API", "http://127.0.0.1:5001")
CACHE_TTL = 60  # 元数据缓存秒数（避免每次决策都打 API）

# 动作白名单已迁移到 skills.py（技能注册表，单一数据源），本模块只负责「物品」元数据。

# ============ 硬编码兜底（真实 DST prefab，动态数据在其上增强） ============
CRAFTABLE_PREFABS = [
    "torch", "axe", "pickaxe", "spear", "hammer", "shovel",
    "backpack", "strawroll", "rope", "boards", "cutstone",
    "bugnet", "trap", "fishingrod", "razor", "papyrus", "compass",
]
CRITICAL_DROP = {
    "torch", "lantern", "minerhat",
    "redgem", "bluegem", "purplegem", "yellowgem", "orangegem", "greengem", "opal",
    "thulecite", "gears", "livinglog", "nightsword", "batbat", "tentaclespike",
}
EXPENSIVE_CRAFT = {"cutstone", "strawroll", "spear"}

# 建筑/结构（build 动词专用）：builder 能「建造」的可放置结构，与 craftable（合成物品）互补
BUILDABLE_PREFABS = [
    "campfire", "firepit", "wall_stone", "wall_hay", "wall_wood", "chest",
    "sciencemachine", "alchemyengine", "birdcage", "tent", "crockpot", "icebox",
]

# 稀有度 → 风险：丢 essential/rare 的东西 high；合成 uncommon/rare 的东西 high
CRITICAL_RARITIES = {"essential", "rare"}
EXPENSIVE_RARITIES = {"uncommon", "rare"}

# 类别 → 动作归属：builder 只能「合成」物品(weapon/tool/armor...)，不能做下面这些
NON_CRAFTABLE_CATEGORIES = {"building", "food", "resource"}  # 建筑→build / 食物→cook / 资源→raw
NON_DROPPABLE_CATEGORIES = {"building"}                      # 结构是摆放的，不在背包里，无所谓「丢弃」

# DB id（英文词典名）→ DST prefab 翻译表
ID_TO_PREFAB = {
    "wood": "log", "stone": "rocks", "grass": "cutgrass",
    "spider_silk": "silk", "cooked_meat": "cookedmeat", "berry": "berries",
    "seed": "seeds", "egg": "bird_egg", "vegetable": "carrot",
}

_cache = {"ts": 0.0, "meta": None}


def _to_prefab(dbid):
    return ID_TO_PREFAB.get(dbid, dbid)


def _fetch_items_meta():
    """从 game_data_api 拉全部物品元数据，失败返回 []。"""
    try:
        r = requests.get(f"{GAME_API}/api/game-data/items-meta", timeout=3)
        if r.status_code == 200:
            return r.json().get("craftables") or []
    except Exception:
        pass
    return []


def get_meta(force=False):
    """返回动作元数据（60s 缓存）：craftable / critical_drop / expensive_craft / costs。

    动态 = 硬编码兜底 ∪ (game_data_api 数据翻译后加入)。API 不可用就纯硬编码兜底。
    """
    now = time.time()
    if not force and _cache["meta"] and now - _cache["ts"] < CACHE_TTL:
        return _cache["meta"]

    craftable = set(CRAFTABLE_PREFABS)
    buildable = set(BUILDABLE_PREFABS)
    critical = set(CRITICAL_DROP)
    expensive = set(EXPENSIVE_CRAFT)
    costs = {}

    for it in _fetch_items_meta():
        pid = _to_prefab(it.get("id", ""))
        if not pid:
            continue
        rarity = it.get("rarity", "common")
        category = it.get("category") or ""
        cost = it.get("cost")

        # craft 只收「builder 能合成的物品」：有配方，且不是建筑/食物/资源
        if cost and category not in NON_CRAFTABLE_CATEGORIES:
            craftable.add(pid)
            costs[pid] = {_to_prefab(m): n for m, n in cost.items()}
            if rarity in EXPENSIVE_RARITIES:
                expensive.add(pid)

        # build 只收「建筑」类（结构与 craftable 互补）
        if cost and category == "building":
            buildable.add(pid)
            costs.setdefault(pid, {_to_prefab(m): n for m, n in cost.items()})

        # 丢弃风险只对「背包里能装的东西」生效（结构建筑是摆放的，排除）
        if rarity in CRITICAL_RARITIES and category not in NON_DROPPABLE_CATEGORIES:
            critical.add(pid)

    meta = {
        "craftable": craftable,
        "buildable": buildable,
        "critical_drop": critical,
        "expensive_craft": expensive,
        "costs": costs,
    }
    _cache["ts"] = now
    _cache["meta"] = meta
    return meta
