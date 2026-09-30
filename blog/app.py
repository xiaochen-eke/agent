# -*- coding: utf-8 -*-
"""个人博客 —— Flask 动态博客（Markdown 写作 + 后台管理 + 评论 + 搜索）。"""
import os
import re
import time
import threading
from functools import wraps

import markdown
from flask import (Flask, request, session, redirect, url_for,
                   render_template, abort, flash)

from db import init_db, get_db

BASE = os.path.dirname(os.path.abspath(__file__))


# ---------- 极简 .env 加载（不依赖 python-dotenv） ----------
def _load_env(path):
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


_load_env(os.path.join(BASE, ".env"))

app = Flask(__name__)
app.secret_key = os.environ.get("BLOG_SECRET_KEY", "dev-secret-change-me")

ADMIN_USER = os.environ.get("BLOG_ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("BLOG_ADMIN_PASSWORD", "admin123")
SITE_TITLE = os.environ.get("BLOG_TITLE", "MY BLOG")
SITE_SUBTITLE = os.environ.get("BLOG_SUBTITLE", "// 记录 · 思考 · 代码")
PAGE_SIZE = 10

MD_EXTENSIONS = ["fenced_code", "tables", "sane_lists"]


# ---------- 工具 ----------
def now():
    return int(time.time())


def render_md(text):
    return markdown.markdown(text or "", extensions=MD_EXTENSIONS)


def make_summary(md_text, n=120):
    plain = re.sub(r"[#>*`\-\[\]()!]", " ", md_text or "")
    plain = re.sub(r"\s+", " ", plain).strip()
    return plain[:n] + ("…" if len(plain) > n else "")


def parse_tags(tags):
    return [t.strip() for t in (tags or "").split(",") if t.strip()]


@app.template_filter("dt")
def _dt(ts):
    if not ts:
        return ""
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))


@app.context_processor
def _inject_globals():
    return dict(site_title=SITE_TITLE, site_subtitle=SITE_SUBTITLE)


# ---------- 评论防刷（单进程内存即可） ----------
_comment_lock = threading.Lock()
_comment_log = {}  # ip -> [timestamps]


def _comment_rate_ok(ip):
    with _comment_lock:
        now_ts = now()
        recent = [t for t in _comment_log.get(ip, []) if now_ts - t < 600]
        _comment_log[ip] = recent
        if len(recent) >= 5:
            return False
        recent.append(now_ts)
        _comment_log[ip] = recent
        return True


# ---------- 查询辅助 ----------
def published_posts(conn, offset=0, limit=PAGE_SIZE):
    return conn.execute(
        "SELECT * FROM posts WHERE status='published' "
        "ORDER BY published_at DESC, id DESC LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()


def count_published(conn):
    return conn.execute(
        "SELECT COUNT(*) c FROM posts WHERE status='published'"
    ).fetchone()["c"]


def post_by_id(conn, pid):
    return conn.execute("SELECT * FROM posts WHERE id=?", (pid,)).fetchone()


# ---------- 鉴权 ----------
def admin_required(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        if not session.get("admin"):
            return redirect(url_for("admin_login"))
        return fn(*a, **kw)
    return wrapper


# ---------- 公开页面 ----------
@app.get("/")
def index():
    page = max(1, request.args.get("page", 1, type=int))
    conn = get_db()
    posts = published_posts(conn, (page - 1) * PAGE_SIZE, PAGE_SIZE)
    total = count_published(conn)
    conn.close()
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    return render_template("index.html", posts=posts, heading=None,
                           page=page, pages=pages, total=total)


@app.get("/post/<int:pid>")
def post_view(pid):
    conn = get_db()
    post = post_by_id(conn, pid)
    if not post or post["status"] != "published":
        conn.close()
        abort(404)
    comments = conn.execute(
        "SELECT * FROM comments WHERE post_id=? AND status='approved' ORDER BY created_at ASC",
        (pid,),
    ).fetchall()
    prev_post = conn.execute(
        "SELECT id, title FROM posts WHERE status='published' AND id < ? "
        "ORDER BY id DESC LIMIT 1",
        (pid,),
    ).fetchone()
    next_post = conn.execute(
        "SELECT id, title FROM posts WHERE status='published' AND id > ? "
        "ORDER BY id ASC LIMIT 1",
        (pid,),
    ).fetchone()
    conn.close()
    return render_template("post.html", post=post, comments=comments,
                           tags=parse_tags(post["tags"]),
                           prev_post=prev_post, next_post=next_post)


@app.post("/post/<int:pid>/comment")
def post_comment(pid):
    conn = get_db()
    post = post_by_id(conn, pid)
    if not post or post["status"] != "published":
        conn.close()
        abort(404)
    # 蜜罐：隐藏的 website 字段被填说明是机器人
    if request.form.get("website"):
        conn.close()
        return redirect(url_for("post_view", pid=pid))
    author = (request.form.get("author") or "").strip()[:40] or "匿名"
    content = (request.form.get("content") or "").strip()
    if not content:
        flash("评论内容不能为空")
        conn.close()
        return redirect(url_for("post_view", pid=pid))
    content = content[:2000]
    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "")
    if not _comment_rate_ok(ip):
        flash("评论太频繁，请稍后再试")
        conn.close()
        return redirect(url_for("post_view", pid=pid))
    conn.execute(
        "INSERT INTO comments(post_id, author, content, status, ip, created_at) "
        "VALUES (?,?,?,'pending',?,?)",
        (pid, author, content, ip, now()),
    )
    conn.commit()
    conn.close()
    flash("评论已提交，待博主审核后显示")
    return redirect(url_for("post_view", pid=pid))


@app.get("/tag/<tag>")
def tag_view(tag):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM posts WHERE status='published' ORDER BY published_at DESC"
    ).fetchall()
    conn.close()
    posts = [r for r in rows if tag in parse_tags(r["tags"])]
    return render_template("index.html", posts=posts,
                           heading=f"标签：{tag}", page=1, pages=1, total=len(posts))


