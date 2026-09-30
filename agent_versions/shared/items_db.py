#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""items_db.py — 饥荒物品库（内置 dict，~10 条）+ lookup(item, intent)。

三版本共用同一份数据：
  - native     直接 import lookup()（工具 = 本地函数调用）
  - langgraph  直接 import lookup()（工具 = 图节点内函数调用）
  - dify       经 items_server 的 HTTP 端点调用（工具 = HTTP 节点）
"""

ITEMS = {
    "草帽": {"id": "straw_hat", "recipe": "12×干草", "stats": "遮阳、轻微回理智", "desc": "干草编的帽子，白天遮阳、缓慢恢复理智"},
    "木甲": {"id": "log_suit", "recipe": "8×原木 + 2×绳子", "stats": "减免 80% 伤害", "desc": "原木做的护甲，牺牲行动速度换取高额减伤"},
    "火把": {"id": "torch", "recipe": "2×干草 + 2×树枝", "stats": "夜间照明", "desc": "手持火把在夜晚提供光源"},
    "斧头": {"id": "axe", "recipe": "1×树枝 + 1×燧石", "stats": "砍树工具", "desc": "砍树必备工具"},
    "镐子": {"id": "pickaxe", "recipe": "2×树枝 + 2×燧石", "stats": "采矿工具", "desc": "挖矿、敲石头必备工具"},
    "营火": {"id": "campfire", "recipe": "3×干草 + 2×原木", "stats": "照明 + 取暖", "desc": "可放置的火源，夜晚照明、冬天取暖"},
    "科学机器": {"id": "science_machine", "recipe": "1×金子 + 4×原木 + 4×石头", "stats": "解锁科技", "desc": "解锁进阶合成配方"},
    "长矛": {"id": "spear", "recipe": "2×树枝 + 1×燧石 + 1×绳子", "stats": "攻击力 34", "desc": "基础近战武器"},
    "肉丸": {"id": "meatballs", "recipe": "1×肉 + 3×填充物", "stats": "回 62.5 饥饿", "desc": "基础熟食，高性价比回饥饿"},
    "陷阱": {"id": "trap", "recipe": "2×树枝 + 2×干草", "stats": "捕捉小动物", "desc": "可放置的陷阱，捕捉兔子等小动物"},
}


def _format(name: str, intent: str) -> str:
    d = ITEMS[name]
    if intent == "recipe":
        return f"{name}的合成配方：{d['recipe']}"
    if intent == "stats":
        return f"{name}的属性：{d['stats']}"
    return f"{name}：配方 {d['recipe']}；属性 {d['stats']}"


def lookup(item: str, intent: str) -> str:
    """按物品名模糊匹配；intent=recipe 返回配方，stats 返回属性；未命中返回提示。"""
    item = (item or "").strip()
    if not item:
        return "未指定物品名。"
    # 1) 精确匹配
    if item in ITEMS:
        return _format(item, intent)
    # 2) 子串匹配（用户输入含物品名，或物品名含用户输入）
    for name in ITEMS:
        if name in item or item in name:
            return _format(name, intent)
    return f"未找到「{item}」的物品信息。"
