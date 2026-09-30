#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dify_brain.py — Dify 版大脑（闭环：状态/语音/视觉 → Dify 工作流 → 建议 → 回灌游戏）

与 native_agent.py 的职责一致（规划→检索→执行→反思），但「大脑」换成了 Dify 工作流。
两者共享同一套采集层（dst_mod + bridge + state_api），只有决策核心不同。

闭环链路：
    dst_mod 采集 → bridge 推状态 → state_api(:5002) 存最新状态 + 规则兜底
    麦克风/音频 → transcribe.py(GLM-4-Voice/Whisper) → 语音文本 voice_query
    截图/图片  → 原生上传 image（视觉模型直接看图）；视频 → 抽帧成图再上传
        ▲                                          │
        └── 本进程轮询 /current_state，发现「⚠️ 状态告警」或有多模态输入时调 Dify
                                                   │
        ┌──────────────────────────────────────────┘
        └── Dify 输出 → POST /advice 入队 → bridge 轮询写 dify_advice.json → 游戏播报

记忆跨轮持久化：
    每轮把 Dify 产出的结构化计划(plan=aggregate 的 next_action/timeline/risks)写进
    dst_memory.json，下一轮作为 start.memory / start.last_action 传回，形成跨轮记忆。

触发策略（事件驱动 + 阈值去噪）：
    ① 状态摘要出现「⚠️ 状态告警」（阈值被穿越）→ 触发（带冷却，避免刷屏省 token）
    ② 玩家给了语音/视觉输入（主动提问）→ 无条件触发（不带冷却）

用法：
    python dify_brain.py                        # 常驻守护进程（状态轮询）
    python dify_brain.py --once                 # 单次：取状态跑一遍
    python dify_brain.py --once --voice a.wav             # 语音提问
    python dify_brain.py --once --vision screen.png       # 画面识别
    python dify_brain.py --once --voice a.wav --vision s.png