@app.get("/category/<cat>")
def category_view(cat):
    conn = get_db()
    posts = conn.execute(
        "SELECT * FROM posts WHERE status='published' AND category=? "
        "ORDER BY published_at DESC",
        (cat,),
    ).fetchall()
    conn.close()
    return render_template("index.html", posts=posts,
                           heading=f"分类：{cat}", page=1, pages=1, total=len(posts))


@app.get("/search")
def search():
    q = (request.args.get("q") or "").strip()
    posts = []
    if q:
        like = f"%{q}%"
        conn = get_db()
        posts = conn.execute(
            "SELECT * FROM posts WHERE status='published' AND "
            "(title LIKE ? OR content_md LIKE ? OR summary LIKE ?) "
            "ORDER BY published_at DESC",
            (like, like, like),
        ).fetchall()
        conn.close()
    return render_template("index.html", posts=posts,
                           heading=f"搜索：{q}", page=1, pages=1, total=len(posts))


@app.get("/tags")
def tags_view():
    conn = get_db()
    rows = conn.execute("SELECT tags FROM posts WHERE status='published'").fetchall()
    conn.close()
    counts = {}
    for r in rows:
        for t in parse_tags(r["tags"]):
            counts[t] = counts.get(t, 0) + 1
    tags = sorted(counts.items(), key=lambda kv: -kv[1])
    return render_template("tags.html", tags=tags)


@app.get("/archive")
def archive():
    conn = get_db()
    posts = conn.execute(
        "SELECT * FROM posts WHERE status='published' ORDER BY published_at DESC, id DESC"
    ).fetchall()
    conn.close()
    groups = {}
    for p in posts:
        key = time.strftime("%Y-%m", time.localtime(p["published_at"] or p["created_at"]))
        groups.setdefault(key, []).append(p)
    return render_template("archive.html", groups=groups)


@app.get("/about")
def about():
    about_md = ""
    path = os.path.join(BASE, "about.md")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            about_md = f.read()
    return render_template("about.html", about_html=render_md(about_md))


@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


# ---------- 管理后台 ----------
@app.get("/admin")
def admin_login():
    if session.get("admin"):
        return redirect(url_for("admin_dashboard"))
    return render_template("admin/login.html")


@app.post("/admin/login")
def admin_login_post():
    u = request.form.get("username", "")
    p = request.form.get("password", "")
    if u == ADMIN_USER and p == ADMIN_PASS:
        session["admin"] = True
        return redirect(url_for("admin_dashboard"))
    flash("账号或密码错误")
    return redirect(url_for("admin_login"))


