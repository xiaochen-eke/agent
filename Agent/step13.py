import requests
import json
import os
import sys

ZHIPU_API_KEY = os.getenv("ZHIPU_API_KEY")
if not ZHIPU_API_KEY:
    print("错误：未设置环境变量 ZHIPU_API_KEY")
    print("请设置: set ZHIPU_API_KEY=your_api_key")
    sys.exit(1)


def call_zhipu_api(messages, model="glm-4-flash", tools=None):
    """调用智谱 GLM API，支持 tools 参数"""
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
# Step13: 带联网搜索的 Agent（人设 + 函数调用 + 联网搜索）
# ============================================================
# 核心变化（与 step05 对比）：
#   step05: 文本解析 "命令:"/"完成:" 执行系统命令
#   step13: 三合一 —— 联网搜索 + 函数调用执行命令 + 人设系统
#
# 为什么把联网搜索做成内置工具：
#   1.【零代码】API 服务端自动完成搜索、提取摘要、排序，客户端零额外代码
#   2.【智能触发】模型自动判断什么时候需要联网，不需要手动控制
#   3.【结果融合】搜索结果直接融入模型回复，无需拼接 tool result
#   4.【可溯源】搜索结果会标注来源链接
#   5.【成本可控】4 档搜索引擎可切换，从 0.01 到 0.05 元/次
#
# 搜索引擎选择（价格由低到高）：
#   search_std        → 标准版（0.01元/次）智谱自研，满足日常查询
#   search_pro        → 高级版（0.03元/次）多引擎协作，召回率大幅提升
#   search_pro_sogou  → 搜狗引擎（0.05元/次）覆盖腾讯生态+知乎
#   search_pro_quark  → 夸克引擎（0.05元/次）精准垂直内容
#
# 使用方式：
#   python step13.py                              → 默认人设 buddy + pro 引擎
#   python step13.py --persona buddy              → 小A（热心伙伴）
#   python step13.py --persona teacher            → 王老师（教学风格）
#   python step13.py --persona strict             → SysAdmin（简洁专业）
#   python step13.py --search-engine pro          → 高级版搜索引擎（默认）
#   python step13.py --search-engine std          → 标准引擎（最省钱）
#   python step13.py --search-engine sogou        → 搜狗引擎（覆盖知乎）
#   python step13.py --search-engine quark        → 夸克引擎
#   python step13.py --no-search                  → 完全关闭联网搜索
# ============================================================

# ---- 搜索引擎配置表 ----
# 用于 --search-engine 参数映射
SEARCH_ENGINES = {
    "std": {
        "id": "search_std",
        "price": "0.01元/次",
        "desc": "智谱自研标准版，性价比极高，满足日常查询需求"
    },
    "pro": {
        "id": "search_pro",
        "price": "0.03元/次",
        "desc": "多引擎协作版，显著降低空结果率，召回率和准确率大幅提升"
    },
    "sogou": {
        "id": "search_pro_sogou",
        "price": "0.05元/次",
        "desc": "搜狗引擎，覆盖腾讯生态（新闻/企鹅号）和知乎内容"
    },
    "quark": {
        "id": "search_pro_quark",
        "price": "0.05元/次",
        "desc": "夸克引擎，精准触达垂直内容"
    },
}

# ---- 人设配置表 ----
# 使用 V2 人设文件（无 "命令:"/"完成:" 格式约束，改为工具调用）
PERSONA_CONFIG = {
    "buddy":   ("小A - 你的电脑管家",      "Agent_v2.md",            "拜拜！有需要随时找我哦~ 👋"),
    "teacher": ("王老师 - 计算机教学助手",  "persona_teacher_v2.md",   "下课！回去记得复习今天的知识点哦~"),
    "strict":  ("SysAdmin - 系统管理员",    "persona_strict_v2.md",    "会话结束。"),
}

# ---- 解析命令行参数 ----
persona_name = "buddy"
search_engine_key = "pro"
no_search = False  # 是否关闭联网搜索

args = sys.argv[1:]
for i, arg in enumerate(args):
    if arg == "--persona" and i + 1 < len(args):
        persona_name = args[i + 1]
    elif arg == "--search-engine" and i + 1 < len(args):
        search_engine_key = args[i + 1]
    elif arg == "--no-search":
        no_search = True

# 校验人设名称
if persona_name not in PERSONA_CONFIG:
    print(f"错误：未知的人设 '{persona_name}'")
    print(f"可用人设: {', '.join(PERSONA_CONFIG.keys())}")
    print("用法: python step13.py --persona buddy|teacher|strict")
    sys.exit(1)

# 校验搜索引擎
if not no_search and search_engine_key not in SEARCH_ENGINES:
    print(f"错误：未知的搜索引擎 '{search_engine_key}'")
    print(f"可用引擎: {', '.join(SEARCH_ENGINES.keys())}")
    print("用法: python step13.py --search-engine std|pro|sogou|quark")
    sys.exit(1)

display_name, persona_file, goodbye_msg = PERSONA_CONFIG[persona_name]
engine_info = SEARCH_ENGINES.get(search_engine_key)

# ---- 加载人设文件 ----
# 优先 V2 文件（专为工具调用设计），不存在则回退到原版
persona_candidates = [
    persona_file,
    persona_file.replace("_v2.md", ".md"),
]
persona_content = None
persona_file_used = None
for pf in persona_candidates:
    if os.path.exists(pf):
        persona_content = open(pf, encoding="utf-8").read()
        persona_file_used = pf
        break