"""

import argparse
import json
import os
import re
import sys
import time

import requests
from html import unescape

# 修复 Windows 控制台 GBK 编码
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# 加载 .env 文件（不依赖 python-dotenv），供 DIFY_API_KEY / ZHIPU_API_KEY 等使用
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

import game_meta  # 物品元数据（可合成/稀有度/配方）
import skills     # 技能注册表（动作白名单单一数据源）

# ============ 配置（均可被环境变量覆盖） ============
STATE_API = os.getenv("DST_STATE_API", "http://127.0.0.1:5002")
DIFY_API_URL = os.getenv("DIFY_API_URL", "http://127.0.0.1/v1/workflows/run")
DIFY_API_KEY = os.getenv("DIFY_API_KEY", "app-GLGMQxrlsTFdpwJwcEy1WphL")
DIFY_FILES_UPLOAD_URL = os.getenv("DIFY_FILES_UPLOAD_URL", "http://127.0.0.1/v1/files/upload")
GOAL = os.getenv("DST_GOAL", "我想活到冬天")
MEMORY_FILE = os.getenv("DST_MEMORY_FILE", os.path.join(os.path.dirname(os.path.abspath(__file__)), "dst_memory.json"))

POLL_INTERVAL = float(os.getenv("DST_POLL_INTERVAL", "3"))      # 轮询 /current_state 的秒数
ALERT_COOLDOWN = float(os.getenv("DST_ALERT_COOLDOWN", "45"))   # 两次「阈值告警」调 Dify 的最小间隔（秒）
DIFY_TIMEOUT = float(os.getenv("DST_DIFY_TIMEOUT", "180"))      # 工作流阻塞等待上限（秒）

# —— Phase 3：LLM 动作决策（把 状态+建议 → 可执行动作 verb+prefab）——
GLM_API_KEY = os.getenv("ZHIPU_API_KEY", "")
GLM_BASE_URL = "https://open.bigmodel.cn/api/paas/v4/"
GLM_ACTION_MODEL = os.getenv("DST_ACTION_MODEL", "glm-4-flash")

# —— Phase 3.5：决策时查游戏数据库（function-calling 工具）——
GAME_API = os.getenv("DST_GAME_API", "http://127.0.0.1:5001")  # 游戏知识库（items/foods/配方/成本）


def log(*args):
    print("[dify_brain]", *args, flush=True)


# ============ 记忆持久化 ============
def load_memory():
    """读取上一轮持久化的记忆，返回 (memory, last_action)。没有则返回空串。"""
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            d = json.load(f)
        return d.get("memory", ""), d.get("last_action", "")
    except Exception:
        return "", ""


def save_memory(memory: str, last_action: str) -> bool:
    """把本轮的结构化计划(plan)与最终动作写回磁盘，供下一轮读取。"""
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(
                {"memory": memory, "last_action": last_action, "updated_at": time.time()},
                f, ensure_ascii=False, indent=2,
            )
        return True
    except Exception as e:
        log(f"写记忆失败: {e}")
        return False


# ============ 多模态感知（惰性导入，不跑多模态时零开销） ============
def run_transcribe(audio_path: str) -> str:
    """语音理解：优先智谱 GLM-4-Voice（原生音频），失败回退本地 Whisper。"""
    try:
        import transcribe
        text = transcribe.transcribe_glm(audio_path)
        if text:
            return text
        return transcribe.transcribe(audio_path)
    except Exception as e:
        log(f"语音识别失败: {e}")
        return ""


def upload_file(path: str):
    """上传文件到 Dify（/v1/files/upload），返回 (upload_file_id, file_type)。"""
    ext = os.path.splitext(path)[1].lower()
    ftype = {
        ".png": "image", ".jpg": "image", ".jpeg": "image", ".bmp": "image", ".webp": "image",
        ".mp4": "video", ".avi": "video", ".mkv": "video", ".mov": "video",
        ".wav": "audio", ".mp3": "audio", ".m4a": "audio", ".flac": "audio",
    }.get(ext, "custom")
    import mimetypes
    mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
    try:
        with open(path, "rb") as f:
            r = requests.post(
                DIFY_FILES_UPLOAD_URL,
                headers={"Authorization": f"Bearer {DIFY_API_KEY}"},
                files={"file": (os.path.basename(path), f, mime)},
                data={"user": "dify-brain"},
                timeout=120,
            )
        r.raise_for_status()
        return r.json().get("id"), ftype
    except Exception as e:
        log(f"上传文件失败 {path}: {e}")
        return None, None


def upload_images(paths):
    """把图片/视频路径转成 Dify file 对象列表（视频先抽帧成图）。"""
    video_exts = {".mp4", ".avi", ".mkv", ".mov", ".flv", ".wmv", ".webm"}
    file_objs = []
    for p in paths:
        if os.path.splitext(p)[1].lower() in video_exts:
            import vision
            for frame in vision.extract_frames(p):
                fid, ftype = upload_file(frame)
                if fid:
                    file_objs.append({"type": ftype, "transfer_method": "local_file", "upload_file_id": fid})
        else:
            fid, ftype = upload_file(p)
            if fid:
                file_objs.append({"type": ftype, "transfer_method": "local_file", "upload_file_id": fid})
    return file_objs


# ============ 核心 ============
def get_current_state():
    """读最新游戏状态（失败返回 None，由上层决定跳过）。"""
    try:
        r = requests.get(f"{STATE_API}/current_state", timeout=5)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log(f"读取状态失败: {e}")
        return None


def poll_panel_query():
    """轮询 state_api 的面板消息队列：有则返回文本，无则返回空串。

    面板「发送消息」会 POST /panel/message 入队，本函数消费后当作 voice_query
    触发 Dify（与语音通道一致），实现 Web 面板的双向对话。
    """
    try:
        r = requests.get(f"{STATE_API}/panel/query", timeout=3)
        if r.status_code == 200:
            d = r.json()
            if isinstance(d, dict):
                return (d.get("text") or "").strip()
    except Exception:
        pass
    return ""


def run_dify(inputs: dict, image_files=None):
    """调用 Dify 工作流（blocking 模式），返回 outputs 字典；失败返回 None。

    image_files 为图片文件对象列表（原生视觉），会写入 inputs['image']。
    """
    body_inputs = dict(inputs)
    if image_files:
        body_inputs["image"] = image_files
    try:
        r = requests.post(
            DIFY_API_URL,
            headers={
                "Authorization": f"Bearer {DIFY_API_KEY}",
                "Content-Type": "application/json",
            },
            json={"inputs": body_inputs, "response_mode": "blocking", "user": "dify-brain"},
            timeout=DIFY_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        log(f"调用 Dify 失败: {e}")
        return None

    run = data.get("data", {})
    if run.get("status") != "succeeded":
        log(f"Dify 运行未成功: status={run.get('status')} error={run.get('error', '')[:200]}")
        return None
    return run.get("outputs") or {}


def strip_reasoning(t: str) -> str:
    """去掉推理模型的思维链，只留最终回答。"""
    if not t:
        return t
    idx = t.rfind("</think>")
    if idx != -1:
        t = t[idx + len("</think>"):]
    t = re.sub(r"<think>.*?</think>", "", t, flags=re.DOTALL)
    t = re.sub(r"<!--.*?-->", "", t, flags=re.DOTALL)
    return t.strip()


def _unwrap_markdown_json(t: str) -> str:
    if t.startswith("```"):
        t = t.split("```", 2)[1]
        if t.lstrip().startswith("json"):
            t = t.lstrip()[4:]
        t = t.strip()
    return t


def extract_advice(outputs) -> str:
    """从 outputs 里抠出可播报的一句话建议（剥离思维链 / JSON / markdown）。"""
    raw = outputs.get("final_advice") or outputs.get("text") or ""
    if isinstance(raw, dict):
        return raw.get("final_advice") or raw.get("advice") or raw.get("action") or json.dumps(raw, ensure_ascii=False)

    t = str(raw).strip()
    t = _unwrap_markdown_json(t)
    t = strip_reasoning(t)
    if not t:
        return ""
    try:
        obj = json.loads(t)
        if isinstance(obj, dict):
            return obj.get("final_advice") or obj.get("advice") or obj.get("action") or t
    except Exception:
        pass
    return t


def extract_plan(outputs) -> str:
    """从 outputs 里抠出结构化计划（aggregate 的 next_action/timeline/risks JSON）。"""
    raw = outputs.get("plan") or ""
    if isinstance(raw, dict):
        return json.dumps(raw, ensure_ascii=False)
    t = str(raw).strip()
    t = _unwrap_markdown_json(t)
    t = strip_reasoning(t)
    return t


def push_advice(message: str) -> bool:
    """把建议 POST 回 state_api 的 /advice 队列，供 bridge 轮询回灌游戏。"""
    try:
        r = requests.post(f"{STATE_API}/advice", json={"message": message, "source": "dify"}, timeout=5)
        return r.status_code == 200
    except Exception as e:
        log(f"回灌建议失败: {e}")
        return False


# 动作白名单（单一数据源在 skills.ACTION_VERBS）
ACTION_VERBS = skills.ACTION_VERBS

# 可合成白名单已迁到 game_meta.get_meta()["craftable"]：硬编码兜底 ∪ game_data_api 配方数据。


def push_action(verb: str, prefab: str = "") -> bool:
    """把可执行动作 POST 回 state_api 的 /action 队列，供 bridge 写 dify_action.json。

    这是「大脑侧」的动作入口：后续把 Dify 产出的结构化计划 / GLM 动作决策映射成
    verb+prefab 后调这里，即可让 mod 执行（低风险自动、高风险弹确认）。
    """
    verb = (verb or "").strip()
    if verb not in ACTION_VERBS:
        log(f"非法动作 verb: {verb!r}")
        return False
    try:
        r = requests.post(f"{STATE_API}/action", json={"verb": verb, "prefab": (prefab or "").strip()}, timeout=5)
        return r.status_code == 200
    except Exception as e:
        log(f"回灌动作失败: {e}")
        return False


def _parse_json_result(t: str):
    """把 GLM 返回文本解析成 JSON dict（容忍 markdown 代码块）；失败返回 None。"""
    if not t:
        return None
    t = t.strip()
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


def _glm_json(system: str, user: str, model: str = None):
    """调 GLM 并解析成 JSON dict（无工具）；失败返回 None。惰性导入 openai。"""
    if not GLM_API_KEY:
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=GLM_API_KEY, base_url=GLM_BASE_URL)
        resp = client.chat.completions.create(
            model=model or GLM_ACTION_MODEL,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.2,
        )
        t = (resp.choices[0].message.content or "").strip()
    except Exception as e:
        log(f"GLM 动作决策失败: {e}")
        return None
    return _parse_json_result(t)


# ============ Phase 3.5：function-calling（决策时查游戏数据库） ============
GAME_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_db",
            "description": (
                "查询《饥荒》游戏数据库，获取物品/食物/生物/建筑/季节的名称、描述、配方、"
                "制作成本、稀有度等信息。当你不确定某物品的用途、价值、配方或成本，"
                "或想了解某类东西（如工具、食物、冬季准备）时先调用它，再据结果做决定。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词，如 'axe'、'斧头'、'营火'、'食物'、'winter'"},
                    "category": {
                        "type": "string",
                        "enum": ["all", "items", "creatures", "buildings", "foods", "seasons"],
                        "description": "限定类别，默认 all",
                    },
                },
                "required": ["query"],
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "联网搜索网页（Bing），获取游戏攻略、配方、数值、社区经验等数据库里没有的"
                "最新信息。当 search_db 查不到、或需要攻略/技巧/最新资讯时调用。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词，如 '饥荒 火堆 配方'、'Don't Starve Together 冬季生存技巧'"},
                },
                "required": ["query"],
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_webpage",
            "description": (
                "抓取指定网页的正文内容。先 web_search 拿到候选网页 URL 后，点进最相关的一条，"
                "读取完整攻略/配方/数值正文，再据结果做决定。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "网页完整 URL，来自 web_search 返回的 results[].url"},
                },
                "required": ["url"],
            },
        }
    }
]


def _search_db(query: str, category: str = "all") -> str:
    """调用 game_data_api 的 /search，返回紧凑 JSON 文本供 LLM 阅读；失败返回错误描述。"""
    log(f"🔍 search_db 查询: {query!r} (category={category})")
    try:
        r = requests.get(f"{GAME_API}/api/game-data/search", params={"q": query, "category": category}, timeout=4)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        return json.dumps({"error": f"数据库查询失败: {e}"}, ensure_ascii=False)

    results = data.get("results") or {}
    if not results:
        return json.dumps({"message": data.get("message", "未找到匹配结果"), "query": query}, ensure_ascii=False)

    compact = {}
    for _cat, matches in results.items():
        for name, info in list(matches.items())[:6]:
            entry = {}
            for k in ("description", "rarity", "category", "requires", "recipe", "cost", "type",
                      "station", "damage", "durability", "nutrition", "health", "danger_level", "behavior", "drops"):
                if info.get(k) not in (None, ""):
                    entry[k] = info[k]
            compact[name] = entry
    return json.dumps(compact, ensure_ascii=False)


def _strip_tags(s: str) -> str:
    """去 HTML 标签 + 反转义实体（&amp;/&#0183;/&ensp; 等）。"""
    s = re.sub(r"<[^>]+>", "", s or "")
    return unescape(s).strip()


