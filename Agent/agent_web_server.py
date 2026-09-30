#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
agent_web_server.py — 「小A」电脑管家 的 codex 风格网页界面后端

给原本只有终端黑窗口的 agent_web.py 套一个浏览器界面：
  - 深色终端质感前端（agent_web.html，同目录，单文件）
  - 对话流 + 命令执行卡片（真实执行 + 逐条确认）
  - 三种人设切换（小A / 王老师 / SysAdmin）

命令执行用 GLM function calling（execute_command 工具）：
  模型返回 tool_call → 后端不立即执行，先回传给前端展示命令卡片
  → 用户点「运行」POST /run → subprocess 执行 → stdout 回填 → 模型继续
  → 直到模型返回纯文本（总结）结束本轮。

复用 live_agent/dify_brain.py 的智谱调用方式：OpenAI SDK + 兼容端点。
"""
import json
import os
import subprocess
import threading
import sys
from datetime import datetime

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_file
from openai import OpenAI

# 修复 Windows 控制台 GBK 编码（日志输出用）
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

API_KEY = os.getenv("ZHIPU_API_KEY", "")
BASE_URL = "https://open.bigmodel.cn/api/paas/v4/"
MODEL = os.getenv("XIAOA_MODEL", "glm-4-flash")

PORT = int(os.getenv("XIAOA_PORT", "5003"))
CMD_TIMEOUT = 60          # 单条命令执行上限（秒）
OUTPUT_LIMIT = 20000      # 回显输出截断（字符）

app = Flask(__name__)

# ============ 人设配置（沿用 agent_web.py） ============
PERSONA_CONFIG = {
    "buddy":   ("小A - 你的电脑管家",     "Agent_v2.md",            "拜拜！有需要随时找我哦~ 👋"),
    "teacher": ("王老师 - 计算机教学助手", "persona_teacher_v2.md",  "下课！回去记得复习今天的知识点哦~"),
    "strict":  ("SysAdmin - 系统管理员",   "persona_strict_v2.md",  "会话结束。"),
}

# ============ execute_command 工具定义（GLM function calling） ============
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "execute_command",
            "description": (
                "执行一条 Windows 系统命令（如 dir、type、copy、move、del、ipconfig、"
                "mkdir 等），返回标准输出与错误输出。用于文件管理、目录浏览、系统查询等操作。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "要执行的完整 Windows 命令（单条）",
                    }
                },
                "required": ["command"],
            },
        },
    }
]


def build_system_prompt(persona: str) -> str:
    """按人设构建系统提示词：日期 + 命令执行说明 + 人设内容。"""
    display_name, persona_file, _ = PERSONA_CONFIG[persona]
    path = os.path.join(BASE_DIR, persona_file)
    with open(path, "r", encoding="utf-8") as f:
        persona_content = f.read()

    today = datetime.now().strftime("%Y-%m-%d")
    return f"""今天日期是 {today}。

你是「{display_name}」，一个运行在 Windows 电脑上的智能助手。

你可以调用 execute_command 工具来执行 Windows 系统命令。规则：
- 当用户的任务需要操作文件、浏览目录、查询系统信息时，调用 execute_command。
- 一次只执行一条命令，等拿到结果后再决定下一步。
- 如果任务不需要执行命令，直接给出文本回答即可，不要强行调用工具。
- 对危险操作（删除、格式化、关机等）要先说明风险。

