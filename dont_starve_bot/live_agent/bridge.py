#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bridge.py — 日志 ↔ HTTP 桥接进程

为什么需要它（面试可讲）：
  DST 的 mod 沙箱非常严格——io.open 只读且只能访问 data/ 目录、网络库不可靠，
  所以 mod 既不能写文件、也不能直接发 HTTP。桥接进程是普通 Python 进程、不受
  沙箱限制，负责把"游戏内"和"游戏外"两条世界接起来：

    1. 监听服务端日志里的 [DIFY_STATE] 行（mod 用 print 打状态）→ POST /state
    2. 把 AI 建议写进 <游戏>/data/dify_advice.json（mod 只读该文件）→ 游戏内播报
"""
import json
import os
import sys
import threading
import time

import requests

# 修复 Windows 控制台 GBK 编码问题
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

STATE_API = "http://127.0.0.1:5002"

# 建议/动作文件必须落在 mod 目录（mod 用 MODROOT 绝对路径读取，见 dst_mod/modmain.lua）
GAME_DATA_DIR = os.environ.get(
    "DST_GAME_DATA_DIR",
    r"C:\Program Files (x86)\Steam\steamapps\common\Don't Starve Together\mods\DifyCollector",
)
ADVICE_PATH = os.path.join(GAME_DATA_DIR, "dify_advice.json")
ACTION_PATH = os.path.join(GAME_DATA_DIR, "dify_action.json")

STATE_MARKER = "[DIFY_STATE]"
RESULT_MARKER = "[DIFY_ACT_RESULT]"


def find_master_log():
    """定位 master 分片（地上世界）的服务端日志。玩家在 master，状态从这里出。"""
    p = os.environ.get("DST_LOG")
    if p:
        return p
    home = os.path.expanduser("~")
    for rel in (
        ("Documents", "Klei", "DoNotStarveTogether"),
        ("OneDrive", "文档", "Klei", "DoNotStarveTogether"),
        ("OneDrive", "Documents", "Klei", "DoNotStarveTogether"),
    ):
        d = os.path.join(home, *rel, "master_server_log.txt")
        if os.path.exists(d):
            return d
    return os.path.join(home, "Documents", "Klei", "DoNotStarveTogether", "master_server_log.txt")


def push_state_loop():
    log_path = find_master_log()
    print(f"[bridge] 监听日志: {log_path}")
    last_ts = None
    pos = 0
    while True:
        try:
            size = os.path.getsize(log_path)
            if size < pos:          # 日志被截断（新开一局），从头读
                pos = 0
            with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                f.seek(pos)
                for line in f:
                    idx = line.find(STATE_MARKER)
                    if idx != -1:
                        data = json.loads(line[idx + len(STATE_MARKER):])
                        ts = data.get("ts")
                        if ts != last_ts:
                            requests.post(f"{STATE_API}/state", json=data, timeout=3)
                            last_ts = ts
                        continue
                    idx = line.find(RESULT_MARKER)
                    if idx != -1:
                        data = json.loads(line[idx + len(RESULT_MARKER):])
                        requests.post(f"{STATE_API}/action/result", json=data, timeout=3)
                        continue
                pos = f.tell()
        except FileNotFoundError:
            pos = 0
        except Exception as e:
            print(f"[bridge] push_state error: {e}")
        time.sleep(1)


def pull_advice_loop():
    last_written = None
    while True:
        try:
            r = requests.get(f"{STATE_API}/advice", timeout=3)
            if r.status_code == 200:
                advice = r.json()
                advice_id = advice.get("id")
                if advice.get("message") and advice_id != last_written:
                    # 写入 advice 文件：第一行 id，其余为 message（mod 按此格式读取）
                    with open(ADVICE_PATH, "w", encoding="utf-8") as f:
                        f.write(f"{advice_id}\n{advice['message']}")
                    last_written = advice_id
        except Exception as e:
            print(f"[bridge] pull_advice error: {e}")
        time.sleep(1)


def pull_action_loop():
    """轮询 state_api 的 /action 队列，把「可执行动作」写进 dify_action.json。

    文件格式：第一行 id，第二行 "verb prefab"，第三行 risk（low/medium/high）。
    mod 按此解析，无需 JSON 解码器。
    """
    last_written = None
    while True:
        try:
            r = requests.get(f"{STATE_API}/action", timeout=3)
            if r.status_code == 200:
                a = r.json()
                aid = a.get("id")
                if a.get("verb") and aid != last_written:
                    prefab = (a.get("prefab") or "").strip()
                    risk = (a.get("risk") or "low").strip()
                    with open(ACTION_PATH, "w", encoding="utf-8") as f:
                        f.write(f"{aid}\n{a['verb']} {prefab}\n{risk}")
                    last_written = aid
        except Exception as e:
            print(f"[bridge] pull_action error: {e}")
        time.sleep(1)


if __name__ == "__main__":
    print(f"[bridge] 建议文件: {ADVICE_PATH}")
    print(f"[bridge] 动作文件: {ACTION_PATH}")
    print(f"[bridge] 状态服务: {STATE_API}")
    threading.Thread(target=push_state_loop, daemon=True).start()
    threading.Thread(target=pull_advice_loop, daemon=True).start()
    threading.Thread(target=pull_action_loop, daemon=True).start()
    while True:
        time.sleep(10)