def _web_search(query: str, num: int = 5) -> str:
    """用 Bing（国内可直连）搜索网页，返回前 num 条 {title,url,snippet} 的紧凑 JSON 文本；失败返回错误描述。"""
    log(f"🌐 web_search 查询: {query!r}")
    try:
        r = requests.get(
            "https://cn.bing.com/search",
            params={"q": query, "count": num},
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                              "(KHTML, like Gecko) Chrome/120 Safari/537.36"
            },
            timeout=10,
        )
        r.raise_for_status()
        page = r.text
    except Exception as e:
        return json.dumps({"error": f"联网搜索失败: {e}"}, ensure_ascii=False)

    results = []
    for block in re.split(r'<li class="b_algo"', page)[1:num + 1]:
        tm = re.search(r'<h2[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', block, re.S)
        if not tm:
            continue
        title = _strip_tags(tm.group(2))
        snippet = ""
        cm = re.search(r'<div class="b_caption">(.*?)</div>', block, re.S)
        if cm:
            pm = re.search(r'<p[^>]*>(.*?)</p>', cm.group(1), re.S)
            if pm:
                snippet = _strip_tags(pm.group(1))
                # 去掉 Bing 摘要开头的日期 "2016年4月21日" 及分隔符 "·"
                snippet = re.sub(r"^\s*(?:\d{4}年\d{1,2}月\d{1,2}日)?\s*·\s*", "", snippet)
        results.append({"title": title, "url": tm.group(1), "snippet": snippet})

    if not results:
        return json.dumps({"message": "未找到相关网页", "query": query}, ensure_ascii=False)
    return json.dumps({"query": query, "results": results}, ensure_ascii=False)


