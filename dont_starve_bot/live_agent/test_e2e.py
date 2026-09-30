#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""端到端联调：state_api(5002) + game_data_api(5001) + dify_brain -> Dify 工作流 -> 回灌队列。"""
import subprocess
import sys
import time

import requests

BASE = "http://127.0.0.1"

procs = []


def start(pyfile):
    p = subprocess.Popen([sys.executable, pyfile], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    procs.append(p)
    return p


def wait_health(port, path="/health", tries=60):
    for _ in range(tries):
        try:
            if requests.get(f"{BASE}:{port}{path}", timeout=1).status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.3)
    return False


def main():
    print("启动 state_api(5002) + game_data_api(5001) …")
    start("state_api.py")
    start("../game_data_api.py")
    if not wait_health(5002):
        print("state_api 启动失败"); return 1
    if not wait_health(5001, path="/api/game-data/health"):
        print("game_data_api 启动失败"); return 1
    print("✅ 两个服务就绪")

    # 灌一条会触发阈值告警的模拟状态
    snap = {
        "world": {"season": "winter", "phase": "night", "day": 20},
        "players": [{
            "prefab": "wilson", "health": 60, "maxhealth": 150,
            "hunger": 15, "sanity": 20, "temperature": 3,
            "inventory": {"火把": 1}, "nearby": {},
        }],
    }
    print("POST /state ->", requests.post(f"{BASE}:5002/state", json=snap).json())

    # 跑 dify_brain 单次（真调 Dify 工作流，最长等 180s）
    print("运行 dify_brain --once（调 Dify 工作流，可能需要 1~3 分钟）…")
    t0 = time.time()
    r = subprocess.run([sys.executable, "dify_brain.py", "--once"],
                       capture_output=True, text=True, timeout=300, encoding="utf-8", errors="replace")
    print("dify_brain 输出：")
    print(r.stdout[-2000:])
    if r.stderr:
        print("stderr:", r.stderr[-500:])
    print(f"耗时 {time.time()-t0:.1f}s")

    # 排空队列，找 source=dify 的建议
    print("\n排空 /advice 队列，查找 Dify 回灌的建议：")
    found = False
    for _ in range(20):
        a = requests.get(f"{BASE}:5002/advice").json()
        if not a:
            break
        src = a.get("source")
        if src == "dify":
            found = True
            print(f"  ✅ [Dify回灌] {a.get('message')}")
        else:
            print(f"  - [规则] {a.get('message')[:40]}")
    if not found:
        print("  ❌ 未发现 Dify 回灌的建议（工作流可能未产出或失败）")
        return 1
    print("\n闭环验证通过 ✅")
    return 0


if __name__ == "__main__":
    code = 1
    try:
        code = main()
    finally:
        for p in procs:
            p.terminate()
        sys.exit(code)
