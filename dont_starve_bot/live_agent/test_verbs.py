#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_verbs.py — 技能注册表回归测试：每个技能都能通过校验，不会静默消失。

为什么需要：动作决策失败时校验层静默 return None，很难发现「某个技能其实从没跑通」。
此测试从 skills.SKILLS 里读每个技能，用它的 sample 构造合成状态，断言 _validate_action
能正常放行，最后顺带跑 check_verbs 的跨语言一致性自检。

新增技能 = 往 skills.SKILLS 加一条（含 sample），本测试自动覆盖，无需手改。

用法：cd live_agent && python test_verbs.py
"""
import os
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import skills
import game_meta
import dify_brain
import check_verbs


def main():
    meta = game_meta.get_meta(force=True)
    craftable = meta["craftable"]
    buildable = meta["buildable"]

    # 用各技能声明的 sample 自动构造合成背包/附近（craftable/buildable 直接用真实名单）
    INV, NEARBY = {}, {}
    for s in skills.SKILLS:
        sample = s.get("sample")
        if not sample:
            continue
        if s["source"] == "inventory":
            INV[sample] = 1
        elif s["source"] == "nearby":
            NEARBY[sample] = 1

    failed = 0
    print("== 校验每个技能能通过 ==")
    for s in skills.SKILLS:
        verb = s["verb"]
        prefab = s.get("sample", "")
        r = dify_brain._validate_action(verb, prefab, INV, NEARBY, craftable, buildable)
        ok = isinstance(r, dict) and r.get("verb") == verb
        print(f"  {'✅' if ok else '❌'} {verb:8s} {prefab or '(空)':12s} [{s['source']}]")
        if not ok:
            failed += 1

    print("\n== source 字段合法性 ==")
    valid_src = {"inventory", "nearby", "craftable", "buildable", "none"}
    src_ok = True
    for s in skills.SKILLS:
        if s["source"] not in valid_src:
            print(f"  ❌ {s['verb']}: 非法 source {s['source']!r}")
            src_ok = False
            failed += 1
        if s["source"] != "none" and not s.get("sample"):
            print(f"  ❌ {s['verb']}: source={s['source']} 但没给 sample，测试覆盖不到")
            src_ok = False
            failed += 1
    if src_ok:
        print("  ✅ source 字段全部合法，且需要 sample 的都有")

    print("\n== 跨语言一致性自检（check_verbs） ==")
    c_ok, c_msgs = check_verbs.check()
    for m in c_msgs:
        print("  " + m)
    if not c_ok:
        failed += 1

    print()
    if failed:
        print(f"❌ {failed} 项失败")
        return 1
    print(f"✅ 全部通过（{len(skills.SKILLS)} 个技能）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