if persona_content is None:
    print(f"错误：人设文件 '{persona_file}' 不存在")
    print(f"已尝试: {', '.join(persona_candidates)}")
    sys.exit(1)

messages = [{"role": "system", "content": persona_content}]

# ---- 构建 tools 数组 ----
# 由两部分组成：
#   1. function 工具：execute_command —— 执行系统命令
#   2. web_search 内置工具：联网搜索 —— API 自动处理搜索和结果融合

TOOLS = []

# 函数工具：命令执行
TOOLS.append({
    "type": "function",
    "function": {
        "name": "execute_command",
        "description": "在 Windows 系统上执行一条命令并返回结果。可用于查看目录(dir)、读取文件内容(type)、创建目录(mkdir)、移动文件(move)等操作。当用户需要操作文件系统或执行系统命令时调用此工具。",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "要执行的 Windows 系统命令，例如 'dir'、'type hello.py'、'mkdir test_folder'"
                }
            },
            "required": ["command"]
        }
    }
})

# 内置工具：联网搜索（除非用户指定 --no-search 关闭）
if not no_search:
    # search_prompt 是可选参数，用于指导模型如何处理搜索结果
    # 当不传入时，模型使用默认搜索回答策略（适合通用场景）
    # 如果需要特定领域的回答风格（如财经分析），可取消下面的注释并自定义
    web_search_config = {
        "enable": "True",
        "search_engine": engine_info["id"],
        "search_result": "True",
        "count": 10,
        "search_recency_filter": "noLimit",
        "content_size": "high",
        # "search_domain_filter": "www.sohu.com",  # 可选：限制搜索域名
        # "search_prompt": "请用简洁的语言总结网络搜索结果中的关键信息，按重要性排序并引用来源。如果信息过时请标注日期。"
    }
    TOOLS.append({
        "type": "web_search",
        "web_search": web_search_config
    })

# ---- 工具执行器 ----
# 注意：web_search 是内置工具类型，API 服务端自动处理搜索
# 客户端不需要为 web_search 编写执行代码
# execute_command 需要客户端执行并返回结果

def execute_tool_call(tool_call):
    """执行函数工具调用，返回执行结果字符串"""
    func_name = tool_call["function"]["name"]
    func_args = json.loads(tool_call["function"]["arguments"])

    if func_name == "execute_command":
        command = func_args["command"]
        try:
            result = os.popen(command).read()
            if result.strip():
                return f"命令 '{command}' 执行结果:\n{result}"
            else:
                return f"命令 '{command}' 执行成功（无输出）"
        except Exception as e:
            return f"命令 '{command}' 执行异常: {e}"

    return f"未知工具: {func_name}"


# ---- 打印启动信息 ----
print("=" * 60)
print(f"🤖 Agent 人设已加载：{display_name}")
print(f"   配置文件: {persona_file_used}")
if no_search:
    print(f"🌐 联网搜索: 已关闭（--no-search）")
else:
    print(f"🌐 联网搜索: 已开启")
    print(f"   搜索引擎: {engine_info['id']}")
    print(f"   引擎说明: {engine_info['desc']}")
    print(f"   单次费用: {engine_info['price']}")
    print(f"   ╰ 切换引擎: python step13.py --search-engine std|pro|sogou|quark")
    print(f"   ╰ 关闭搜索: python step13.py --no-search")
print(f"📦 命令执行: 函数调用模式（execute_command）")
print(f"   ╰ 切换人设: python step13.py --persona buddy|teacher|strict")
print("=" * 60)


# =============================================
# Agent 主循环
# =============================================
# 处理流程：
#   1. 接收用户输入
#   2. 调用 API（携带 tools 数组）
#   3. 判断模型返回：
#      a. tool_calls → 执行函数工具（execute_command），将结果送回模型继续
#      b. content → 输出最终回复（内容可能已包含联网搜索结果）
#      c. 异常 → 报错退出内循环
#   4. 回到步骤 1
#
# web_search 是特殊的内置工具类型：
#   - 不会出现在 tool_calls 中（不需要客户端执行）
#   - API 服务端自动完成搜索并融合结果到模型回复中
#   - 模型回复的 content 可能包含搜索结果和来源链接
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

        # ---- 情况1: 模型要调用函数工具（execute_command） ----
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
            continue  # 将工具结果送回模型，让模型决定下一步

        # ---- 情况2: 模型直接回复文本 ----
        # 此时 content 可能包含两种内容：
        #   - 普通对话回复（不需要联网和命令执行）
        #   - 联网搜索结果 + 模型分析（web_search 内置工具自动完成）
        # 不管是哪种，客户端都直接展示即可
        if msg.get("content"):
            messages.append(msg)
            print(f"Agent: {msg['content']}")
            # 当 web_search 被触发时，搜索结果和来源链接已自动融入 content 中
            # 客户端无需额外处理，直接展示即可
            break

        # ---- 异常：模型既没有调用工具，也没有回复文本 ----
        print(f"[ERROR] 模型返回异常：content 和 tool_calls 均为空")
        print(f"[DEBUG] finish_reason={finish_reason}, msg={json.dumps(msg, ensure_ascii=False)}")
        break
