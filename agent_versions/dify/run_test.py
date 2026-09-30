#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_test.py — 跑一次 Dify draft 工作流（console debugger 端点），打印节点执行链 + 最终输出。

用法：
  cd agent_versions/dify
  python run_test.py <app_id> "草帽怎么合成？"
"""
import json
import sys

import requests

from import_to_dify import make_auth, read_secret_key

BASE = "http://localhost/console/api"


def run(app_id, query):
    headers = make_auth(read_secret_key())
    r = requests.post(
        f"{BASE}/apps/{app_id}/workflows/draft/run",
        headers=headers,
        json={"inputs": {"query": query}},
        stream=True,
        timeout=180,
    )
    print("run HTTP", r.status_code)
    final = None
    for raw in r.iter_lines(decode_unicode=True):
        if not raw:
            continue
        if raw.startswith("event: "):
            evt = raw[len("event: "):]
            continue
        if raw.startswith("data: "):
            data = raw[len("data: "):]
            try:
                obj = json.loads(data)
            except Exception:
                continue
            # 只打印关键事件，避免刷屏
            etype = obj.get("event") or evt
            if etype in ("node_started", "node_finished"):
                d = obj.get("data", {})
                title = d.get("title") or d.get("node_id") or "?"
                status = d.get("status", "")
                err = d.get("error", "")
                outs = d.get("outputs")
                print(f"  [{etype}] {title} {status} {err}")
                if etype == "node_finished" and outs:
                    print(f"           outputs: {json.dumps(outs, ensure_ascii=False)[:600]}")
            elif etype == "workflow_finished":
                d = obj.get("data", {})
                final = d.get("outputs", {})
                print("  [workflow_finished] outputs:", json.dumps(final, ensure_ascii=False))
            elif etype in ("workflow_failed", "node_failed"):
                print("  [" + etype + "]", json.dumps(obj.get("data", {}), ensure_ascii=False)[:800])
    print("\n=== 最终输出 ===")
    print(json.dumps(final, ensure_ascii=False, indent=2) if final else "(无)")


if __name__ == "__main__":
    app_id = sys.argv[1]
    q = sys.argv[2] if len(sys.argv) > 2 else "草帽怎么合成？"
    run(app_id, q)