def _read_webpage(url: str, max_chars: int = 2000) -> str:
    """抓取指定网页正文（去脚本/样式/标签），返回 {url,title,text} 的紧凑 JSON；失败返回错误描述。"""
    log(f"📄 read_webpage 抓取: {url!r}")
    try:
        r = requests.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                              "(KHTML, like Gecko) Chrome/120 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            },
            timeout=12,
        )
        r.raise_for_status()
        ct = r.headers.get("Content-Type", "")
        if "charset" not in ct.lower():
            r.encoding = r.apparent_encoding or "utf-8"
        html = r.text
    except Exception as e:
        return json.dumps({"error": f"抓取网页失败: {e}"}, ensure_ascii=False)

    tm = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
    title = _strip_tags(tm.group(1)) if tm else ""
    body = re.sub(r"(?is)<(script|style|noscript|iframe)[^>]*>.*?</\1>", " ", html)
    body = re.sub(r"<[^>]+>", " ", body)
    body = unescape(body)
    body = re.sub(r"\s+", " ", body).strip()
    return json.dumps(
        {"url": url, "title": title, "text": body[:max_chars]},
        ensure_ascii=False,
    )


def _execute_tool(name: str, args: dict) -> str:
    """执行一个工具并返回字符串结果。后续新工具只需在这里加分支。"""
    log(f"🔧 调用工具 {name}({args})")
    if name == "search_db":
        return _search_db(str(args.get("query", "")), str(args.get("category", "all")))
    if name == "web_search":
        return _web_search(str(args.get("query", "")))
    if name == "read_webpage":
        return _read_webpage(str(args.get("url", "")))
    return json.dumps({"error": f"未知工具 {name}"}, ensure_ascii=False)