{persona_content}
"""


# ============ 会话状态（单会话，人设切换即重置） ============
_state_lock = threading.Lock()
_session = {
    "persona": "buddy",
    "messages": [{"role": "system", "content": build_system_prompt("buddy")}],
    "pending": None,  # {"assistant_msg": dict, "tool_call": dict, "command": str}
}


def _reset(persona: str):
    with _state_lock:
        _session["persona"] = persona
        _session["messages"] = [{"role": "system", "content": build_system_prompt(persona)}]
        _session["pending"] = None


def _call_glm(messages):
    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
    return client.chat.completions.create(
        model=MODEL,
        messages=messages,
        tools=TOOLS,
        tool_choice="auto",
    )


def _extract_command(msg):
    """从 GLM 返回的 message 解析出 tool_call（execute_command）。无则返回 None。"""
    tcs = getattr(msg, "tool_calls", None) or []
    for tc in tcs:
        if tc.function.name == "execute_command":
            try:
                args = json.loads(tc.function.arguments or "{}")
            except Exception:
                args = {}
            command = (args.get("command") or "").strip()
            if command:
                return {"assistant_msg": msg, "tool_call": tc, "command": command}
    return None


def _assistant_to_dict(msg):
    """把 assistant message 转成可回填 messages 的 dict（含 tool_calls）。"""
    d = {"role": "assistant", "content": getattr(msg, "content", None) or ""}
    tcs = getattr(msg, "tool_calls", None) or []
    if tcs:
        d["tool_calls"] = [
            {
                "id": tc.id,
                "type": tc.type or "function",
                "function": {"name": tc.function.name, "arguments": tc.function.arguments},
            }
            for tc in tcs
        ]
    return d


def execute_command(command: str) -> dict:
    """真实执行一条 Windows 命令，返回 {command, stdout, stderr, status}。"""
    try:
        # 不指定 encoding，走系统 locale（Windows 中文 = GBK），errors 兜底防崩溃
        r = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            timeout=CMD_TIMEOUT, errors="replace",
        )
        out = (r.stdout or "").strip()[:OUTPUT_LIMIT]
        err = (r.stderr or "").strip()[:OUTPUT_LIMIT]
        status = "ok" if r.returncode == 0 else f"exit:{r.returncode}"
        return {"command": command, "stdout": out, "stderr": err, "status": status}
    except subprocess.TimeoutExpired:
        return {"command": command, "stdout": "", "stderr": f"命令执行超时（>{CMD_TIMEOUT}s）", "status": "timeout"}
    except Exception as e:
        return {"command": command, "stdout": "", "stderr": str(e), "status": "error"}


def _tool_result_text(executed: dict) -> str:
    """把执行结果拼成回填给模型的 tool content。"""
    return (
        f"命令: {executed['command']}\n"
        f"状态: {executed['status']}\n"
        f"标准输出:\n{executed['stdout'] or '(空)'}\n"
        f"标准错误:\n{executed['stderr'] or '(空)'}"
    )


# ============ 路由 ============
@app.route("/")
def index():
    return send_file(os.path.join(BASE_DIR, "agent_web.html"))


@app.route("/personas")
def personas():
    return jsonify({k: v[0] for k, v in PERSONA_CONFIG.items()})


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(force=True) or {}
    message = (data.get("message") or "").strip()
    persona = data.get("persona") or "buddy"
    if persona not in PERSONA_CONFIG:
        persona = "buddy"
    if not message:
        return jsonify({"error": "empty message"}), 400
    if not API_KEY:
        return jsonify({"error": "未配置 ZHIPU_API_KEY"}), 500

    with _state_lock:
        if _session["persona"] != persona:
            _reset(persona)
        messages = _session["messages"]
        messages.append({"role": "user", "content": message})
        try:
            resp = _call_glm(messages)
        except Exception as e:
            messages.pop()
            return jsonify({"error": f"GLM 调用失败: {e}"}), 500

        msg = resp.choices[0].message
        cmd = _extract_command(msg)
        if cmd:
            _session["pending"] = cmd
            return jsonify({"type": "command", "command": cmd["command"], "name": "execute_command"})

        content = getattr(msg, "content", None) or ""
        messages.append({"role": "assistant", "content": content})
        return jsonify({"type": "text", "content": content})


@app.route("/run", methods=["POST"])
def run():
    data = request.get_json(force=True) or {}
    approve = bool(data.get("approve", True))

    with _state_lock:
        pending = _session.get("pending")
        if not pending:
            return jsonify({"error": "没有待执行的命令"}), 400

        _session["pending"] = None
        messages = _session["messages"]
        messages.append(_assistant_to_dict(pending["assistant_msg"]))

        if approve:
            executed = execute_command(pending["command"])
        else:
            executed = {"command": pending["command"], "stdout": "", "stderr": "", "status": "rejected"}

        tool_content = _tool_result_text(executed) if approve else "用户拒绝执行该命令。"
        messages.append({
            "role": "tool",
            "tool_call_id": pending["tool_call"].id,
            "content": tool_content,
        })

        try:
            resp = _call_glm(messages)
        except Exception as e:
            return jsonify({"error": f"GLM 调用失败: {e}"}), 500

        msg = resp.choices[0].message
        next_cmd = _extract_command(msg)
        if next_cmd:
            _session["pending"] = next_cmd
            return jsonify({
                "executed": executed,
                "next": {"type": "command", "command": next_cmd["command"], "name": "execute_command"},
            })

        content = getattr(msg, "content", None) or ""
        messages.append({"role": "assistant", "content": content})
        return jsonify({
            "executed": executed,
            "next": {"type": "text", "content": content},
        })


@app.route("/reset", methods=["POST"])
def reset():
    data = request.get_json(force=True) or {}
    persona = data.get("persona") or _session["persona"]
    if persona not in PERSONA_CONFIG:
        persona = "buddy"
    _reset(persona)
    return jsonify({"status": "ok", "persona": persona})


if __name__ == "__main__":
    if not API_KEY:
        print("[agent_web] ⚠️ 未设置 ZHIPU_API_KEY，请在 Agent/.env 里配置")
    print(f"[agent_web] 人设: {', '.join(PERSONA_CONFIG)}")
    print(f"[agent_web] 模型: {MODEL}  端口: {PORT}")
    print(f"[agent_web] 打开 http://127.0.0.1:{PORT}")
    app.run(host="127.0.0.1", port=PORT, debug=False, threaded=True)
