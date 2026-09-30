#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""import_to_dify.py — 把三版对比项目的 Dify 工作流通过 console API 导入（自托管，自签 JWT）。

原理：从 docker-api 容器读 SECRET_KEY，自签 console API JWT（同 build_demo_v9.py 的套路），
调用 Dify 官方导入端点 POST /console/api/apps/imports，让 Dify 自己把 DSL 归一化成内部格式。

用法：
  cd agent_versions/dify
  python import_to_dify.py workflow.deepseek.yml "饥荒物品顾问(deepseek)"
"""
import json
import subprocess
import sys
import time

import jwt
import requests

API_CONTAINER = "docker-api-1"
AID = "e4d0a9a4-5052-4262-9a10-9dd1430f2a5e"   # 控制台用户 id（沿用现有 demo 的创建者）
BASE = "http://localhost/console/api"


def read_secret_key():
    out = subprocess.run(
        ["docker", "exec", API_CONTAINER, "sh", "-c", "cat /app/api/storage/.dify_secret_key"],
        capture_output=True, text=True,
    )
    sk = out.stdout.strip()
    if not sk:
        raise RuntimeError(f"读不到 SECRET_KEY: {out.stderr}")
    return sk


def make_auth(sk):
    exp = int(time.time()) + 3600
    access = jwt.encode(
        {"user_id": AID, "exp": exp, "iss": "SELF_HOSTED", "sub": "Console API Passport"},
        sk, algorithm="HS256",
    )
    csrf = jwt.encode({"exp": exp, "sub": AID}, sk, algorithm="HS256")
    return {
        "Authorization": "Bearer " + access,
        "X-CSRF-Token": csrf,
        "Cookie": "csrf_token=" + csrf,
        "Content-Type": "application/json",
    }


def import_app(yaml_path, name):
    sk = read_secret_key()
    headers = make_auth(sk)
    yaml_content = open(yaml_path, encoding="utf-8").read()

    payload = {
        "mode": "yaml-content",
        "yaml_content": yaml_content,
        "name": name,
        "description": "饥荒物品顾问（Dify 版）——三版本 Agent 对比示例",
        "icon": "🎒",
        "icon_background": "#FFEAD5",
    }
    r = requests.post(f"{BASE}/apps/imports", headers=headers, json=payload, timeout=60)
    print("import HTTP", r.status_code)
    body = r.json()
    print(json.dumps(body, ensure_ascii=False, indent=2)[:1500])

    # 202 = 待确认（有依赖），调 confirm 完成导入
    if r.status_code == 202:
        import_id = body.get("id") or body.get("import_id")
        if import_id:
            r2 = requests.post(f"{BASE}/apps/imports/{import_id}/confirm", headers=headers, timeout=60)
            print("confirm HTTP", r2.status_code)
            print(json.dumps(r2.json(), ensure_ascii=False, indent=2)[:1500])
            body = r2.json()

    app_id = body.get("app_id")
    if app_id:
        print("\n[OK] 导入完成，App id =", app_id)
        print("   控制台地址 = http://localhost/app/" + app_id + "/workflow")
    else:
        print("\n[FAIL] 未拿到 app_id，看上面的错误信息。")
    return app_id


if __name__ == "__main__":
    yaml_path = sys.argv[1] if len(sys.argv) > 1 else "workflow.deepseek.yml"
    name = sys.argv[2] if len(sys.argv) > 2 else "饥荒物品顾问(deepseek)"
    import_app(yaml_path, name)
