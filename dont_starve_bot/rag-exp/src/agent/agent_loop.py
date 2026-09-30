# -*- coding: utf-8 -*-
"""
Agent 主循环（ReAct 模式）
==========================
实现基于 tool_calls（函数调用）的 Agent 决策机制：

核心流程（ReAct: Reasoning + Acting）：
  1. 用户提问 → 模型分析 → 决定调用哪个工具（或直接回答）
  2. 执行工具 → 将结果回传给模型
  3. 模型根据工具结果生成最终答案
  4. 失败检测 → 自动重试（切换工具）

架构：
  用户问题 → [Agent大脑: GLM-4 + tool_calls]
                ├── 工具1: 本地知识库检索 (local_search)
                ├── 工具2: 网络搜索 (web_search)
                └── 工具3: 视觉理解 (vision_tool)
           → 工具执行 → 结果回传 → 最终答案
"""

import json
import sys
import os
from typing import List, Dict, Optional, Callable
from datetime import datetime

from openai import OpenAI

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config.settings import ZHIPU_BASE_URL, ZHIPU_API_KEY
from src.agent.tools import (
    TOOL_DEFINITIONS,
    ToolImplementations,
    create_tool_map,
)

# ============================================================================
# 失败检测关键词
# ============================================================================

FAILURE_PATTERNS = [
    "我不知道",
    "我无法回答",
    "无法回答这个问题",
    "无法确定答案",
    "完全不清楚",
    "没有任何相关信息",
    "没有找到相关信息",
    "搜索失败",
    "检索失败",
    "未找到任何结果",
    "工具不可用",
    "暂无相关数据",
    "无法获取实时数据",
    "无法获取最新",
    "I don't know",
    "I cannot answer",
    "no results found",
    "not available at this time",
    "很抱歉，我无法",
    "抱歉，我无法获取",
]

EMPTY_ANSWER_THRESHOLD = 10  # 答案少于10个字符视为失败

RETRY_PROMPT = (
    "你刚才的回答未能有效解决问题。请尝试使用不同的工具或不同的查询方式重新获取信息。"
    "如果之前使用了本地检索，请尝试网络搜索；如果之前使用了网络搜索，请尝试本地检索。"
    "请务必调用一个工具来获取信息。"
)

MAX_RETRIES = 2  # 最多重试次数
MAX_TOOL_ROUNDS = 5  # 最多工具调用轮次（含最终回答轮次）


# ============================================================================
# Agent 主循环
# ============================================================================

