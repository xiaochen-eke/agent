#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_verbs.py — 跨语言一致性自检：Python ACTION_VERBS ↔ modmain.lua exec_action。

为什么需要：动作白名单在 Python（skills.ACTION_VERBS）和 Lua（modmain.lua 的
exec_action 分支）各有一份，跨语言无法共享。加了新 verb 若只在一边生效，另一边会
静默拒绝/无实现。此脚本把两边抽出来比对，不一致立即报警。

用法：cd live_agent && python check_verbs.py
"""
import os
import re
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import skills

LUA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dst_mod", "modmain.lua")


def check():
    """返回 (ok: bool, messages: list[str])。"""
    if not os.path.exists(LUA_PATH):
        return False, [f"找不到 mod 文件：{LUA_PATH}"]

    lua = open(LUA_PATH, encoding="utf-8").read()
    # exec_action 里的 `if/elseif verb == "x"` 分支；find_nearby_harvestable 里的同名
    # 校验是 chop/mine/harvest 的子集，取集合后不影响比对。
    lua_verbs = set(re.findall(r'verb\s*==\s*"([a-z_]+)"', lua))
    py_verbs = set(skills.ACTION_VERBS)

    missing_in_lua = py_verbs - lua_verbs   # Python 白名单有、Lua 没 exec 分支（最危险）
    missing_in_py = lua_verbs - py_verbs    # Lua 有分支、Python 没白名单（分支成了死代码）

    if not missing_in_lua and not missing_in_py:
        return True, [f"✅ Python ACTION_VERBS 与 modmain.lua exec_action 一致：{sorted(py_verbs)}"]

    msgs = []
    if missing_in_lua:
        msgs.append(f"❌ Python 白名单有、但 modmain.lua 没有 exec 分支：{sorted(missing_in_lua)}（加了 verb 忘了写 Lua）")
    if missing_in_py:
        msgs.append(f"⚠️  modmain.lua 有分支、但 Python 白名单没有：{sorted(missing_in_py)}（Lua 分支是死代码）")
    return False, msgs


if __name__ == "__main__":
    ok, msgs = check()
    for m in msgs:
        print(m)
    sys.exit(0 if ok else 1)