def _glm_tools(system: str, user: str, tools: list = None, model: str = None, max_turns: int = 4):
    """GLM function-calling 循环：模型可调用 tools 查知识，最终产出 JSON dict；失败返回 None。

    与 _glm_json 的区别：这里把 tools 传给模型，模型不确定时先查库再决定。
    若模型/API 不支持 function calling（抛错），返回 None，由上层回退到 _glm_json。
    """
    if not GLM_API_KEY:
        return None
    tools = tools or GAME_TOOLS
    try:
        from openai import OpenAI
        client = OpenAI(api_key=GLM_API_KEY, base_url=GLM_BASE_URL)
    except Exception as e:
        log(f"OpenAI 客户端初始化失败: {e}")
        return None

    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    for _ in range(max_turns):
        try:
            resp = client.chat.completions.create(
                model=model or GLM_ACTION_MODEL,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                temperature=0.2,
            )
        except Exception as e:
            log(f"GLM function-calling 失败: {e}")
            return None

        msg = resp.choices[0].message
        if not getattr(msg, "tool_calls", None):
            return _parse_json_result(msg.content)

        # 回填 assistant 的 tool_calls，再回填每个 tool 的执行结果
        messages.append({
            "role": "assistant",
            "content": msg.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments or "{}"},
                }
                for tc in msg.tool_calls
            ],
        })
        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except Exception:
                args = {}
            result = _execute_tool(tc.function.name, args)
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})

    return None


def _normalize_prefab(prefab):
    """剥离模型可能误带的数量后缀：flintx3 / flint x3 / flint×3 / meatballs(1) / meatballs=1 → 名字。"""
    p = (prefab or "").strip()
    p = re.sub(r"[xX×]\s*\d+$", "", p)   # flintx3 / flint x3 / flint×3
    p = re.sub(r"\(\d+\)$", "", p)        # meatballs(1)
    p = re.sub(r"[=:：]\s*\d+$", "", p)   # meatballs=1
    return p.strip()


def _validate_action(verb, prefab, inv, nearby, craftable, buildable):
    """校验 verb+prefab 是否真实可执行（宁可不做，不做错）。

    每个拒绝点都打日志，避免「动作没反应」时无从排查。prefab 来源由 skills 注册表的
    source 字段决定（inventory/nearby/craftable/buildable/none）。返回 {verb, prefab} 或 None。
    """
    src = skills.SOURCE_OF.get(verb)
    if src == "inventory" and prefab not in inv:
        log(f"拒绝动作 {verb}：prefab {prefab!r} 不在背包 {sorted(inv)}")
        return None
    if src == "nearby" and prefab not in nearby:
        log(f"拒绝动作 {verb}：prefab {prefab!r} 不在附近 {sorted(nearby)}")
        return None
    if src == "craftable" and prefab not in craftable:
        log(f"拒绝合成：prefab {prefab!r} 不在可合成名单 {sorted(craftable)}")
        return None
    if src == "buildable" and prefab not in buildable:
        log(f"拒绝建造：prefab {prefab!r} 不在可建造名单 {sorted(buildable)}")
        return None
    # src == "none"（sleep/explore）无需 prefab
    return {"verb": verb, "prefab": prefab}


