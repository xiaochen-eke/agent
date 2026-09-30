import requests
import json
import os
import sys
import fnmatch

# 绕过系统代理，避免 SSL 错误
os.environ.setdefault('no_proxy', '*')
os.environ.setdefault('NO_PROXY', '*')

# ---- 加载 .env ----
def _load_dotenv():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v
_load_dotenv()

# ============================================================
# 搜索 Agent — 基于 Function Calling 的多工具搜索助手
# ============================================================
# 工具列表:
#   search_files      - 按文件名模式搜索
#   search_content    - 搜索文件内容 (grep)
#   search_images     - 搜索已分类的图片
#   list_image_labels - 列出所有图片分类标签
#   read_file         - 读取文件内容
#   web_search        - 网页搜索 (通过智谱 web_search 工具)
#
# 用法:
#   python search_agent.py
#   python search_agent.py --persona buddy|teacher|strict
# ============================================================

ZHIPU_API_KEY = os.getenv("ZHIPU_API_KEY")

# ---- 图片搜索相关配置 ----
SUPPORTED_IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".bmp", ".gif")
DEFAULT_IMAGE_DIR = r"C:\\DLdata\\git\\PH\\1"


def call_zhipu_api(messages, model="glm-4-flash", tools=None):
    url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
    headers = {
        "Authorization": ZHIPU_API_KEY,
        "Content-Type": "application/json"
    }
    data = {"model": model, "messages": messages, "temperature": 0.7}
    if tools:
        data["tools"] = tools
        data["tool_choice"] = "auto"
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"API调用失败: {response.status_code}, {response.text}")


# ============================================================
# 工具实现
# ============================================================

def tool_search_files(directory: str, pattern: str = "*", recursive: bool = True) -> str:
    """按文件名模式搜索文件，支持通配符。"""
    if not os.path.isdir(directory):
        return f"错误：目录不存在 - {directory}"
    results = []
    if recursive:
        for root, dirs, files in os.walk(directory):
            for f in files:
                if fnmatch.fnmatch(f.lower(), pattern.lower()):
                    results.append(os.path.join(root, f))
    else:
        for f in os.listdir(directory):
            full = os.path.join(directory, f)
            if os.path.isfile(full) and fnmatch.fnmatch(f.lower(), pattern.lower()):
                results.append(full)
    if not results:
        return f"在 {directory} 中没有找到匹配 '{pattern}' 的文件"
    return f"找到 {len(results)} 个文件:\n" + "\n".join(results[:100])


def tool_search_content(directory: str, query: str, file_pattern: str = "*",
                        case_sensitive: bool = False, recursive: bool = True) -> str:
    """在文件内容中搜索关键词 (grep)。"""
    if not os.path.isdir(directory):
        return f"错误：目录不存在 - {directory}"
    results = []
    flags = 0 if case_sensitive else os.path.__dict__.get('_IGNORECASE', 1)  # fallback
    walker = os.walk(directory) if recursive else [(directory, [], os.listdir(directory))]
    for root, dirs, files in walker:
        for f in files:
            if not fnmatch.fnmatch(f.lower(), file_pattern.lower()):
                continue
            fp = os.path.join(root, f)
            try:
                with open(fp, encoding="utf-8", errors="ignore") as fh:
                    for lineno, line in enumerate(fh, 1):
                        if case_sensitive:
                            hit = query in line
                        else:
                            hit = query.lower() in line.lower()
                        if hit:
                            results.append(f"{fp}:{lineno}: {line.strip()}")
                            if len(results) >= 200:
                                break
            except Exception:
                continue
            if len(results) >= 200:
                break
    if not results:
        return f"在 {directory} 中没有找到包含 '{query}' 的文件"
    return f"找到 {len(results)} 处匹配:\n" + "\n".join(results)


def _index_images(base_dir: str) -> dict:
    """扫描图片目录，返回 label -> [paths] 映射。"""
    index = {}
    if not os.path.isdir(base_dir):
        return index
    for root, dirs, files in os.walk(base_dir):
        rel = os.path.relpath(root, base_dir)
        if rel == ".":
            continue
        label = rel.replace(os.sep, "/")
        imgs = [os.path.join(root, f) for f in files
                if f.lower().endswith(SUPPORTED_IMAGE_EXTS)]
        if imgs:
            index[label] = imgs
    return index


def tool_search_images(base_dir: str, query: str) -> str:
    """在已分类的图片中搜索，匹配标签或文件名。"""
    if not os.path.isdir(base_dir):
        return f"错误：图片目录不存在 - {base_dir}"
    index = _index_images(base_dir)
    if not index:
        return f"在 {base_dir} 中没有找到任何图片，请先运行图片分类。"
    q = query.lower()
    results = []
    for label, paths in index.items():
        for p in paths:
            if q in label.lower() or q in os.path.basename(p).lower():
                results.append(f"[{label}] {p}")
    if not results:
        return f"没有找到与 '{query}' 相关的图片"
    return f"找到 {len(results)} 张图片:\n" + "\n".join(results[:100])


