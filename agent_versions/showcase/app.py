#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""app.py — 三版本 Agent 对比 · 全栈展示（Flask 后端）。

主页三张卡片分别进入三个引擎的对话页；后端把三个引擎统一成一个接口：

    POST /api/chat   {"engine": "native"|"langgraph"|"dify", "query": "..."}
    → {"answer": "..."}

  - native     → 直接 import native/agent.py 的 run()
  - langgraph  → 直接 import langgraph/agent.py 编译好的 graph
  - dify       → 复用 dify/import_to_dify.py 的自签 JWT，跑已发布应用的 draft-run

用法：
  cd agent_versions/showcase
  pip install -r requirements.txt
  python app.py            # 打开 http://localhost:5100
"""
import functools
import json
import os
import re
import secrets
import sys
import threading
import time
from urllib.parse import quote

import jwt
import requests
from flask import Flask, jsonify, redirect, request, send_from_directory

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)  # agent_versions/
GIT_ROOT = os.path.dirname(ROOT)  # C:\DLdata\git（live_agent 在 dont_starve_bot 下）
LIVE_DIR = os.path.join(GIT_ROOT, "dont_starve_bot", "live_agent")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "dify"))

# 加载 .env（不依赖 python-dotenv）
def _load_dotenv(path=None):
    if path is None:
        path = os.path.join(BASE, ".env")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v

_load_dotenv()

# MySQL 用户存储（可选）：没装 SQLAlchemy 或没配 MYSQL_URL 时 db=None，回退 users.json
try:
    import db
except Exception:
    db = None

# 已发布的 Dify 应用（deepseek 变体）
DIFY_APP_ID = os.getenv("DIFY_APP_ID", "4c967095-8bbb-4ed4-875a-e2322f8809dc")
DIFY_WEB_URL = f"http://localhost/app/{DIFY_APP_ID}"

app = Flask(__name__, static_folder="static", static_url_path="/static")

# 外部媒体目录（视频等素材，如 C:\DLdata\git\PH\1）
PH_MEDIA_DIR = os.path.join(GIT_ROOT, "PH", "1")


@app.route("/media/<path:filename>")
def serve_media(filename):
    return send_from_directory(PH_MEDIA_DIR, filename)

# --- 三个引擎：导入失败就降级，不影响其它引擎 ---
_native_run = _native_err = None
_lg_graph = _lg_err = None
try:
    from native.agent import run as _native_run  # noqa: E402
except Exception as e:  # pragma: no cover
    _native_err = str(e)
try:
    from langgraph.agent import graph as _lg_graph  # noqa: E402
except Exception as e:  # pragma: no cover
    _lg_err = str(e)

# Dify 认证与 draft-run（复用已有脚本，避免重复实现）
from import_to_dify import make_auth, read_secret_key  # noqa: E402

# 真实游戏大脑（Dify 链 app 3ff0efd8 + GLM 动作决策 + state_api 回灌）
# 导入即触发 live_agent/.env 载入（ZHIPU_API_KEY / DIFY_API_KEY），失败则降级不影响其它引擎。
_brain = _brain_err = None
try:
    if LIVE_DIR not in sys.path:
        sys.path.insert(0, LIVE_DIR)
    import dify_brain as _brain  # noqa: E402
except Exception as e:  # pragma: no cover
    _brain_err = str(e)

DIFY_RUN_URL = "http://localhost/console/api/apps/{app_id}/workflows/draft/run"

# --- 对话历史（按引擎持久化到本地 JSON 文件，刷新/切换页面不丢）---
HISTORY_FILE = os.path.join(BASE, "history.json")
_history_lock = threading.Lock()
_HISTORY_MAX = 200  # 每个引擎最多保留的消息条数


def _load_history():
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_history(h):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(h, f, ensure_ascii=False, indent=2)


# 历史按用户隔离：登录后按 openid 存，未登录（登录未启用）用 "anon"
def _uid():
    u = getattr(request, "user", None) or {}
    return u.get("openid", "anon")


def _history_append(engine, role, text):
    with _history_lock:
        h = _load_history()
        per_user = h.setdefault(_uid(), {})
        msgs = per_user.setdefault(engine, [])
        msgs.append({"role": role, "text": text, "ts": int(time.time())})
        per_user[engine] = msgs[-_HISTORY_MAX:]
        _save_history(h)


# ============ 微信登录 / 鉴权（开发调试用微信「测试号」） ============
# 个人主体无法创建开放平台「网站应用」，所以本地/个人调试走公众平台「测试号」的网页授权
# （snsapi_userinfo）：扫码后能拿到 openid + 昵称头像，流程与正式完全一致；上线时把
# appid/secret 换成认证服务号（企业）的即可，或改用开放平台网站应用扫码（snsapi_login）。
WX_APPID = os.getenv("WX_APPID", "")
WX_SECRET = os.getenv("WX_SECRET", "")
WX_REDIRECT_URI = os.getenv("WX_REDIRECT_URI", "http://127.0.0.1:5100/auth/wechat/callback")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://127.0.0.1:5100/auth/google/callback")
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me")
TOKEN_TTL = 60 * 60 * 24 * 7  # 7 天

# 登录「可选」不强制：配了哪个提供商，登录页就亮哪个按钮；全都没配则整站游客态照常跑。
WX_ENABLED = bool(WX_APPID and WX_SECRET)
GOOGLE_ENABLED = bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)
AUTH_ENABLED = WX_ENABLED or GOOGLE_ENABLED

USERS_FILE = os.path.join(BASE, "users.json")
_users_lock = threading.Lock()
_pending_states = {}  # state -> 过期时间戳（单进程内存即可，用于防 CSRF）
_pending_auth = {}    # state -> {"token","user","ts"}：手机授权成功后暂存，PC 轮询一次性取走

# 游客提问限额：不登录最多问 GUEST_QUOTA 个问题（对话/对比/大脑三入口共享），登录后不限。
GUEST_QUOTA = 3
ANON_COOKIE = "anon_id"
_anon_quota = {}      # anon_id -> 已问问题数（单进程内存即可）
_quota_lock = threading.Lock()


def _authorize_url(state):
    """拼微信网页授权 URL。PC 浏览器不能直接打开它（微信会拦「请在微信客户端打开链接」），
    只能把它做成二维码让手机微信扫 —— 扫码后微信在手机端完成授权并回跳 redirect_uri。"""
    return ("https://open.weixin.qq.com/connect/oauth2/authorize"
            f"?appid={WX_APPID}"
            f"&redirect_uri={quote(WX_REDIRECT_URI, safe='')}"
            "&response_type=code&scope=snsapi_userinfo"
            f"&state={state}#wechat_redirect")


def _load_users():
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            d = json.load(f)
            return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _save_users(u):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(u, f, ensure_ascii=False, indent=2)


def _upsert_user(openid, nickname, avatar):
    # 优先落 MySQL（只存登录/账号数据）；没配或连不上则回退 users.json
    if db is not None:
        u = db.get_or_create_user(openid, nickname, avatar)
        if u is not None:
            return u
    with _users_lock:
        users = _load_users()
        u = users.setdefault(openid, {})
        u["openid"] = openid
        u["nickname"] = nickname or u.get("nickname", "")
        u["avatar"] = avatar or u.get("avatar", "")
        u["updated_at"] = int(time.time())
        u.setdefault("created_at", int(time.time()))
        _save_users(users)
        return u


def _sign_token(u):
    payload = {"openid": u["openid"], "nickname": u["nickname"],
               "avatar": u.get("avatar", ""), "exp": int(time.time()) + TOKEN_TTL}
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def _decode_token(token):
    if not token:
        return None
    if token.startswith("Bearer "):
        token = token[7:]
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except Exception:
        return None


def _current_user():
    return _decode_token(request.headers.get("Authorization", ""))


@app.before_request
def _attach_user():
    """登录「可选」：带有效 token 就按账号隔离历史；没带则以游客身份（anon）照常使用。"""
    request.user = _current_user()


def _anon_id():
    """游客匿名标识：首次请求生成并写 cookie，之后靠 cookie 稳定计数。"""
    cached = getattr(request, "_anon_id_cached", None)
    if cached:
        return cached
    aid = request.cookies.get(ANON_COOKIE)
    if not aid:
        aid = secrets.token_urlsafe(12)
        request._anon_new = aid
    request._anon_id_cached = aid
    return aid


@app.after_request
def _set_anon_cookie(resp):
    """游客匿名 cookie 首次生成时写回浏览器，后续请求据此计数。"""
    aid = getattr(request, "_anon_new", None)
    if aid:
        resp.set_cookie(ANON_COOKIE, aid, max_age=60 * 60 * 24 * 365,
                        httponly=True, samesite="Lax")
    return resp


def _guest_consume():
    """游客问一题：未超限则计数并放行，超限返回 False；登录用户直接放行。"""
    u = getattr(request, "user", None) or {}
    if u.get("openid"):
        return True
    with _quota_lock:
        aid = _anon_id()
        n = _anon_quota.get(aid, 0)
        if n >= GUEST_QUOTA:
            return False
        _anon_quota[aid] = n + 1
        return True


@app.get("/auth/config")
def auth_config():
    """前端启动时读：启用了哪些登录方式 + 当前已登录用户（回显昵称/头像）。"""
    return jsonify({
        "enabled": AUTH_ENABLED,
        "wechat": WX_ENABLED,
        "google": GOOGLE_ENABLED,
        "user": _current_user(),
    })


@app.get("/auth/quota")
def auth_quota():
    """游客提问额度回显：前端据此显示剩余次数、决定是否弹滑块/拦截。"""
    logged = bool((getattr(request, "user", None) or {}).get("openid"))
    used = 0 if logged else _anon_quota.get(_anon_id(), 0)
    return jsonify({
        "limit": GUEST_QUOTA,
        "used": used,
        "remaining": max(0, GUEST_QUOTA - used),
        "logged_in": logged,
    })


@app.get("/auth/wechat/login")
def wechat_login():
    if not WX_ENABLED:
        return jsonify({"error": "未配置 WX_APPID / WX_SECRET（见 .env.example）"}), 500
    state = secrets.token_urlsafe(16)
    with _users_lock:
        _pending_states[state] = time.time() + 600  # 10 分钟有效
    return jsonify({"state": state})


@app.get("/auth/wechat/qrcode")
def wechat_qrcode():
    """把授权 URL 渲染成二维码 PNG，PC 页面 <img> 直接展示，手机微信扫它。"""
    state = request.args.get("state", "")
    with _users_lock:
        valid = state in _pending_states and _pending_states[state] > time.time()
    if not valid:
        return jsonify({"error": "二维码已过期，请重新点击登录"}), 410
    try:
        import io
        import qrcode
    except Exception:
        return jsonify({"error": "缺少 qrcode/Pillow：pip install qrcode[pil]"}), 500
    qr = qrcode.QRCode(border=2)
    qr.add_data(_authorize_url(state))
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return app.response_class(buf.getvalue(), mimetype="image/png")


@app.get("/auth/status")
def auth_status():
    """PC 端轮询：手机扫码授权成功后，这里把 token + 用户一次性交给 PC。"""
    state = request.args.get("state", "")
    with _users_lock:
        rec = _pending_auth.get(state)
        if rec:
            _pending_auth.pop(state, None)
            return jsonify({"ok": True, "token": rec["token"], "user": rec["user"]})
        if state in _pending_states and _pending_states[state] < time.time():
            _pending_states.pop(state, None)
            return jsonify({"ok": False, "expired": True})
    return jsonify({"ok": False})


def _auth_page(title, msg):
    return ("<!doctype html><html lang=zh-CN><meta charset=utf-8>"
            "<meta name=viewport content='width=device-width,initial-scale=1'>"
            f"<title>{title}</title><body style='font-family:sans-serif;text-align:center;"
            f"padding:60px 20px'><h2>{title}</h2><p>{msg}</p></body></html>")


@app.get("/auth/wechat/callback")
def wechat_callback():
    # 本路由是手机微信扫码授权后回跳的地址（redirect_uri），落地在手机上，不是 PC。
    code = request.args.get("code")
    state = request.args.get("state")
    with _users_lock:
        valid = state in _pending_states and _pending_states.pop(state, 0) > time.time()
    if not code or not valid:
        return _auth_page("授权失败", "state 校验不通过或二维码已过期，请回到电脑页面重新扫码。")

    r = requests.get("https://api.weixin.qq.com/sns/oauth2/access_token",
                     params={"appid": WX_APPID, "secret": WX_SECRET,
                             "code": code, "grant_type": "authorization_code"},
                     timeout=10)
    d = r.json()
    if "errcode" in d or "openid" not in d:
        return _auth_page("授权失败", "换取 access_token 失败：" + str(d.get("errmsg", d)))
    openid, web_at = d["openid"], d["access_token"]

    nickname, avatar = "", ""
    try:
        resp = requests.get("https://api.weixin.qq.com/sns/userinfo",
                            params={"access_token": web_at, "openid": openid, "lang": "zh_CN"},
                            timeout=10)
        resp.encoding = "utf-8"  # 微信 userinfo 是 UTF-8 但响应头常缺 charset，强制按 UTF-8 解码，避免昵称乱码
        info = resp.json()
        nickname, avatar = info.get("nickname", ""), info.get("headimgurl", "")
    except Exception:
        pass  # 拿不到昵称头像不影响登录

    u = _upsert_user(openid, nickname, avatar)
    token = _sign_token(u)
    user = {"openid": u["openid"], "nickname": u["nickname"], "avatar": u.get("avatar", "")}
    with _users_lock:
        _pending_auth[state] = {"token": token, "user": user, "ts": time.time() + 120}
    return _auth_page("授权成功", "请回到电脑页面，页面会自动登录。")


# ---- Google 登录（PC 浏览器直接跳转即可，无需二维码/轮询）----
@app.get("/auth/google/login")
def google_login():
    if not GOOGLE_ENABLED:
        return jsonify({"error": "未配置 GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET（见 .env.example）"}), 500
    state = secrets.token_urlsafe(16)
    with _users_lock:
        _pending_states[state] = time.time() + 600  # 10 分钟有效
    url = ("https://accounts.google.com/o/oauth2/v2/auth"
           f"?client_id={GOOGLE_CLIENT_ID}"
           f"&redirect_uri={quote(GOOGLE_REDIRECT_URI, safe='')}"
           "&response_type=code&scope=openid%20email%20profile"
           f"&state={state}&prompt=select_account")
    return redirect(url)


@app.get("/auth/google/callback")
def google_callback():
    code = request.args.get("code")
    state = request.args.get("state")
    with _users_lock:
        valid = state in _pending_states and _pending_states.pop(state, 0) > time.time()
    if not code or not valid:
        return _auth_page("授权失败", "state 校验不通过或已过期，请重新登录。")

    r = requests.post("https://oauth2.googleapis.com/token",
                      data={"code": code, "client_id": GOOGLE_CLIENT_ID,
                            "client_secret": GOOGLE_CLIENT_SECRET,
                            "redirect_uri": GOOGLE_REDIRECT_URI,
                            "grant_type": "authorization_code"},
                      timeout=10)
    d = r.json()
    if "access_token" not in d:
        return _auth_page("授权失败", "换取 access_token 失败：" + str(d.get("error_description", d.get("error", d))))
    at = d["access_token"]

    # sub 是账号唯一 ID，name 昵称，picture 头像
    info = requests.get("https://www.googleapis.com/oauth2/v3/userinfo",
                        headers={"Authorization": "Bearer " + at}, timeout=10).json()
    sub = info.get("sub", "")
    if not sub:
        return _auth_page("授权失败", "未取到 Google 用户信息")

    u = _upsert_user(sub, info.get("name", ""), info.get("picture", ""))
    token = _sign_token(u)
    return redirect(f"/?token={token}")


def _strip_think(text: str) -> str:
    """deepseek 推理模型会输出 <think>...</think> 前缀，剥掉只留正文。"""
    return re.sub(r"<think>.*?</think>", "", text or "", flags=re.S).strip()


def dify_answer(query: str) -> str:
    headers = make_auth(read_secret_key())
    r = requests.post(
        DIFY_RUN_URL.format(app_id=DIFY_APP_ID),
        headers=headers,
        json={"inputs": {"query": query}},
        stream=True,
        timeout=180,
    )
    r.raise_for_status()
    final = None
    for raw in r.iter_lines(decode_unicode=True):
        if not raw or not raw.startswith("data: "):
            continue
        try:
            obj = json.loads(raw[len("data: "):])
        except Exception:
            continue
        if obj.get("event") == "workflow_finished":
            final = obj.get("data", {}).get("outputs", {})
    return _strip_think((final or {}).get("answer", ""))


@app.get("/")
def index():
    return app.send_static_file("index.html")


@app.get("/api/config")
def config():
    """前端读取 Dify 已发布应用地址（卡片上的「在 Dify 打开」链接）。"""
    return jsonify({"dify_web_url": DIFY_WEB_URL})


@app.get("/api/history")
def history():
    engine = request.args.get("engine")
    with _history_lock:
        h = _load_history()
    mine = h.get(_uid(), {})
    if engine:
        return jsonify({"messages": mine.get(engine, [])})
    return jsonify({"messages": mine})


@app.post("/api/history/clear")
def history_clear():
    engine = (request.get_json(force=True, silent=True) or {}).get("engine")
    with _history_lock:
        h = _load_history()
        if engine:
            h.setdefault(_uid(), {}).pop(engine, None)
        else:
            h[_uid()] = {}
        _save_history(h)
    return jsonify({"ok": True})


@app.post("/api/chat")
def chat():
    data = request.get_json(force=True, silent=True) or {}
    engine = data.get("engine")
    query = (data.get("query") or "").strip()
    save = bool(data.get("save"))  # 只有对话页传 save=true 才落历史，并排对比不落
    # 提问计费：对话页 save=true 默认计一次；并排对比三个引擎，由前端指定其中一个带 consume=true 只计一次
    consume = bool(data.get("consume", save))
    if not query:
        return jsonify({"error": "问题不能为空"}), 400
    if engine not in ("native", "langgraph", "dify"):
        return jsonify({"error": f"未知引擎：{engine}"}), 400
    if consume and not _guest_consume():
        return jsonify({"error": f"游客最多问 {GUEST_QUOTA} 个问题，请登录后继续", "code": "QUOTA"}), 403

    if save:
        _history_append(engine, "user", query)

    def fail(msg):
        if save:
            _history_append(engine, "err", msg)
        return jsonify({"error": msg}), 500

    try:
        if engine == "native":
            if _native_run is None:
                return fail(f"native 引擎不可用：{_native_err}")
            answer = _native_run(query)
        elif engine == "langgraph":
            if _lg_graph is None:
                return fail(f"langgraph 引擎不可用：{_lg_err}")
            answer = _lg_graph.invoke({"query": query}).get("answer", "")
        else:  # dify
            answer = dify_answer(query)
    except Exception as e:  # 引擎内抛异常也要返回 JSON，避免前端拿到 HTML 500
        return fail(f"{engine} 引擎调用失败：{e}")

    answer = _with_game_action(answer, query)
    if save:
        _history_append(engine, "bot", answer)
    return jsonify({"answer": answer})


# ---------- 游戏大脑控制台（真实 Dify 链 + 动作回灌） ----------

STATE_API = "http://127.0.0.1:5002"


def _action_results():
    """读 state_api 时间线里最近的「动作执行结果」，供控制台显示角色是否真的执行了。"""
    try:
        snap = requests.get(f"{STATE_API}/panel/snapshot", timeout=3).json()
    except Exception:
        return []
    events = snap.get("events") or []
    return [e for e in events if e.get("type") == "result"][-5:]


# 中文动作名（单一数据源在 skills.VERB_CN；游戏大脑未加载时降级为空，回退到原 verb）
try:
    import skills
    _VERB_CN = skills.VERB_CN
except Exception:
    _VERB_CN = {}

# 顾问文本里常见的“我做不到”推辞话术 —— 动作其实已经下发时，用它替换掉，避免自相矛盾
_REFUSAL_MARKERS = (
    "无法直接操作", "无法操作游戏", "无法直接控制", "无法控制游戏",
    "不能直接控制", "没法直接远程", "无法直接远程", "不能直接操作",
    "很抱歉，作为", "抱歉，作为", "作为一个文本", "作为文本助手",
)


def _with_game_action(text, query=""):
    """把引擎的文本回答接上真实游戏控制：读实时状态 → 映射成可执行动作 → 推入队列。

    只在游戏在跑（有实时状态）时生效；否则原样返回纯文本。动作决策优先用用户的「原话」
    （“去砍树”“我饿了”这类直接指令），其次才是回答文本——否则通用生存建议几乎映射不出
    具体动作。prefab 由 dify_brain.extract_action 白名单校验（必须在真实背包/附近），
    无效则宁可不做。
    """
    if _brain is None:
        return text
    try:
        state = _brain.get_current_state()
        if not state or state.get("status") == "empty":
            return text
        action = _brain.extract_action(query or text, "", state)
        if not action or not _brain.push_action(action["verb"], action["prefab"]):
            return text
        verb_cn = _VERB_CN.get(action["verb"], action["verb"])
        done = f"🎮 已指挥角色执行：{action['verb']} {action['prefab']}"
        # 顾问文本在推辞、而动作已真正下发时，用一句确定的“已指挥”替代推辞，别让用户看到自相矛盾
        if any(m in (text or "") for m in _REFUSAL_MARKERS):
            return f"已接入你的游戏，我现在就让角色执行：{verb_cn} {action['prefab']}。\n\n{done}"
        return text + f"\n\n{done}"
    except Exception:
        pass
    return text


@app.get("/api/brain/state")
def brain_state():
    """读当前游戏状态 + 大脑记忆/目标 + 最近动作结果（供控制台展示）。"""
    if _brain is None:
        return jsonify({"error": f"游戏大脑不可用：{_brain_err}"}), 500
    try:
        state = _brain.get_current_state()
        memory, last_action = _brain.load_memory()
        return jsonify({
            "state": state,
            "goal": _brain.GOAL,
            "memory": memory,
            "last_action": last_action,
            "results": _action_results(),
        })
    except Exception as e:
        return jsonify({"error": f"读取大脑状态异常：{e}"}), 500


@app.post("/api/brain")
def brain_run():
    """把用户指令当作 voice_query 交给真实大脑跑一轮：
    Dify 链规划/建议 → GLM 动作决策 → 回灌 state_api（bridge/mod 在跑时才会真正执行）。"""
    if _brain is None:
        return jsonify({"error": f"游戏大脑不可用：{_brain_err}"}), 500
    query = (request.get_json(force=True, silent=True) or {}).get("query", "").strip()
    if not query:
        return jsonify({"error": "指令不能为空"}), 400
    if not _guest_consume():
        return jsonify({"error": f"游客最多问 {GUEST_QUOTA} 个问题，请登录后继续", "code": "QUOTA"}), 403
    try:
        state = _brain.get_current_state()
        memory, last_action = _brain.load_memory()
        inputs = {
            "goal": _brain.GOAL,
            "memory": memory,
            "last_action": last_action,
            "voice_query": query,
            "vision_summary": "",
        }
        outputs = _brain.run_dify(inputs)
        if outputs is None:
            return jsonify({"error": "Dify 大脑调用失败（容器/密钥未就绪，或工作流非 succeeded）"}), 502
        advice = _brain.extract_advice(outputs)
        plan = _brain.extract_plan(outputs)
        action = _brain.extract_action(advice, plan, state) if advice else None
        pushed_action = bool(action and _brain.push_action(action["verb"], action["prefab"]))
        pushed_advice = bool(advice and _brain.push_advice(advice))
        _brain.save_memory(plan if plan else memory, advice if advice else last_action)
        return jsonify({
            "advice": advice,
            "plan": plan,
            "action": action,
            "pushed_action": pushed_action,
            "pushed_advice": pushed_advice,
            "state": state,
            "goal": _brain.GOAL,
        })
    except Exception as e:
        return jsonify({"error": f"大脑执行异常：{e}"}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5100, debug=False)