def extract_action(advice: str, plan: str = "", state=None):
    """把 (实时状态 + AI 建议) 映射成一条可执行动作 {verb, prefab}（LLM 决策 + 白名单校验）。

    - 只允许 verb ∈ ACTION_VERBS；prefab 必须原样出现在真实「背包」「附近」或「可合成」
      列表里，杜绝模型凭空编 prefab。
    - 无明确动作 / GLM 失败 / 校验不过 → 返回 None（宁可不做，不做错）。
    """
    if state is None:
        state = get_current_state()
    if not state or state.get("status") == "empty":
        return None

    raw = state.get("state") or {}
    world = raw.get("world", {})
    players = raw.get("players", [])
    if isinstance(players, dict):
        players = list(players.values())
    if not players:
        return None
    player = players[0]
    inv = player.get("inventory") or {}
    nearby = player.get("nearby") or {}

    if not inv and not nearby:
        return None

    # 只给「纯名字」列表（不带数量），避免模型把 "flintx3" 当成一个词原样抄
    inv_s = "、".join(inv.keys()) or "无"
    nearby_s = "、".join(nearby.keys()) or "无"
    inv_cnt = "、".join(f"{k}={v}" for k, v in inv.items()) or "无"
    nearby_cnt = "、".join(f"{k}={v}" for k, v in nearby.items()) or "无"

    meta = game_meta.get_meta()
    craftable = meta["craftable"]
    buildable = meta.get("buildable", craftable)
    costs = meta["costs"]
    # 可合成列表带配方（有配方的显示材料），让 LLM 知道「能造什么、要什么、哪些贵」
    craft_parts = []
    for p in sorted(craftable):
        c = costs.get(p)
        if c:
            craft_parts.append(f"{p}(需{'、'.join(f'{m}×{n}' for m, n in c.items())})")
        else:
            craft_parts.append(p)
    craftable_s = "、".join(craft_parts) or "无"
    buildable_s = "、".join(sorted(buildable)) or "无"
    skill_lines = "\n".join(skills.prompt_lines())
    system = (
        "你是《饥荒》动作决策器。根据玩家当前状态和 AI 建议，决定一个立即执行的游戏动作。\n"
        "动作动词及 prefab 来源：\n"
        + skill_lines + "\n"
        "prefab 必须是列表里的一个完整名字，原样复制，不要加数量或任何其它字符。\n"
        "没有明确该做的动作、动作会危害玩家时，verb 返回 none。\n"
        "决定前若对某物品的用途/配方/成本/价值不确定，可先调用 search_db 工具查数据库，再据结果决定。\n"
        f'只输出 JSON，格式：{{"verb":"{skills.VERB_LIST}|none","prefab":"prefab名","reason":"一句话理由"}}'
    )
    user = (
        f"玩家状态：生命{player.get('health')} 饥饿{player.get('hunger')} 精神{player.get('sanity')} "
        f"时段{world.get('phase')}\n"
        f"背包（名字）：{inv_s}\n"
        f"背包数量：{inv_cnt}\n"
        f"附近（名字）：{nearby_s}\n"
        f"附近数量：{nearby_cnt}\n"
        f"可合成：{craftable_s}\n"
        f"可建造：{buildable_s}\n"
        f"AI 建议：{advice or '（无）'}"
    )
    result = _glm_tools(system, user) or _glm_json(system, user)
    if not isinstance(result, dict):
        log("拒绝动作：GLM 决策无有效输出（API 失败或返回非 JSON）")
        return None

    verb = (result.get("verb") or "").strip().lower()
    prefab = _normalize_prefab(result.get("prefab"))
    if verb in ("none", ""):
        return None
    if verb not in ACTION_VERBS:
        log(f"拒绝动作：verb {verb!r} 不在白名单 {ACTION_VERBS}")
        return None
    return _validate_action(verb, prefab, inv, nearby, craftable, buildable)


