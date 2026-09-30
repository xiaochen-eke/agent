#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
Agent 工具调用实验 —— 基于 tool_calls 的自主决策 Agent
================================================================================

实验目的：
    1. 掌握基于 tool_calls（函数调用）的 Agent 决策机制
    2. 能够为 Agent 配备多个工具（本地检索、网络搜索、视觉理解）
    3. 实现 Agent 在 RAG 流程中的自主工具选择与失败重试逻辑

实验原理：
    Agent（智能体）是一种能够感知环境、进行自主决策并执行动作的系统。
    本实验在 RAG 架构之上引入 Agent 机制，使大模型从"被动回答"转变为"主动规划"。

    核心流程（ReAct 模式）：
        用户问题 → [Agent 大脑: GLM-4 + tool_calls]
                      ├── 工具1: 本地知识库检索 (local_search)
                      ├── 工具2: 网络搜索 (web_search)
                      └── 工具3: 视觉理解 (vision_tool)
                 → 工具执行 → 结果回传 → 失败检测 → 重试 → 最终答案

    三个工具：
        1. local_search:  基于 ChromaDB 向量数据库的混合检索
        2. web_search:    基于 DuckDuckGo 的网络搜索
        3. vision_tool:   基于 GLM-4V 的视觉理解

用法:
    python agent_main.py                    # 运行所有测试用例
    python agent_main.py --test 1           # 仅运行测试1: 文本问题
    python agent_main.py --test 2           # 仅运行测试2: 实时问题
    python agent_main.py --test 3           # 仅运行测试3: 图像问题
    python agent_main.py --interactive      # 交互模式
================================================================================
"""

import os
import sys
import argparse
import json
import time
from typing import Dict
from datetime import datetime

# 修复 Windows 控制台编码
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# 绕过代理
os.environ.setdefault('no_proxy', '*')
os.environ.setdefault('NO_PROXY', '*')

# ---- 加载 .env ----
def _load_dotenv():
    _here = os.path.dirname(os.path.abspath(__file__))
    _parent = os.path.dirname(_here)
    search_paths = [
        os.path.join(_here, '.env'),
        os.path.join(_here, 'config', '.env'),
        os.path.join(_parent, '.env'),
        os.path.join(_parent, 'backend', '.env'),
    ]
    for env_path in search_paths:
        if os.path.exists(env_path):
            with open(env_path, encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#') or '=' not in line:
                        continue
                    k, v = line.split('=', 1)
                    k, v = k.strip(), v.strip().strip('"').strip("'")
                    if k and k not in os.environ:
                        os.environ[k] = v
            break

_load_dotenv()

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.settings import ZHIPU_API_KEY
from src.agent.agent_loop import AgentLoop
from src.agent.tools import TOOL_DEFINITIONS


# ============================================================================
# 测试用例定义
# ============================================================================

TEST_CASES = [
    {
        "id": 1,
        "name": "文本问题 → 触发本地检索",
        "description": "测试 Agent 是否能自主选择 local_search 工具来回答知识性问题",
        "query": "什么是RAG？请详细解释其原理和应用场景。",
        "image_url": None,
        "expected_tool": "local_search",
        "expected_behaviour": "Agent 应识别这是一个知识性概念问题，"
                             "优先调用 local_search 工具检索本地知识库",
    },
    {
        "id": 2,
        "name": "实时问题 → 触发网络搜索",
        "description": "测试 Agent 是否能自主选择 web_search 工具来获取实时信息",
        "query": "今天天气如何？（请搜索北京今天的天气情况）",
        "image_url": None,
        "expected_tool": "web_search",
        "expected_behaviour": "Agent 应识别这是实时信息问题，"
                             "调用 web_search 工具进行网络搜索",
    },
    {
        "id": 3,
        "name": "图像问题 → 触发视觉工具",
        "description": "测试 Agent 是否能自主选择 vision_tool 来分析图片内容",
        "query": "这张图片里有什么动物？请详细描述图片内容。",
        "image_url": "https://images.pexels.com/photos/45201/kitty-cat-kitten-pet-45201.jpeg",
        "expected_tool": "vision_tool",
        "expected_behaviour": "Agent 应识别这是图像分析问题，"
                             "调用 vision_tool 工具进行视觉理解",
    },
]


# ============================================================================
# 输出格式化
# ============================================================================

def print_banner():
    today = datetime.now().strftime('%Y年%m月%d日 %H:%M')
    print(f"""
