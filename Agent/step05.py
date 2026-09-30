import requests
import json
import os
import sys

ZHIPU_API_KEY = os.getenv("ZHIPU_API_KEY")
def call_zhipu_api(messages, model="glm-4-flash"):
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

    response = requests.post(url, headers=headers, json=data)

    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"API调用失败: {response.status_code}, {response.text}")

# ============================================================
# Step05: 带人设的 Agent（支持人设切换）
# ============================================================
# 核心变化：
# Agent.md 中不再只有功能指令，而是加入了【身份定义 + 行为准则】
# 这就是给人设的方式——在 system message 中定义角色的性格、风格和行为规范
#
# 人设的三层结构：
#   第一层：身份定义   → "你是谁"（名字、性格、风格）
#   第二层：行为准则   → "什么能做/不能做"（安全边界、交流规则）
#   第三层：功能指令   → "怎么输出"（命令:/完成: 格式约束）
#
# 人设切换：
#   python step05.py                        → 默认人设：小A（buddy）
#   python step05.py --persona buddy        → 小A（热心伙伴）
#   python step05.py --persona teacher      → 王老师（教学风格）
#   python step05.py --persona strict       → SysAdmin（简洁专业）
# ============================================================

# 人设配置表：key 是命令行参数值，value 是 (人设名称, 人设文件名, 退出时的告别语)
PERSONA_CONFIG = {
    "buddy":   ("小A - 你的电脑管家", "Agent.md",           "拜拜！有需要随时找我哦~ 👋"),
    "teacher": ("王老师 - 计算机教学助手", "persona_teacher.md", "下课！回去记得复习今天的知识点哦~"),
    "strict":  ("SysAdmin - 系统管理员",   "persona_strict.md",  "会话结束。"),
}

# 解析命令行参数，获取人设名称
persona_name = "buddy"  # 默认人设
args = sys.argv[1:]
for i, arg in enumerate(args):
    if arg == "--persona" and i + 1 < len(args):
        persona_name = args[i + 1]

# 校验人设名称是否有效
if persona_name not in PERSONA_CONFIG:
    print(f"错误：未知的人设 '{persona_name}'")
    print(f"可用人设: {', '.join(PERSONA_CONFIG.keys())}")
    print("用法: python step05.py --persona <人设名>")
    sys.exit(1)

display_name, persona_file, goodbye_msg = PERSONA_CONFIG[persona_name]

# 加载对应的人设文件作为 system prompt
if not os.path.exists(persona_file):
    print(f"错误：人设文件 '{persona_file}' 不存在")
    sys.exit(1)

messages = [{"role": "system", "content": open(persona_file, encoding="utf-8").read()}]

# 展示当前加载的人设
print("=" * 50)
print(f"🤖 Agent 人设已加载：{display_name}")
print(f"   配置文件: {persona_file}")
print(f"   切换人设: python step05.py --persona buddy|teacher|strict")
print("=" * 50)

while True:
    user_input = input("\n你: ")
    if user_input.lower() in ["退出", "exit", "quit"]:
        print(f"Agent: {goodbye_msg}")
        break
    messages.append({"role": "user", "content": user_input})

    while True:
        try:
            result = call_zhipu_api(messages)
        except Exception as e:
            print(f"[ERROR] API 调用异常: {e}")
            break

        if not result.get("choices"):
            print("[ERROR] API 返回异常：choices 为空")
            break

        assistant_reply = result['choices'][0]['message']['content']
        if not assistant_reply:
            print("[ERROR] 模型返回内容为空")
            break

        messages.append({"role": "assistant", "content": assistant_reply})

        # ---- 调试日志：打印大模型原始返回，方便排查格式问题 ----
        print(f"[DEBUG] 模型原始返回: {repr(assistant_reply)}")

        # 先去除首尾空白字符（换行、空格等），再判断格式
        reply_clean = assistant_reply.strip()
        if reply_clean.startswith("完成:"):
            reply_text = reply_clean.split("完成:", 1)[1].strip()
            print(f"Agent: {reply_text}")
            break

        if not reply_clean.startswith("命令:"):
            print(f"[ERROR] 模型返回不符合预期格式！期望 '命令:' 或 '完成:' 开头，实际返回见上方 DEBUG 行")
            break

        command = reply_clean.split("命令:", 1)[1].strip()
        print(f"Agent 执行: {command}")
        try:
            command_result = os.popen(command).read()
        except Exception as e:
            command_result = f"命令执行异常: {e}"
        content = f"执行完毕 {command_result}"
        messages.append({"role": "user", "content": content})
