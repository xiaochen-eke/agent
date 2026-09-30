#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""agent.py — LangGraph 版饥荒物品顾问（StateGraph：节点 + 条件边）。

对比点：
  - 三步显式建模成「节点 + 边」；
  - 条件分支用 add_conditional_edges + route 函数 + 映射表；
  - 状态在 TypedDict 里显式流转。

用法：
  cd agent_versions/langgraph
  pip install -r requirements.txt
  python agent.py "草帽怎么合成？"
  python agent.py "今天天气如何？"    # route 返回 "answer"，跳过 tool 节点
"""
import json
import os
import sys
from typing import TypedDict

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

from langchain_openai import ChatOpenAI            # noqa: E402
from langgraph.graph import StateGraph, START, END  # noqa: E402

llm = ChatOpenAI(
    model=os.getenv("ADVISOR_MODEL", "glm-4-flash"),
    base_url="https://open.bigmodel.cn/api/paas/v4/",
    api_key=os.getenv("ZHIPU_API_KEY", ""),
    temperature=0.2,
)

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


class State(TypedDict):
    query: str
    intent: str
    item: str
    tool_result: str
    answer: str


def node_intent(state: State):
    raw = llm.invoke([("system", INTENT_SYS), ("user", state["query"])]).content
    info = _parse_json(raw) or {"intent": "other", "item": ""}
    return {"intent": info.get("intent", "other"), "item": info.get("item", "")}


def node_tool(state: State):
    return {"tool_result": lookup(state["item"], state["intent"])}


def node_answer(state: State):
    user = f"问题：{state['query']}\n"
    if state.get("tool_result"):
        user += f"【物品信息】{state['tool_result']}"
    return {"answer": llm.invoke([("system", ANSWER_SYS), ("user", user)]).content}


def route(state: State):
    return "tool" if state["intent"] in ("recipe", "stats") else "answer"


builder = StateGraph(State)
builder.add_node("intent", node_intent)
builder.add_node("tool", node_tool)
builder.add_node("answer", node_answer)
builder.add_edge(START, "intent")
builder.add_conditional_edges("intent", route, {"tool": "tool", "answer": "answer"})
builder.add_edge("tool", "answer")
builder.add_edge("answer", END)
graph = builder.compile()


if __name__ == "__main__":
    q = sys.argv[1] if len(sys.argv) > 1 else "草帽怎么合成？"
    out = graph.invoke({"query": q})
    print(out["answer"])
