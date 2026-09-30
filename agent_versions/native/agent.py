#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""agent.py — 原生版饥荒物品顾问（零框架）。

对比点：
  - 控制流是显式 if/elif；
  - 工具是直接 import 本地函数 lookup()；
  - LLM 是 requests 直调智谱 OpenAI 兼容端点，无任何编排/agent 框架。

用法：
  cd agent_versions/native
  python agent.py "草帽怎么合成？"
  python agent.py "木甲防御多少？"
  python agent.py "今天天气如何？"    # 走 other 分支，跳过工具
"""
import json
import os
import sys

import requests

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from shared.items_db import lookup  # noqa: E402

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def _load_dotenv(path=None):
    if path is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "shared", ".env")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v


_load_dotenv()

API_KEY = os.getenv("ZHIPU_API_KEY", "")
URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
MODEL = os.getenv("ADVISOR_MODEL", "glm-4-flash")

INTENT_SYS = (
    "你是《饥荒》物品顾问。判断用户问题属于哪类，并提取物品名。"
    "recipe=问某物品怎么合成/怎么做；stats=问属性/效果/数值；other=与物品无关。"
    '只输出 JSON，格式：{"intent": "recipe|stats|other", "item": "物品名(other 时空)"}'
)
ANSWER_SYS = (
    "你是《饥荒》生存顾问兼物品顾问，已接入玩家正在游玩的《饥荒》游戏：你给出的动作会被系统"
    "自动下发并执行到角色身上。有【物品信息】就据此回答；没有物品信息（例如问生存攻略、"
    "怎么活下去、或要你操作/控制角色）时，直接给出一个具体动作，指明让角色去吃的食物、"
    "去装备的物品、去采集/砍/挖/攻击的目标（如：吃浆果、装备火把、砍树、攻击蜘蛛）。"
    "回答以「让角色……」开头陈述动作即可。"
)


def glm(messages, temperature=0.2):
    r = requests.post(
        URL,
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        json={"model": MODEL, "messages": messages, "temperature": temperature},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def _parse_json(text):
    """容忍 markdown 代码块 / 前后杂质，解析 JSON dict；失败返回 None。"""
    t = (text or "").strip()
    if t.startswith("```"):
        t = t.split("```", 2)[1]
        if t.lstrip().startswith("json"):
            t = t.lstrip()[4:]
        t = t.strip()
    try:
        return json.loads(t)
    except Exception:
        start, end = t.find("{"), t.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(t[start:end + 1])
            except Exception:
                return None
        return None


def detect_intent(query):
    raw = glm([{"role": "system", "content": INTENT_SYS}, {"role": "user", "content": query}])
    return _parse_json(raw) or {"intent": "other", "item": ""}


def answer(query, tool_result=None):
    user = f"问题：{query}\n" + (f"【物品信息】{tool_result}" if tool_result else "")
    return glm([{"role": "system", "content": ANSWER_SYS}, {"role": "user", "content": user}])


def run(query):
    info = detect_intent(query)
    intent, item = info.get("intent", "other"), info.get("item", "")
    if intent == "other":          # 条件分支：跳过工具
        return answer(query)
    result = lookup(item, intent)  # 工具调用（直接 import dict）
    return answer(query, result)


if __name__ == "__main__":
    q = sys.argv[1] if len(sys.argv) > 1 else "草帽怎么合成？"
    print(run(q))
