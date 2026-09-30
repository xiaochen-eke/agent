# -*- coding: utf-8 -*-
"""个人博客 SQLite 数据层（stdlib sqlite3，无第三方依赖）。"""
import os
import sqlite3

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE, "data", "blog.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    title        TEXT NOT NULL,
    content_md   TEXT NOT NULL DEFAULT '',
    content_html TEXT NOT NULL DEFAULT '',
    summary      TEXT NOT NULL DEFAULT '',
    category     TEXT NOT NULL DEFAULT '未分类',
    tags         TEXT NOT NULL DEFAULT '',
    status       TEXT NOT NULL DEFAULT 'draft',
    created_at   INTEGER NOT NULL,
    updated_at   INTEGER NOT NULL,
    published_at INTEGER
);
CREATE TABLE IF NOT EXISTS comments (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id    INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    author     TEXT NOT NULL,
    content    TEXT NOT NULL,
    status     TEXT NOT NULL DEFAULT 'pending',
    ip         TEXT NOT NULL DEFAULT '',
    created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_posts_status ON posts(status, published_at);
CREATE INDEX IF NOT EXISTS idx_comments_post ON comments(post_id, status);
"""


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db()
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