╔══════════════════════════════════════════════════════════════════════╗
║     Agent 工具调用实验 —— 基于 tool_calls 的自主决策 Agent           ║
║                                                                      ║
║     🕐 系统时间: {today:<51}║
║                                                                      ║
║  实验原理：                                                           ║
║    ReAct 模式: Thought → Action (工具调用) → Observation → Answer     ║
║                                                                      ║
║  三个工具：                                                           ║
║    ① local_search  — 本地知识库检索（向量数据库）                     ║
║    ② web_search    — 通用网络搜索（Bing → DuckDuckGo → GLM回退）     ║
║    ③ vision_tool   — 视觉理解（GLM-4V）                              ║
║                                                                      ║
║  核心特性：                                                           ║
║    • 模型自主决定调用哪个工具                                          ║
║    • 失败自动检测 + 切换工具重试                                       ║
║    • 全流程日志记录                                                   ║
╚══════════════════════════════════════════════════════════════════════╝
""")


def print_tool_schemas():
    """打印工具定义"""
    print("📋 工具 JSON Schema 定义:")
    print("─" * 70)
    for tool in TOOL_DEFINITIONS:
        print(f"\n  工具: {tool['function']['name']}")
        print(f"  描述: {tool['function']['description'][:100]}...")
        print(f"  参数: {json.dumps(tool['function']['parameters']['properties'], ensure_ascii=False, indent=4)}")
    print("─" * 70)


def print_tool_schemas_langchain(tools_list):
    """打印 LangChain @tool 定义"""
    print("📋 LangChain @tool 工具定义:")
    print("─" * 70)
    for t in tools_list:
        print(f"\n  工具: {t.name}")
        print(f"  描述: {t.description[:120]}...")
        if hasattr(t, 'args_schema') and t.args_schema:
            try:
                schema = t.args_schema.model_json_schema()
                props = schema.get('properties', {})
                for k, v in props.items():
                    print(f"  参数 {k}: {v.get('type', '?')} — {v.get('description', '')[:80]}")
            except Exception:
                print(f"  参数: (自动生成)")
    print("─" * 70)


def print_result(run_result: Dict, test_case: Dict, elapsed: float):
    """格式化打印运行结果"""
    print(f"\n{'━' * 70}")
    print(f"📊 测试结果 #{test_case['id']}: {test_case['name']}")
    print(f"{'━' * 70}")

    # 基本信息
    print(f"\n  【基本信息】")
    print(f"  问题: {test_case['query']}")
    if test_case.get('image_url'):
        print(f"  图片URL: {test_case['image_url']}")
    print(f"  期望工具: {test_case['expected_tool']}")
    print(f"  总耗时: {elapsed:.1f} 秒")

    # 工具调用记录
    print(f"\n  【工具调用记录】")
    tool_calls = run_result.get('tool_calls_made', [])
    if tool_calls:
        for i, tc in enumerate(tool_calls):
            print(f"  调用 #{i+1}: {tc['tool']}")
            print(f"    参数: {json.dumps(tc['args'], ensure_ascii=False)}")
            print(f"    结果预览: {tc.get('result_preview', '')[:150]}...")
    else:
        print(f"  (无工具调用 — 模型直接回答)")

    # 重试信息
    print(f"\n  【重试信息】")
    print(f"  重试次数: {run_result.get('retry_count', 0)}")
    print(f"  总推理轮次: {run_result.get('total_rounds', 0)}")

    # 最终答案
    print(f"\n  【最终答案】")
    answer = run_result.get('answer', '')
    print(f"  {answer}")

    # 工具日志
    print(f"\n  【工具调用详细日志】")
    logs = run_result.get('log', [])
    if logs:
        for entry in logs:
            print(f"  [{entry.get('timestamp', '?')}] {entry['tool']}: {entry.get('result_summary', '?')}")
    else:
        print(f"  (无日志)")

    # 验证
    print(f"\n  【验证】")
    actual_tools = [tc['tool'] for tc in tool_calls]
    expected = test_case['expected_tool']
    if expected in actual_tools:
        print(f"  ✅ Agent 正确选择了 {expected} 工具")
    elif actual_tools:
        print(f"  ⚠️ Agent 未选择期望的 {expected} 工具，而是选择了 {actual_tools}")
    else:
        print(f"  ⚠️ Agent 未调用任何工具")

    # 答案有效性
    ans = answer or ""
    if len(ans.strip()) < 10:
        print(f"  ❌ 答案过短/为空")
    elif any(kw in ans for kw in ['不知道', '无法回答', '无法获取']):
        print(f"  ⚠️ 答案可能不完整（含'不知道/无法回答'）")
    else:
        print(f"  ✅ 答案有效")


# ============================================================================
# 交互模式
# ============================================================================

def interactive_mode(agent: AgentLoop):
    """交互式 Agent 模式"""
    print("\n🔮 进入交互模式（输入 'quit' 或 'exit' 退出）\n")

    while True:
        try:
            user_input = input("👤 你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 再见!")
            break

        if not user_input:
            continue
        if user_input.lower() in ('quit', 'exit', 'q'):
            print("👋 再见!")
            break

        # 检查是否附加图片
        image_url = None
        if user_input.startswith("image:"):
            parts = user_input[6:].split(maxsplit=1)
            if len(parts) >= 2:
                image_url = parts[0].strip()
                query = parts[1].strip()
            else:
                print("⚠️ 用法: image: <URL> <问题>")
                continue
        else:
            query = user_input

        agent.reset()
        t0 = time.time()
        result = agent.run(query, image_url=image_url)
        elapsed = time.time() - t0

        print(f"\n🤖 Agent ({elapsed:.1f}s):")
        print(f"   {result['answer']}")
        print(f"   [工具调用: {len(result['tool_calls_made'])}次 | "
              f"重试: {result['retry_count']}次]")
        print()


# ============================================================================
# 主函数
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Agent 工具调用实验")
    parser.add_argument("--test", type=int, choices=[1, 2, 3],
                        help="仅运行指定的测试用例 (1/2/3)")
    parser.add_argument("--interactive", "-i", action="store_true",
                        help="交互模式")
    parser.add_argument("--no-retry", action="store_true",
                        help="禁用重试机制")
    parser.add_argument("--method", type=str, choices=["native", "langchain"],
                        default="native",
                        help="实现方式: native(原生JSON Schema) | langchain(LangChain @tool)")
    args = parser.parse_args()

    print_banner()

    # 初始化 Agent
    method_label = "原生 JSON Schema (方式A)" if args.method == "native" else "LangChain @tool (方式B)"
    print(f"🔧 正在初始化 Agent...（{method_label}）")

    if args.method == "langchain":
        from src.agent.agent_langchain import LangChainAgentWrapper, TOOLS_LC
        agent_wrapper = LangChainAgentWrapper(api_key=ZHIPU_API_KEY)
        # 兼容旧接口
        agent = agent_wrapper
        # 覆盖 tool schemas 显示
        print_tool_schemas_langchain(TOOLS_LC)
    else:
        agent = AgentLoop(api_key=ZHIPU_API_KEY)
        print_tool_schemas()

    # 交互模式
    if args.interactive:
        interactive_mode(agent)
        return

    # 选择测试用例
    if args.test:
        test_cases = [tc for tc in TEST_CASES if tc['id'] == args.test]
    else:
        test_cases = TEST_CASES

    # 运行测试
    all_results = []
    for tc in test_cases:
        print(f"\n{'=' * 70}")
        print(f"🧪 运行测试 #{tc['id']}: {tc['name']}")
        print(f"   描述: {tc['description']}")
        print(f"   期望行为: {tc['expected_behaviour']}")
        print(f"{'=' * 70}")

        if hasattr(agent, 'reset'):
            agent.reset()
        t0 = time.time()
        result = agent.run(tc['query'], image_url=tc.get('image_url'))
        elapsed = time.time() - t0

        print_result(result, tc, elapsed)
        all_results.append({
            "test": tc,
            "result": result,
            "elapsed": elapsed,
        })

    # 实验总结
    print(f"\n\n{'=' * 70}")
    print(f"📊 实验总结")
    print(f"{'=' * 70}")

    for i, r in enumerate(all_results):
        tc = r['test']
        result = r['result']
        tools_used = [c['tool'] for c in result.get('tool_calls_made', [])]
        correct_tool = tc['expected_tool'] in tools_used
        status = "✅" if correct_tool else "⚠️"
        print(f"\n  测试 #{tc['id']}: {status} {tc['name']}")
        print(f"     实际工具: {tools_used if tools_used else '(无)'}")
        print(f"     期望工具: {tc['expected_tool']}")
        print(f"     重试次数: {result['retry_count']}")
        print(f"     耗时: {r['elapsed']:.1f}s")
        print(f"     答案长度: {len(result.get('answer', ''))} 字符")

    print(f"\n{'=' * 70}")
    print("✅ 实验完成！")
    print(f"{'=' * 70}")
    print("\n💡 提示: 以上输出可直接截图作为实验报告的「实验结果与分析」部分。")


if __name__ == '__main__':
    main()