@app.get("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    return redirect(url_for("admin_login"))


@app.get("/admin/dashboard")
@admin_required
def admin_dashboard():
    conn = get_db()
    posts = conn.execute("SELECT * FROM posts ORDER BY updated_at DESC").fetchall()
    pending = conn.execute(
        "SELECT COUNT(*) c FROM comments WHERE status='pending'"
    ).fetchone()["c"]
    conn.close()
    return render_template("admin/dashboard.html", posts=posts, pending=pending)


@app.route("/admin/post/new", methods=["GET", "POST"])
@admin_required
def admin_post_new():
    if request.method == "POST":
        return _save_post(None)
    return render_template("admin/editor.html", post=None)


@app.route("/admin/post/<int:pid>/edit", methods=["GET", "POST"])
@admin_required
def admin_post_edit(pid):
    conn = get_db()
    post = post_by_id(conn, pid)
    conn.close()
    if not post:
        abort(404)
    if request.method == "POST":
        return _save_post(pid)
    return render_template("admin/editor.html", post=post)


def _save_post(pid):
    title = (request.form.get("title") or "").strip()
    content_md = request.form.get("content_md") or ""
    category = (request.form.get("category") or "").strip() or "未分类"
    tags = (request.form.get("tags") or "").strip()
    status = request.form.get("status") or "draft"
    if not title:
        flash("标题不能为空")
        if pid is None:
            return redirect(url_for("admin_post_new"))
        return redirect(url_for("admin_post_edit", pid=pid))

    content_html = render_md(content_md)
    summary = make_summary(content_md)
    published_at = now() if status == "published" else None

    conn = get_db()
    if pid is None:
        ts = now()
        cur = conn.execute(
            "INSERT INTO posts(title, content_md, content_html, summary, category, tags, "
            "status, created_at, updated_at, published_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (title, content_md, content_html, summary, category, tags, status,
             ts, ts, published_at),
        )
        conn.commit()
        new_id = cur.lastrowid
        conn.close()
        flash("已创建")
        return redirect(url_for("admin_post_edit", pid=new_id))
    else:
        conn.execute(
            "UPDATE posts SET title=?, content_md=?, content_html=?, summary=?, "
            "category=?, tags=?, status=?, updated_at=?, published_at=? WHERE id=?",
            (title, content_md, content_html, summary, category, tags, status,
             now(), published_at, pid),
        )
        conn.commit()
        conn.close()
        flash("已保存")
        return redirect(url_for("admin_post_edit", pid=pid))


@app.post("/admin/post/<int:pid>/delete")
@admin_required
def admin_post_delete(pid):
    conn = get_db()
    conn.execute("DELETE FROM posts WHERE id=?", (pid,))
    conn.commit()
    conn.close()
    flash("已删除")
    return redirect(url_for("admin_dashboard"))


@app.post("/admin/post/<int:pid>/toggle")
@admin_required
def admin_post_toggle(pid):
    conn = get_db()
    post = post_by_id(conn, pid)
    if post:
        new_status = "draft" if post["status"] == "published" else "published"
        conn.execute(
            "UPDATE posts SET status=?, published_at=?, updated_at=? WHERE id=?",
            (new_status, now() if new_status == "published" else None, now(), pid),
        )
        conn.commit()
    conn.close()
    return redirect(url_for("admin_dashboard"))


@app.get("/admin/comments")
@admin_required
def admin_comments():
    conn = get_db()
    comments = conn.execute(
        "SELECT c.*, p.title AS post_title FROM comments c "
        "LEFT JOIN posts p ON p.id = c.post_id ORDER BY c.created_at DESC"
    ).fetchall()
    conn.close()
    return render_template("admin/comments.html", comments=comments)


@app.post("/admin/comment/<int:cid>/<action>")
@admin_required
def admin_comment_action(cid, action):
    conn = get_db()
    if action == "approve":
        conn.execute("UPDATE comments SET status='approved' WHERE id=?", (cid,))
    elif action == "spam":
        conn.execute("UPDATE comments SET status='spam' WHERE id=?", (cid,))
    else:
        conn.execute("DELETE FROM comments WHERE id=?", (cid,))
    conn.commit()
    conn.close()
    return redirect(url_for("admin_comments"))


if __name__ == "__main__":
    init_db()
    app.run(host="127.0.0.1",
            port=int(os.environ.get("BLOG_PORT", "5200")),
            debug=False)
