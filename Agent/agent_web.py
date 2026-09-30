import os
import sys
from datetime import datetime
from dotenv import load_dotenv
from zhipuai import ZhipuAI

# ==========================
# 加载环境变量
# ==========================
load_dotenv()

API_KEY = os.getenv("ZHIPU_API_KEY")

if not API_KEY:
    print("错误：未设置 ZHIPU_API_KEY")
    print("请在 .env 文件中配置：")
    print("ZHIPU_API_KEY=你的API_KEY")
    sys.exit(1)

client = ZhipuAI(api_key=API_KEY)

# ==========================
# 人设配置
# ==========================
PERSONA_CONFIG = {
    "buddy": (
        "小A - 你的电脑管家",
        "Agent_v2.md",
        "拜拜！有需要随时找我哦~ 👋"
    ),
    "teacher": (
        "王老师 - 计算机教学助手",
        "persona_teacher_v2.md",
        "下课！回去记得复习今天的知识点哦~"
    ),
    "strict": (
        "SysAdmin - 系统管理员",
        "persona_strict_v2.md",
        "会话结束。"
    ),
}

# ==========================
# 解析命令行参数
# ==========================
persona_name = "buddy"

args = sys.argv[1:]

for i, arg in enumerate(args):
    if arg == "--persona" and i + 1 < len(args):
        persona_name = args[i + 1]

if persona_name not in PERSONA_CONFIG:
    print(f"未知人设: {persona_name}")
    print("可选: buddy | teacher | strict")
    sys.exit(1)

display_name, persona_file, goodbye_msg = PERSONA_CONFIG[persona_name]

# ==========================
# 加载人设文件
# ==========================
if not os.path.exists(persona_file):
    print(f"找不到人设文件: {persona_file}")
    sys.exit(1)

with open(persona_file, "r", encoding="utf-8") as f:
    persona_content = f.read()

# ==========================
# 系统提示词
# ==========================
today = datetime.now().strftime("%Y-%m-%d")

system_prompt = f"""
今天日期是 {today}。

你是一个联网Agent。

当用户询问：
- 今天新闻
- 最新新闻
- AI新闻
- 科技新闻
- 热点事件
- 当前发生了什么
- 今日日期
- 今日时间

优先使用联网搜索获取最新信息。

不要编造新闻。
必须基于搜索结果回答。

{persona_content}
"""

messages = [
    {
        "role": "system",
        "content": system_prompt
    }
]

# ==========================
# Agent调用函数
# ==========================
def ask_agent(chat_messages):
    response = client.chat.completions.create(
        model="glm-4-flash",
        messages=chat_messages,
        tools=[
            {
                "type": "web_search",
                "web_search": {
                    "enable": True
                }
            }
        ]
    )

    return response

# ==========================
# 启动信息
# ==========================
print("=" * 60)
print(f"🤖 Agent 已启动: {display_name}")
print(f"📄 人设文件: {persona_file}")
print(f"🌐 联网搜索: 已开启")
print(f"📅 今天日期: {today}")
print("=" * 60)

# ==========================
# 主循环
# ==========================
while True:

    try:
        user_input = input("\n你: ").strip()

        if not user_input:
            continue

        if user_input.lower() in ["exit", "quit", "退出"]:
            print(f"\nAgent: {goodbye_msg}")
            break

        messages.append(
            {
                "role": "user",
                "content": user_input
            }
        )

        response = ask_agent(messages)

        assistant_msg = response.choices[0].message

        content = assistant_msg.content

        if not content:
            content = "模型未返回内容"

        print("\n" + "=" * 60)
        print(f"🤖 {display_name}")
        print("=" * 60)
        print(content)
        print("=" * 60)

        messages.append(
            {
                "role": "assistant",
                "content": content
            }
        )

    except KeyboardInterrupt:
        print(f"\n\nAgent: {goodbye_msg}")
        break

    except Exception as e:
        print(f"\n[ERROR] {e}")