def tool_list_image_labels(base_dir: str) -> str:
    """列出所有图片分类标签及其数量。"""
    if not os.path.isdir(base_dir):
        return f"错误：图片目录不存在 - {base_dir}"
    index = _index_images(base_dir)
    if not index:
        return f"在 {base_dir} 中没有找到任何图片分类。"
    lines = []
    total = 0
    for label, paths in sorted(index.items()):
        cnt = len(paths)
        total += cnt
        lines.append(f"  {label} ({cnt} 张)")
    return f"共 {len(index)} 个分类, {total} 张图片:\n" + "\n".join(lines)


def tool_read_file(filepath: str, lines: int = 50) -> str:
    """读取文件内容（前 N 行）。"""
    if not os.path.exists(filepath):
        return f"错误：文件不存在 - {filepath}"
    if not os.path.isfile(filepath):
        return f"错误：不是文件 - {filepath}"
    try:
        with open(filepath, encoding="utf-8", errors="ignore") as f:
            content = []
            for i, line in enumerate(f):
                if i >= lines:
                    content.append(f"... (共 {lines} 行，后续内容省略)")
                    break
                content.append(line.rstrip())
            return "\n".join(content)
    except Exception as e:
        return f"读取失败: {e}"


def tool_web_search(query: str, max_results: int = 5) -> str:
    """
    网页搜索 — 使用智谱 web_search 工具。
    
    参数:
        query: 搜索查询词
        max_results: 返回结果数量上限
    
    返回:
        格式化的搜索结果字符串
    """
    try:
        # 使用智谱的 web_search 工具能力
        search_prompt = f"""请搜索以下内容，并给出最相关的 {max_results} 条结果。
搜索词: {query}

返回格式:
1. 标题
   URL/来源
   摘要 (100字内)
---"""
        
        result = call_zhipu_api(
            [{"role": "user", "content": search_prompt}],
            model="glm-4-flash",
            tools=[{"type": "web_search", "web_search": {"enable": True}}]
        )
        
        msg = result.get("choices", [{}])[0].get("message", {})
        content = msg.get("content", "")
        
        if content:
            return f"【网页搜索结果】\n查询词: {query}\n\n{content}"
        else:
            return f"网页搜索 '{query}' 无结果，请尝试换个关键词"
            
    except Exception as e:
        # 降级方案：直接使用大模型搜索能力（基于训练数据）
        try:
            result = call_zhipu_api(
                [{"role": "user", 
                  "content": f"基于你的知识回答: {query}\n请给出最有帮助的信息，并标注来源"}],
                model="glm-4-flash"
            )
            content = result["choices"][0]["message"].get("content", "")
            return f"【基于知识库的搜索结果】\n{content}" if content else "搜索无结果"
        except Exception as e2:
            return f"❌ 网页搜索失败: {str(e2)}\n建议: 请检查网络连接或稍后重试"


# ============================================================
# 工具注册表
# ============================================================

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": "在指定目录中按文件名模式搜索文件。支持通配符 * 和 ?，例如 *.py 搜索所有Python文件、*报告* 搜索含'报告'的文件。",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {"type": "string", "description": "要搜索的目录路径"},
                    "pattern": {"type": "string", "description": "文件名匹配模式，支持通配符，默认 * 匹配所有文件", "default": "*"},
                    "recursive": {"type": "boolean", "description": "是否递归搜索子目录，默认 true", "default": True}
                },
                "required": ["directory"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_content",
            "description": "在文件内容中搜索关键词（类似 grep），返回匹配的行及位置。",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {"type": "string", "description": "要搜索的目录路径"},
                    "query": {"type": "string", "description": "要搜索的关键词"},
                    "file_pattern": {"type": "string", "description": "限定搜索的文件类型，如 *.py。默认 * 搜索所有文本文件", "default": "*"},
                    "case_sensitive": {"type": "boolean", "description": "是否区分大小写，默认 false", "default": False},
                    "recursive": {"type": "boolean", "description": "是否递归搜索子目录，默认 true", "default": True}
                },
                "required": ["directory", "query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_images",
            "description": "在已分类的图片库中搜索图片。可按分类标签搜索（如'猫'、'狗'），也可按文件名搜索。",
            "parameters": {
                "type": "object",
                "properties": {
                    "base_dir": {"type": "string", "description": f"图片分类根目录，默认 {DEFAULT_IMAGE_DIR}", "default": DEFAULT_IMAGE_DIR},
                    "query": {"type": "string", "description": "搜索关键词，匹配分类标签或文件名"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_image_labels",
            "description": "列出所有图片分类标签及每个分类下的图片数量。",
            "parameters": {
                "type": "object",
                "properties": {
                    "base_dir": {"type": "string", "description": f"图片分类根目录，默认 {DEFAULT_IMAGE_DIR}", "default": DEFAULT_IMAGE_DIR}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "读取文件内容。用于查看搜索到文件的具体内容。",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {"type": "string", "description": "要读取的文件完整路径"},
                    "lines": {"type": "integer", "description": "读取行数限制，默认 50", "default": 50}
                },
                "required": ["filepath"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "网页搜索，用于查找互联网上的信息、新闻、文档等。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词或问题，尽量具体"}
                },
                "required": ["query"]
            }
        }
    }
]