def tick(last_summary: str, last_fire: float, voice_query: str = "", vision_summary: str = "", image_files=None):
    """一轮：取状态 → 判断是否触发 → 调 Dify → 消费输出(播报+记忆) → 回灌。

    返回 (新 last_summary, 新 last_fire)。
    """
    state = get_current_state()
    summary = ""
    if state and state.get("status") != "empty":
        summary = state.get("summary", "")

    has_multimodal = bool(voice_query or vision_summary or image_files)
    alerted = "⚠️" in summary or "状态告警" in summary

    # —— 触发判断 ——
    if not has_multimodal:
        # 仅状态驱动：无状态或未告警都不触发
        if not summary:
            log("暂无游戏状态（先启动 game/dst_mod/bridge 跑起来）")
            return summary, last_fire
        if not alerted:
            return summary, last_fire
        now = time.time()
        if now - last_fire < ALERT_COOLDOWN:
            log("有告警但处于冷却期，跳过")
            return summary, last_fire
    else:
        now = time.time()  # 多模态输入是玩家主动提问，不带冷却

    memory, last_action = load_memory()
    inputs = {
        "goal": GOAL,
        "memory": memory,
        "last_action": last_action,
        "voice_query": voice_query,
        "vision_summary": vision_summary,
    }
    log(f"触发 Dify 工作流…" + (f"\n{summary}" if summary else "（无状态，纯多模态输入）"))
    outputs = run_dify(inputs, image_files=image_files)
    if outputs is None:
        return summary, last_fire

    advice = extract_advice(outputs)
    plan = extract_plan(outputs)

    # 结构化输出消费：打印 + 持久化为跨轮记忆
    if plan:
        log(f"结构化计划(plan): {plan[:400]}")
    if advice:
        ok = push_advice(advice)
        log(f"{'✅ 已回灌' if ok else '❌ 回灌失败'}: {advice}")
    elif plan:
        log("工作流只产出结构化计划、未产出可播报建议")

    # —— Phase 3：告警/多模态都走 LLM 动作决策（search_db/web_search/read_webpage 工具）——
    # 只要拿到了 Dify 建议，就尝试映射成一条可执行动作并推动作队列；
    # extract_action 内部有 verb 白名单 + prefab 必须在背包/附近 的双重校验，无效则返回 None（宁可不做）。
    if advice:
        action = extract_action(advice, plan, state)
        if action:
            ok = push_action(action["verb"], action["prefab"])
            log(f"{'✅ 已推动作' if ok else '❌ 推动作失败'}: {action['verb']} {action['prefab']}")

    # 持久化：plan 作为长期记忆，advice 作为上轮动作（缺省时保留旧值）
    save_memory(plan if plan else memory, advice if advice else last_action)
    return summary, now


def main():
    global GOAL
    parser = argparse.ArgumentParser(description="Dify 版饥荒生存规划大脑（闭环 + 记忆 + 多模态）")
    parser.add_argument("--once", action="store_true", help="单次运行后退出（联调用）")
    parser.add_argument("--voice", metavar="音频文件", help="语音输入（wav/mp3…），先转文字再交给工作流")
    parser.add_argument("--vision", metavar="图片/视频", help="图片/视频输入，原生上传给 Dify 视觉模型（视频先抽帧成图）")
    parser.add_argument("--goal", default=GOAL, help="生存目标（覆盖默认值）")
    args = parser.parse_args()

    GOAL = args.goal

    log(f"状态服务: {STATE_API}")
    log(f"Dify 工作流: {DIFY_API_URL}")
    log(f"目标: {GOAL}")
    log(f"记忆文件: {MEMORY_FILE}")

    voice_query = run_transcribe(args.voice) if args.voice else ""
    image_files = upload_images([args.vision]) if args.vision else []
    if voice_query:
        log(f"语音识别结果: {voice_query}")
    if image_files:
        log(f"已上传 {len(image_files)} 张图给 Dify 原生视觉")

    if args.once:
        tick("", 0.0, voice_query=voice_query, image_files=image_files)
        return

    if args.voice or args.vision:
        log("提示：--voice/--vision 仅在 --once 模式下生效，常驻模式只做状态轮询。")

    log(f"开始常驻轮询（间隔 {POLL_INTERVAL}s，冷却 {ALERT_COOLDOWN}s）…")
    last_summary = ""
    last_fire = 0.0
    while True:
        try:
            msg = poll_panel_query()
            if msg:
                log(f"面板消息: {msg}")
                last_summary, last_fire = tick(last_summary, last_fire, voice_query=msg)
            else:
                last_summary, last_fire = tick(last_summary, last_fire)
        except Exception as e:
            log(f"本轮异常: {e}")
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
