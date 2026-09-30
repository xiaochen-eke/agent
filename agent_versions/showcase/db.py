# -*- coding: utf-8 -*-
"""db.py — MySQL 存储（只存「登录/账号」数据）。

约定：旧的 SQLite / ChromaDB / history.json 一律不动，本模块只负责 users 表。
若 .env 没配 MYSQL_URL、或 MySQL 连不上，get_or_create_user 返回 None，
调用方（app.py）会回退到本地 users.json —— 没起数据库时演示照常跑。
"""
import os
import time

from sqlalchemy import BigInteger, Column, DateTime, String, create_engine, func
from sqlalchemy.orm import declarative_base, sessionmaker

MYSQL_URL = os.getenv("MYSQL_URL", "")

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    openid = Column(String(64), nullable=False, unique=True, index=True)
    nickname = Column(String(64), default="")
    avatar = Column(String(512), default="")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


_engine = None
_Session = None
_fail_until = 0.0


def _connect():
    global _engine, _Session, _fail_until
    if _engine is not None:
        return True
    if time.time() < _fail_until:
        return False
    try:
        _engine = create_engine(MYSQL_URL, pool_pre_ping=True, pool_recycle=3600)
        Base.metadata.create_all(_engine)  # 首次自动建表
        _Session = sessionmaker(bind=_engine)
        return True
    except Exception:
        _engine = None
        _fail_until = time.time() + 60  # 连不上就冷却 60s，别每个请求都去撞一次
        return False


def get_or_create_user(openid, nickname, avatar):
    """登录成功后落库；返回 {openid, nickname, avatar}，MySQL 不可用时返回 None。"""
    if not MYSQL_URL or not _connect():
        return None
    try:
        s = _Session()
        try:
            u = s.query(User).filter(User.openid == openid).first()
            if u is None:
                u = User(openid=openid, nickname=nickname or "", avatar=avatar or "")
                s.add(u)
            else:
                if nickname:
                    u.nickname = nickname
                if avatar:
                    u.avatar = avatar
            s.commit()
            return {"openid": u.openid, "nickname": u.nickname or "", "avatar": u.avatar or ""}
        finally:
            s.close()
    except Exception:
        return None
