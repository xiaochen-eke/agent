"""
Agent 搜索封装器 — 把 search_agent.py 的工具调用循环封装成可直接调用的类
用于 Flask 后端 API 和前端集成
"""

import os
import sys
import json
import time
from typing import Dict, List

# 绕过系统代理，避免 SSL 错误
os.environ.setdefault('no_proxy', '*')
os.environ.setdefault('NO_PROXY', '*')

# ========== 导入 Agent 模块 ==========
_AGENT_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "Agent")
)
if _AGENT_DIR not in sys.path:
    sys.path.insert(0, _AGENT_DIR)


class SearchAgentWrapper:
    """
    封装 search_agent.py 的工具调用循环，提供同步 search() 方法。
    返回：answer + 每步的工具调用信息（用于前端展示）
    """

    def __init__(self, api_key: str, base_dir: str = None):
        self.api_key = api_key
        self.base_dir = base_dir or os.getcwd()

        import search_agent as agent_module
        agent_module.ZHIPU_API_KEY = api_key
        self.agent = agent_module

        # 修复 web_search: 使用 glm-4-flash (支持内置 web_search 工具)
        self._patch_web_search()
        # 注入 API 超时
        self._patch_call_api()

    def _patched_web_search(self, query: str, max_results: int = 3) -> str:
        """修复版 web_search — 自动加饥荒关键词 + 精简结果"""
        # 如果查询和饥荒相关，加上饥荒限定范围
        if not any(k in query.lower() for k in ['饥荒', "don't starve", 'dont starve']):
            query = f"饥荒 Don't Starve {query}"

        try:
            search_prompt = (
                f"请搜索以下内容，用简洁的列表给出最相关的 {max_results} 条结果。\n"
                f"搜索词: {query}\n\n"
                f"每条结果格式: 标题 + 一句摘要（不超过50字）"
            )

            result = self.agent.call_zhipu_api(
                [{"role": "user", "content": search_prompt}],
                model="glm-4-flash",
                tools=[{"type": "web_search", "web_search": {"enable": True}}]
            )

            msg = result.get("choices", [{}])[0].get("message", {})
            content = msg.get("content", "")

            if content:
                # 精简结果，给主模型足够上下文空间
                clipped = content[:600]
                return f"【搜索结果】{clipped}"
            elif msg.get("tool_calls"):
                return f"网页搜索 '{query}' 已执行，请查看结果"
            return f"网页搜索 '{query}' 无结果，请尝试换个关键词"

        except Exception as e:
            return f"❌ 网页搜索失败: {str(e)}"

    def _patch_call_api(self):
        """给 API 调用加超时 + 绕过代理"""
        _original = self.agent.call_zhipu_api

        def _call_with_timeout(messages, model="glm-4-flash", tools=None):
            import requests as _requests
            url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
            headers = {
                "Authorization": self.api_key,
                "Content-Type": "application/json"
            }
            data = {"model": model, "messages": messages, "temperature": 0.7}
            if tools:
                data["tools"] = tools
                data["tool_choice"] = "auto"
            # 连接 30s，读取 120s（含搜索结果时模型需要更长时间）
            response = _requests.post(url, headers=headers, json=data,
                                      timeout=(30, 120),
                                      proxies={"http": None, "https": None})
            if response.status_code == 200:
                return response.json()
            raise Exception(f"API调用失败: {response.status_code}, {response.text[:200]}")

        self.agent.call_zhipu_api = _call_with_timeout

    def _fallback_answer(self, query: str, steps: list) -> str:
        """让模型基于搜索结果直接回答（不带工具）"""
        # 把搜索结果拼进问题一起发给模型
        search_context = ""
        for s in steps:
            search_context += f"\n【{s['tool']} 结果】\n{s['result_preview']}"

        msgs = [
            {"role": "system", "content": "你是小搜，一个搜索助手。下面有搜索结果，请根据结果总结回答用户问题，不要编造。如果结果不相关就诚实说。"},
            {"role": "user", "content": f"问题: {query}\n\n{search_context}\n\n请根据以上搜索结果回答。"},
        ]
        try:
            result = self.agent.call_zhipu_api(msgs, model="glm-4-flash")
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            return content or f"很抱歉，没有搜到关于「{query}」的相关信息。"
        except Exception:
            return f"很抱歉，搜索「{query}」超时，请稍后重试。"

    def _patch_web_search(self):
        """将 web_search 工具替换为修复版"""
        self.agent.TOOL_EXECUTORS["web_search"] = (
            lambda args: self._patched_web_search(**args)
        )

    def search(self, query: str, max_turns: int = 3) -> Dict:
        """
        执行 Agent 搜索

        Returns:
            {
                "answer": str,              # 最终回答
                "steps": [{"tool": "...", "args": {...}, "result_preview": "..."}],
                "tool_calls_count": int,
                "elapsed_ms": int
            }
        """
        start_time = time.time()
        steps = []

        system_content = (
            self.agent.SEARCH_PERSONA +
            "\n\n【重要规则】\n"
            "1. 每次收到工具返回的搜索结果后，你必须立即用中文总结回答用户问题，不要再调用工具。\n"
            "2. 如果搜索结果不相关，就诚实告诉用户并给出建议，不要反复搜索。\n"
            "3. 最多调用一次搜索工具，之后必须给出最终回答。"
        )
        messages = [{"role": "system", "content": system_content}]
        messages.append({"role": "user", "content": query})

        answer = ""
        remaining_turns = max_turns

        try:
            while remaining_turns > 0:
                remaining_turns -= 1

                result = self.agent.call_zhipu_api(
                    messages, tools=self.agent.TOOLS
                )

                if not result.get("choices"):
                    answer = "⚠️ API 返回异常，请稍后重试"
                    break

                msg = result["choices"][0]["message"]

                # 模型要求调用工具
                if msg.get("tool_calls"):
                    # 如果已经搜过一轮了，不再执行更多工具，强制回答
                    if steps:
                        answer = self._fallback_answer(query, steps)
                        break

                    messages.append(msg)
                    for tc in msg["tool_calls"]:
                        func_name = tc["function"]["name"]
                        try:
                            func_args = json.loads(tc["function"]["arguments"])
                        except json.JSONDecodeError:
                            func_args = {"raw": tc["function"]["arguments"]}

                        tool_result = self.agent.execute_tool_call(tc)

                        preview = tool_result[:500] + (
                            "..." if len(tool_result) > 500 else ""
                        )
                        steps.append({
                            "tool": func_name,
                            "args": func_args,
                            "result_preview": preview,
                        })

                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": tool_result,
                        })
                    continue

                # 模型返回最终回答
                if msg.get("content"):
                    messages.append(msg)
                    answer = msg["content"]
                    break

                # 也没 tool_calls 也没 content
                # 有搜索结果 → 让模型强制回答
                if steps:
                    answer = self._fallback_answer(query, steps)
                else:
                    answer = "⚠️ 模型返回为空，请重试"
                break

            if not answer:
                # 已经搜过了但模型还不回答 → 强制终结：不带工具让模型直接回答
                if steps:
                    answer = self._fallback_answer(query, steps)
                elif remaining_turns == 0:
                    answer = self._fallback_answer(query, steps)

        except Exception as e:
            answer = f"❌ Agent 搜索异常: {str(e)}"

        elapsed_ms = int((time.time() - start_time) * 1000)

        return {
            "answer": answer,
            "steps": steps,
            "tool_calls_count": len(steps),
            "elapsed_ms": elapsed_ms,
        }