class AgentLoop:
    """
    ReAct 模式 Agent 主循环

    核心机制：
      1. 将用户问题 + 工具定义发送给模型
      2. 模型返回 tool_calls（选择工具）或直接文本回答
      3. 若为 tool_calls：执行工具，将结果回传，循环至模型给出最终答案
      4. 检测答案失败 → 触发重试（切换工具）
    """

    def __init__(self, api_key: str = None):
        self.api_key = api_key or ZHIPU_API_KEY
        _timeout = httpx.Timeout(180.0, connect=30.0) if HAS_HTTPX else 180.0
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=ZHIPU_BASE_URL,
            timeout=_timeout,
            max_retries=3,
        )

        # 工具实现
        self.tools_impl = ToolImplementations(self.api_key)
        self.tool_map = create_tool_map(self.tools_impl)

        # Agent 使用的模型（需支持 tool_calls）
        self.agent_model = "glm-4-flash"

        # 对话历史（多轮）
        self.conversation_history: List[Dict] = []

        # 运行日志
        self.run_log: List[Dict] = []

    def _add_message(self, role: str, content, tool_calls=None, tool_call_id=None, name=None):
        """向对话历史中添加消息"""
        msg = {"role": role}
        if content is not None:
            msg["content"] = content
        if tool_calls is not None:
            msg["tool_calls"] = tool_calls
        if tool_call_id is not None:
            msg["tool_call_id"] = tool_call_id
        if name is not None:
            msg["name"] = name
        self.conversation_history.append(msg)

    def _call_model(self, tools: List[Dict] = None) -> dict:
        """
        调用大模型 API（含重试逻辑）
        返回: OpenAI ChatCompletionMessage
        """
        import time as _time
        kwargs = {
            "model": self.agent_model,
            "messages": self.conversation_history,
            "temperature": 0.7,
            "max_tokens": 2048,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        last_error = None
        for attempt in range(3):
            try:
                response = self.client.chat.completions.create(**kwargs)
                return response.choices[0].message
            except Exception as e:
                last_error = e
                if attempt < 2:
                    wait = (attempt + 1) * 5
                    print(f"   ⚠️ API 调用失败 (尝试 {attempt+1}/3): {e}")
                    print(f"      等待 {wait}s 后重试...")
                    _time.sleep(wait)

        print(f"   ❌ API 调用 3 次均失败: {last_error}")
        # 返回一个带失败消息的虚拟对象
        class _FakeMessage:
            content = "[Agent] 抱歉，我无法获取信息，API 请求超时。"
            tool_calls = None
        return _FakeMessage()

    def _is_failure(self, text: str) -> bool:
        """
        检测回答是否为失败回答
        返回 True 表示检测到失败，需要重试
        """
        if not text or len(text.strip()) < EMPTY_ANSWER_THRESHOLD:
            return True
        text_lower = text.lower()
        for pattern in FAILURE_PATTERNS:
            if pattern.lower() in text_lower:
                return True
        return False

    def _execute_tool(self, tool_name: str, tool_args: Dict) -> str:
        """执行指定的工具并返回结果"""
        func = self.tool_map.get(tool_name)
        if func is None:
            return f"❌ 未知工具: {tool_name}"

        print(f"   🔧 执行工具: {tool_name}")
        print(f"   📋 参数: {json.dumps(tool_args, ensure_ascii=False)}")

        try:
            result = func(**tool_args)
            print(f"   ✅ 工具执行完成 ({len(result)} 字符)")
            return result
        except Exception as e:
            error_msg = f"❌ 工具执行出错: {str(e)}"
            print(f"   {error_msg}")
            return error_msg

    def _single_round(self, tools: List[Dict]) -> Dict:
        tool_calls_made = []
        rounds = 0

        while rounds < MAX_TOOL_ROUNDS:
            rounds += 1
            print(f"\n   ── Agent 推理轮次 {rounds} ──")

            # 接近上限时，追加提示引导模型给出最终答案
            if rounds >= MAX_TOOL_ROUNDS - 1:
                self._add_message(
                    "user",
                    "【系统提示】这是最后一轮推理，请基于已有的工具结果直接给出最终答案，不要再调用工具。"
                )

            # 调用模型
            message = self._call_model(tools)

            # 情况1: 模型直接返回文本（无需调用工具）
            if message.content and not message.tool_calls:
                self._add_message("assistant", message.content)
                print(f"   💬 模型直接回答: {message.content[:150]}...")
                return {
                    "answer": message.content,
                    "tool_calls_made": tool_calls_made,
                    "rounds": rounds,
                }

            # 情况2: 模型请求调用工具
            if message.tool_calls:
                # 记录 assistant 的 tool_calls 消息
                self._add_message(
                    "assistant",
                    content=message.content,
                    tool_calls=[
                        {
                            "id": tc.id,
                            "type": tc.type,
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in message.tool_calls
                    ],
                )

                for tc in message.tool_calls:
                    tool_name = tc.function.name
                    try:
                        tool_args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        tool_args = {}

                    print(f"   🤔 模型选择工具: {tool_name}")
                    print(f"      query: {tool_args.get('query', tool_args.get('image_url', '?'))}")

                    # 执行工具
                    result = self._execute_tool(tool_name, tool_args)
                    tool_calls_made.append({
                        "tool": tool_name,
                        "args": tool_args,
                        "result_preview": result[:200],
                    })

                    # 将工具结果回传给模型
                    self._add_message(
                        "tool",
                        content=result,
                        tool_call_id=tc.id,
                        name=tool_name,
                    )

                # 工具执行完毕，添加提示引导模型作答（含日期红线）
                from datetime import datetime as _dt
                _today = _dt.now().strftime('%Y年%m月%d日')
                hint = (
                    '请基于以上工具返回的信息直接回答用户最初的问题。注意：'
                    f'今天是{_today}，只能使用搜索结果中的绝对日期，'
                    '严禁编造「1天前」「上周」等相对时间。请给出完整答案，不要再调用工具。'
                )
                self._add_message("user", hint)

                # 继续循环，让模型基于工具结果生成答案
                continue

            # 情况3: 模型返回空（异常）
            print(f"   ⚠️ 模型返回异常（无内容也无tool_calls）")
            return {
                "answer": "[Agent] 模型返回异常，无法获取有效回答。",
                "tool_calls_made": tool_calls_made,
                "rounds": rounds,
            }

        # 达到最大轮次
        print(f"   ⚠️ 达到最大工具调用轮次 ({MAX_TOOL_ROUNDS})")
        return {
            "answer": "[Agent] 达到最大工具调用轮次，请尝试简化问题。",
            "tool_calls_made": tool_calls_made,
            "rounds": rounds,
        }

    def run(self, user_query: str, image_url: str = None) -> Dict:
        """
        Agent 主入口

        参数:
            user_query: 用户问题
            image_url: 可选，图片URL（会触发视觉工具）

        返回:
            {
                "answer": str,           # 最终答案
                "tool_calls_made": list, # 工具调用记录
                "retry_count": int,      # 重试次数
                "total_rounds": int,     # 总推理轮次
                "log": list,             # 运行日志
            }
        """
        print(f"\n{'=' * 70}")
        print(f"🤖 Agent 启动")
        print(f"   用户问题: {user_query}")
        if image_url:
            print(f"   图片URL: {image_url}")
        print(f"{'=' * 70}")

        # 重置状态
        self.conversation_history = []
        self.tools_impl.call_log = []

        # ---- 构建初始消息 ----
        system_prompt = self._build_system_prompt()

        self._add_message("system", system_prompt)

        # 强制把今天日期注入用户消息，防止模型用训练截止日期生成搜索query
        today_tag = datetime.now().strftime('%Y年%m月%d日')
        if image_url:
            user_content = (
                f"【当前日期: {today_tag}】\n"
                f"用户问题: {user_query}\n"
                f"图片URL: {image_url}\n"
                f"请使用视觉理解工具分析这张图片，然后回答问题。"
            )
        else:
            user_content = f"【当前日期: {today_tag}】\n用户问题: {user_query}"

        self._add_message("user", user_content)

        # ---- 第一轮尝试 ----
        print(f"\n📡 第一轮 Agent 推理...")
        tools = TOOL_DEFINITIONS
        result = self._single_round(tools)

        answer = result.get("answer", "")
        all_tool_calls = result.get("tool_calls_made", [])
        total_rounds = result.get("rounds", 0)
        retry_count = 0

        # ---- 失败检测 + 重试 ----
        while self._is_failure(answer) and retry_count < MAX_RETRIES:
            retry_count += 1
            print(f"\n{'─' * 50}")
            print(f"🔄 检测到回答失败，启动第 {retry_count} 次重试...")
            print(f"   失败原因: 回答为空或包含'不知道/无法回答'等关键词")
            print(f"   当前回答预览: {answer[:200] if answer else '(空)'}")
            print(f"{'─' * 50}")

            # 记录之前的工具调用
            prev_tools = [tc["tool"] for tc in all_tool_calls]

            # 重试策略：添加重试提示
            self._add_message("user", RETRY_PROMPT)

            # 再次执行
            retry_result = self._single_round(tools)
            answer = retry_result.get("answer", "")
            all_tool_calls.extend(retry_result.get("tool_calls_made", []))
            total_rounds += retry_result.get("rounds", 0)

            print(f"\n   第 {retry_count} 次重试结果预览: {answer[:200]}...")

        # ---- 如果仍然失败，最终回退 ----
        if self._is_failure(answer):
            print(f"\n⚠️ {MAX_RETRIES} 次重试后仍无法获取有效答案，使用最终回退策略...")
            answer = self._fallback_answer(user_query, image_url)
            total_rounds += 1

        # ---- 汇总 ----
        print(f"\n{'=' * 70}")
        print(f"🏁 Agent 运行完成")
        print(f"   工具调用次数: {len(all_tool_calls)}")
        print(f"   重试次数: {retry_count}")
        print(f"   总推理轮次: {total_rounds}")
        print(f"   最终答案长度: {len(answer)} 字符")
        print(f"{'=' * 70}")

        return {
            "answer": answer,
            "tool_calls_made": all_tool_calls,
            "retry_count": retry_count,
            "total_rounds": total_rounds,
            "log": self.tools_impl.get_log(),
        }

    def _build_system_prompt(self) -> str:
        """构建系统提示词（ReAct 风格, 含日期红线）"""
        today_str = datetime.now().strftime('%Y年%m月%d日 %A')
        return (
            f"【真实日期】今天是 **{today_str}**。请牢牢记住。\n\n"
            "【身份】你是具备工具调用能力的 AI Agent，根据用户问题自主选择工具获取信息。\n\n"
            "## 可用工具\n"
            "1. **local_search**: 搜索本地知识库（向量语义+关键词混合检索）。\n"
            "   适用：概念解释、知识性问题、游戏攻略。\n"
            "2. **web_search**: 通用网络搜索（Bing→DuckDuckGo→GLM回退）。\n"
            "   适用：实时信息、最新新闻。\n"
            "3. **vision_tool**: 视觉理解（GLM-4V 图片分析）。\n"
            "   适用：图片分析。\n\n"
            "## !! 日期处理红线（违反即错误）\n"
            "- 只能输出搜索结果中**明确写出的绝对日期**（如\"2026年6月5日报道\"）\n"
            "- **绝对禁止**编造相对时间：\"1天前\"\"5小时前\"\"昨天\"\"上周\"——一律禁止\n"
            "- 搜索结果没写日期的，写\"（日期未标注）\"，不许猜测\n"
            "- 如果搜索结果日期距今天较远（如6月3日的结果，今天已是6月18日），如实标注，不要粉饰\n\n"
            "## 决策规则\n"
            "- 知识性/概念性问题 → local_search\n"
            "- 实时信息/新闻 → web_search\n"
            "- 图片分析 → vision_tool\n\n"
            "## 工具调用策略\n"
            "- 每次只调用1个工具，获取结果后立即综合回答\n"
            "- 最多调用2次工具\n\n"
            "## 回答格式\n"
            "- 注明信息来源\n"
            "- 新闻类逐条列出，每条带绝对日期"
        )

    def _fallback_answer(self, user_query: str, image_url: str = None) -> str:
        """
        最终回退策略：当所有工具和重试都失败后，
        直接调用 GLM 模型凭借其内部知识回答
        """
        print("   🔄 执行最终回退 (使用 GLM 内置知识)...")

        if image_url:
            prompt = (
                f"请根据你的知识回答以下问题。如果无法准确回答，请如实说明。\n\n"
                f"问题: {user_query}\n"
                f"（用户还提供了一张图片但无法分析: {image_url}）"
            )
        else:
            prompt = (
                f"请根据你的知识回答以下问题。如果无法准确回答，请如实说明。\n\n"
                f"问题: {user_query}"
            )

        try:
            response = self.client.chat.completions.create(
                model="glm-4-flash",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=2048,
            )
            answer = response.choices[0].message.content
            return f"[回退模式 - 基于模型内置知识]\n{answer}"
        except Exception as e:
            return (
                f"抱歉，多次尝试后仍无法回答您的问题「{user_query}」。\n"
                f"可能原因：网络连接问题、API不可用或知识库为空。\n"
                f"错误详情: {str(e)}"
            )

    def reset(self):
        """重置 Agent 状态"""
        self.conversation_history = []
        self.tools_impl.call_log = []
        self.run_log = []
