import requests
import json
import os
import sys

ZHIPU_API_KEY = os.getenv("ZHIPU_API_KEY")

def call_zhipu_api(messages, model="glm-4-flash", tools=None):
    url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"

    headers = {
        "Authorization": ZHIPU_API_KEY,
        "Content-Type": "application/json"
    }

    data = {
        "model": model,
        "messages": messages,
        "temperature": 1.0
    }

    if tools:
        data["tools"] = tools
        data["tool_choice"] = "auto"

    response = requests.post(url, headers=headers, json=data)

    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"API调用失败: {response.status_code}, {response.text}")

# ============================================================
# Step06: 使用 Tools 数组（原生 Function Calling）的 Agent
# ============================================================
# 核心变化（与 step05 对比）：
#   step05: system prompt 约束模型输出"命令:"/"完成:" → 字符串切割 → 执行
#   step06: API 原生 tools 参数定义工具 → 模型返回结构化 tool_calls → 直接调用
#
# 为什么 tools 数组更规范：
#   1.【可靠性】模型输出结构化 JSON，不会出现格式错误
#   2.【参数提取】模型直接返回 {"command": "dir"}，无需解析字符串
#   3.【多工具选择】模型通过 function name 精确指定工具
#   4.【安全性】只能调用预定义的工具白名单
#   5.【业界标准】OpenAI / 智谱 / Claude 全部支持
#
# 使用方式：
#   python step06.py                        → 默认：小A（buddy）
#   python step06.py --persona buddy        → 小A（热心伙伴）
#   python step06.py --persona teacher      → 王老师（教学风格）
#   python step06.py --persona strict       → SysAdmin（简洁专业）
# ============================================================

# ---- 工具定义（tools 数组） ----
# 所有可用工具在此定义，模型只能调用这里列出的工具
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "execute_command",
            "description": "在 Windows 系统上执行一条命令并返回结果。当用户需要创建文件、查看目录、读取文件内容、或执行任何系统操作时，调用此工具。",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "要执行的 Windows 命令，例如 'dir'、'type hello.py'、'echo hello > test.txt'"
                    }
                },
                "required": ["command"]
            }
        }
    }
]

# ---- 工具执行器 ----
# 根据 tool_calls 中 function name 分发到对应的执行函数
def execute_tool_call(tool_call):
    func_name = tool_call["function"]["name"]
    func_args = json.loads(tool_call["function"]["arguments"])

    if func_name == "execute_command":
        command = func_args["command"]
        try:
            result = os.popen(command).read()
            return f"命令 '{command}' 执行结果:\n{result}" if result else f"命令 '{command}' 执行成功（无输出）"
        except Exception as e:
            return f"命令 '{command}' 执行异常: {e}"

    return f"未知工具: {func_name}"

# ---- 人设配置（V2 人设文件，不含命令格式约束） ----
PERSONA_CONFIG = {
    "buddy":   ("小A - 你的电脑管家",     "Agent_v2.md",           "拜拜！有需要随时找我哦~ 👋"),
    "teacher": ("王老师 - 计算机教学助手", "persona_teacher_v2.md",  "下课！回去记得复习今天的知识点哦~"),
    "strict":  ("SysAdmin - 系统管理员",   "persona_strict_v2.md",   "会话结束。"),
}

persona_name = "buddy"
args = sys.argv[1:]
for i, arg in enumerate(args):
    if arg == "--persona" and i + 1 < len(args):
        persona_name = args[i + 1]

if persona_name not in PERSONA_CONFIG:
    print(f"错误：未知的人设 '{persona_name}'")
    print(f"可用人设: {', '.join(PERSONA_CONFIG.keys())}")
    print("用法: python step06.py --persona <人设名>")
    sys.exit(1)

display_name, persona_file, goodbye_msg = PERSONA_CONFIG[persona_name]

if not os.path.exists(persona_file):
    print(f"错误：人设文件 '{persona_file}' 不存在")
    sys.exit(1)

messages = [{"role": "system", "content": open(persona_file, encoding="utf-8").read()}]

print("=" * 60)
print(f"🤖 Agent 人设已加载：{display_name}")
print(f"   工具模式: 原生 Function Calling（{len(TOOLS)} 个工具）")
print(f"   可用工具: {', '.join(t['function']['name'] for t in TOOLS)}")
print(f"   切换人设: python step06.py --persona buddy|teacher|strict")
print("=" * 60)

# =============================================
# Agent 主循环
# =============================================
while True:
    user_input = input("\n你: ")
    if user_input.lower() in ["退出", "exit", "quit"]:
        print(f"Agent: {goodbye_msg}")
        break
    messages.append({"role": "user", "content": user_input})

    while True:
        try:
            result = call_zhipu_api(messages, tools=TOOLS)
        except Exception as e:
            print(f"[ERROR] API 调用异常: {e}")
            break

        if not result.get("choices"):
            print("[ERROR] API 返回异常：choices 为空")
            break

        msg = result["choices"][0]["message"]
        finish_reason = result["choices"][0].get("finish_reason", "")

        # ---- 情况1: 模型要调用工具 ----
        if msg.get("tool_calls"):
            messages.append(msg)

            for tc in msg["tool_calls"]:
                func_name = tc["function"]["name"]
                func_args = tc["function"]["arguments"]
                print(f"[Tool] 调用 {func_name}({func_args})")

                tool_result = execute_tool_call(tc)

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": tool_result
                })
            continue  # 继续循环，让模型根据工具结果决定下一步

        # ---- 情况2: 模型直接回复文本（不需要工具，任务完成） ----
        if msg.get("content"):
            messages.append(msg)
            print(f"Agent: {msg['content']}")
            break

        # ---- 异常 ----
        print(f"[ERROR] 模型返回异常：content 和 tool_calls 均为空")
        print(f"[DEBUG] finish_reason={finish_reason}, msg={json.dumps(msg, ensure_ascii=False)}")
        break
