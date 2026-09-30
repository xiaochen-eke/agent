#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""items_server.py — Flask :5099，GET /lookup?item=&intent=，供 Dify HTTP 节点调用。

启动：cd agent_versions/shared && python items_server.py
依赖：pip install flask
"""
from flask import Flask, jsonify, request

from items_db import lookup

app = Flask(__name__)


@app.route("/lookup", methods=["GET"])
def handle_lookup():
    item = request.args.get("item", "")
    intent = request.args.get("intent", "stats")
    result = lookup(item, intent)
    return jsonify({"result": result, "item": item, "intent": intent})


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"ok": True})


if __name__ == "__main__":
    # host=0.0.0.0 让 Docker 容器经 host.docker.internal 能访问到宿主机
    app.run(host="0.0.0.0", port=5099, debug=False)
