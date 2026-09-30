#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
native_agent.py — 原生多智能体大脑（不依赖 Dify 平台）

纯 Python 手写「规划 → 检索 → 执行 → 反思」四个 agent，直接调智谱 GLM
（OpenAI 兼容 SDK）。数据来自两个自建服务：
  - 实时状态：state_api (:5002)  /current_state
  - 静态百科：game_data_api (:5001) /api/game-data/search

面试要点：没有用任何编排框架，能逐行讲清 Agent 的每个环节——
为什么拆成 4 个角色、各自输入输出是什么、工具怎么被调用、结果怎么被校验。

用法：
  python native_agent.py "我想活到冬天"     # 按需问答
  python native_agent.py                    # 默认目标「生存下去」
"""

import json
import os
import sys

import requests
from openai import OpenAI

# 修复 Windows 控制台 GBK 编码
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# 加载 .env 文件（不依赖 python-dotenv），供 ZHIPU_API_KEY 使用
def _load_dotenv(path=None):
    if path is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    if not os.path.exists(path):
        return
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v
_load_dotenv()

# Phase 3：复用 dify_brain 的动作决策 + 风险白名单（纯 GLM + state_api，不依赖 Dify）
from dify_brain import extract_action, push_action

# ============ 配置 ============
API_KEY = os.getenv("ZHIPU_API_KEY", "")
BASE_URL = "https://open.bigmodel.cn/api/paas/v4/"
MODEL_STRONG = os.getenv("LIVE_AGENT_STRONG_MODEL", "glm-4-flash")  # 规划 / 反思
MODEL_FAST = os.getenv("LIVE_AGENT_FAST_MODEL", "glm-4-flash")      # 检索改写 / 执行

STATE_API = "http://127.0.0.1:5002"
GAME_API = "http://127.0.0.1:5001"

VERBOSE = os.getenv("LIVE_AGENT_VERBOSE", "1") == "1"


def log(role, text):
    if VERBOSE:
        print(f"\n  ── [{role}] ──\n{text.strip()}")


# ============ LLM 封装 ============
class LLM:
    def __init__(self):
        if not API_KEY:
            raise RuntimeError("未设置 ZHIPU_API_KEY 环境变量")
        self.client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

    def chat(self, model, system, user, temperature=0.3):
        resp = self.client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
        )
        return resp.choices[0].message.content

    def chat_json(self, model, system, user):
        text = self.chat(model, system, user)
        # 容忍模型输出 markdown 代码块
        t = text.strip()
        if t.startswith("```"):
            t = t.split("```", 2)[1]
            if t.startswith("json"):
                t = t[4:]
        try:
            return json.loads(t)
        except Exception:
            start, end = t.find("{"), t.rfind("}")
            if start != -1 and end > start:
                try:
                    return json.loads(t[start:end + 1])
                except Exception:
                    return {"raw": text}
            return {"raw": text}


# ============ 多智能体 ============
class LiveAgent:
    def __init__(self):
        self.llm = LLM()

    # ---- 工具：读实时状态 ----
    def get_current_state(self):
        r = requests.get(f"{STATE_API}/current_state", timeout=5).json()
        return r

    # ---- 工具：查静态百科 ----
    def search_knowledge(self, query):
        try:
            r = requests.get(
                f"{GAME_API}/api/game-data/search",
                params={"q": query, "category": "all"},
                timeout=5,
            ).json()
        except Exception:
            return ""
        if r.get("status") != "success":
            return ""
        return self._flatten(r.get("results", {}))

    @staticmethod
    def _flatten(results):
        """把 search 结果压成紧凑文本片段"""
        parts = []
        for cat, items in results.items():
            if not isinstance(items, dict):
                continue
            for name, data in items.items():
                desc = data.get("description", "")
                uses = data.get("uses", [])
                extra = ""
                if uses:
                    extra = " 用途:" + "/".join(uses)
                parts.append(f"【{cat}】{name}: {desc}{extra}")
        return "\n".join(parts)

    # ---- 1. 规划 agent ----
    def plan(self, state_summary, goal):
        system = (
            "你是《饥荒》生存规划专家。根据玩家当前实时状态，把生存目标拆解成 2~4 个"
            "最紧迫的子目标（例如：恢复精神、准备光源、寻找食物）。"
            '只输出 JSON，格式：{"sub_goals": ["子目标1", "子目标2"]}'
        )
        user = f"玩家目标：{goal}\n当前状态：\n{state_summary}"
        result = self.llm.chat_json(MODEL_STRONG, system, user)
        log("① 规划 Planner", json.dumps(result, ensure_ascii=False, indent=2))
        return result

    # ---- 2. 检索 agent ----
    def retrieve(self, needs):
        """把子目标改写为搜索词 → 调静态百科 → 聚合知识"""
        if not needs:
            return ""
        system = (
            "把每个生存子目标改写为 1~3 个用于百科搜索的中文【短关键词】（2~4 字，"
            "像词典词条那样，不要整句）。例如「寻找食物」→「食物」「浆果」「烹饪锅」；"
            "「准备光源」→「营火」「火把」；「保持体温」→「体温」「保暖」。"
            '只输出 JSON，格式：{"queries": ["关键词1", "关键词2"]}'
        )
        result = self.llm.chat_json(
            MODEL_FAST, system, json.dumps({"needs": needs}, ensure_ascii=False)
        )
        queries = result.get("queries", needs) if isinstance(result, dict) else needs

        knowledge = []
        for q in queries:
            snippet = self.search_knowledge(q)
            if snippet:
                knowledge.append(snippet)
        text = "\n\n".join(knowledge)
        log("② 检索 Retriever", f"搜索词:{queries}\n命中知识:\n{text[:600]}")
        return text

    # ---- 3. 执行 agent ----
    def execute(self, state_summary, knowledge, plan):
        system = (
            "你是《饥荒》行动决策专家。结合当前状态、检索到的百科知识、规划的子目标，"
            "给出玩家现在最该做的【一件具体可执行的事】。"
            '只输出 JSON，格式：{"action": "具体行动", "priority": 1, "reason": "理由"}'
        )
        user = (
            f"规划：{json.dumps(plan, ensure_ascii=False)}\n"
            f"知识：\n{knowledge}\n\n当前状态：\n{state_summary}"
        )
        result = self.llm.chat_json(MODEL_FAST, system, user)
        log("③ 执行 Executor", json.dumps(result, ensure_ascii=False, indent=2))
        return result

    # ---- 4. 反思 agent ----
    def reflect(self, state_summary, action):
        system = (
            "你是《饥荒》反思校验专家。校验该行动是否可行：材料是否够、当前是否安全、"
            "是否符合状态，指出风险并给出最终一句话建议。"
            '只输出 JSON，格式：{"final_advice": "一句话建议", "confidence": 0.8, "risks": ["风险"]}'
        )
        user = f"行动：{json.dumps(action, ensure_ascii=False)}\n当前状态：\n{state_summary}"
        result = self.llm.chat_json(MODEL_STRONG, system, user)
        log("④ 反思 Reflector", json.dumps(result, ensure_ascii=False, indent=2))
        return result

    # ---- 主流程 ----
    def advise(self, goal="生存下去"):
        state = self.get_current_state()
        summary = state.get("summary", "")
        if state.get("status") == "empty":
            return "还没有收到游戏状态，请先进游戏跑起来。"

        plan = self.plan(summary, goal)
        needs = (plan.get("sub_goals") or plan.get("needs") or []) if isinstance(plan, dict) else []
        knowledge = self.retrieve(needs)
        action = self.execute(summary, knowledge, plan)
        reflection = self.reflect(summary, action)

        reflection = reflection if isinstance(reflection, dict) else {}
        action = action if isinstance(action, dict) else {}
        final = reflection.get("final_advice") or action.get("action") or "继续观察。"
        confidence = reflection.get("confidence", action.get("priority", "?"))

        # Phase 3：把最终建议映射成可执行动作并推入队列（复用 dify_brain 的白名单校验）
        exec_act = extract_action(final, "", state)
        if exec_act:
            if push_action(exec_act["verb"], exec_act["prefab"]):
                final += f"（已推动作 {exec_act['verb']} {exec_act['prefab']}）"
        return f"{final}（置信度 {confidence}）"


if __name__ == "__main__":
    goal = sys.argv[1] if len(sys.argv) > 1 else "生存下去"
    print(f"目标：{goal}\n正在运行多智能体链路…")
    try:
        agent = LiveAgent()
        print("\n" + "=" * 40)
        print("最终建议：", agent.advise(goal))
        print("=" * 40)
    except RuntimeError as e:
        print(f"❌ {e}")
    except Exception as e:
        print(f"❌ 运行出错：{e}")