TOOL_EXECUTORS = {
    "search_files":      lambda args: tool_search_files(**args),
    "search_content":    lambda args: tool_search_content(**args),
    "search_images":     lambda args: tool_search_images(**args),
    "list_image_labels": lambda args: tool_list_image_labels(**args),
    "read_file":         lambda args: tool_read_file(**args),
    "web_search":        lambda args: tool_web_search(**args),
}


def execute_tool_call(tool_call):
    func_name = tool_call["function"]["name"]
    func_args = json.loads(tool_call["function"]["arguments"])
    executor = TOOL_EXECUTORS.get(func_name)
    if executor:
        return executor(func_args)
    return f"未知工具: {func_name}"


# ============================================================
# 人设
# ============================================================

SEARCH_PERSONA = """## 一、你的身份

你是 "小搜"，一个专业又热情的搜索助手，住在用户的电脑里。

性格特征：
- 性格：细心、高效、善于发现
- 说话风格：简洁明了，结果导向，带一点理工男的幽默感
- 特长：文件搜索、内容检索、图片查找、网页搜索，你能帮用户快速定位任何信息
- 口癖：喜欢在搜索结果后说"找到啦！"或给个实用的小提示

## 二、行为准则

1. 始终使用中文交流
2. 搜索结果要清晰展示，帮用户快速理解
3. 如果搜不到，给用户建议换个关键词或扩大范围
4. 主动友好，但不过度啰嗦

## 三、可用工具

你可以使用以下工具帮助用户搜索：
- search_files：按文件名搜索
- search_content：搜索文件内容
- search_images：搜索图片
- list_image_labels：查看图片分类
- read_file：查看文件内容
- web_search：网页搜索

根据用户的自然语言请求，选择最合适的工具组合。"""

PERSONA_CONFIG = {
    "search":  ("小搜 - 智能搜索助手",   SEARCH_PERSONA,  "有事搜一搜，没事常联系~"),
    "buddy":   ("小A - 你的电脑管家",     "Agent_v2.md",   "拜拜！有需要随时找我哦~"),
    "teacher": ("王老师 - 计算机教学助手", "persona_teacher_v2.md", "下课！回去记得复习今天的知识点哦~"),
    "strict":  ("SysAdmin - 系统管理员",   "persona_strict_v2.md",  "会话结束。"),
}


# ============================================================
# 主程序
# ============================================================

def main():
    persona_name = "search"
    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg == "--persona" and i + 1 < len(args):
            persona_name = args[i + 1]

    if persona_name not in PERSONA_CONFIG:
        print(f"错误：未知的人设 '{persona_name}'")
        print(f"可用人设: {', '.join(PERSONA_CONFIG.keys())}")
        sys.exit(1)

    display_name, persona_source, goodbye_msg = PERSONA_CONFIG[persona_name]

    # 人设可以是字符串（内联）或文件路径
    if persona_source.endswith(".md") and os.path.exists(persona_source):
        system_content = open(persona_source, encoding="utf-8").read()
    else:
        system_content = persona_source

    messages = [{"role": "system", "content": system_content}]

    print("=" * 60)
    print(f"🔍 搜索 Agent 已加载：{display_name}")
    print(f"   可用工具: {', '.join(t['function']['name'] for t in TOOLS)}")
    print("=" * 60)

    while True:
        try:
            user_input = input("\n你: ")
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if user_input.lower() in ["退出", "exit", "quit"]:
            print(f"Agent: {goodbye_msg}")
            break
        messages.append({"role": "user", "content": user_input})

        max_turns = 5  # 防止无限循环
        while max_turns > 0:
            max_turns -= 1
            try:
                result = call_zhipu_api(messages, tools=TOOLS)
            except Exception as e:
                print(f"[ERROR] API 调用异常: {e}")
                break

            if not result.get("choices"):
                print("[ERROR] API 返回异常：choices 为空")
                break

            msg = result["choices"][0]["message"]

            if msg.get("tool_calls"):
                messages.append(msg)
                for tc in msg["tool_calls"]:
                    func_name = tc["function"]["name"]
                    func_args = tc["function"]["arguments"]
                    print(f"[Tool] 🔍 {func_name}({func_args[:100]}{'...' if len(func_args) > 100 else ''})")

                    tool_result = execute_tool_call(tc)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": tool_result
                    })
                continue

            if msg.get("content"):
                messages.append(msg)
                print(f"Agent: {msg['content']}")
                break

            print(f"[ERROR] 模型返回异常")
            break


if __name__ == "__main__":
    main()
