#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vision.py — 图像/视频识别，把玩家看到的画面转成文字喂给 Dify 工作流。

技术选型（面试可讲）：
  - 图像：本地多模态/描述模型（transformers 的 image-to-text pipeline），
    不依赖云 API、离线可用。默认用轻量描述模型，可用环境变量 VISION_MODEL
    换成更强的 VLM（如 Qwen/Qwen2-VL-2B-Instruct）做画面问答。
  - 视频：OpenCV 抽帧（默认每 2 秒抽 1 帧、最多 8 帧），逐帧描述后拼成
    「第1帧: …；第2帧: …」的文字摘要，把视频降维成一段可消费的文本。

    这是「非结构化视觉信号 → 结构化文本」的感知层，跟 state_api 把游戏状态
    压成摘要是同一套思路：感知层产出文本，Dify 只做决策。

用法：
    python vision.py 截图.png
    python vision.py 录像.mp4
    from vision import describe_media
    text = describe_media("a.png")   # 被 dify_brain 调用
"""
import os
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# 默认描述模型（约 500MB，CPU 可跑）。换更强的 VLM 时改这个环境变量。
DEFAULT_MODEL = os.getenv("VISION_MODEL", "nlpconnect/vit-gpt2-image-captioning")
MAX_FRAMES = int(os.getenv("VISION_MAX_FRAMES", "8"))
FRAME_INTERVAL_SEC = float(os.getenv("VISION_FRAME_INTERVAL", "2"))

_pipe = None

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
VIDEO_EXTS = {".mp4", ".avi", ".mkv", ".mov", ".webm", ".flv", ".wmv"}


def _get_pipeline():
    """惰性加载描述模型（首次会联网下载权重）。"""
    global _pipe
    if _pipe is None:
        from transformers import pipeline
        print(f"[vision] 加载描述模型 '{DEFAULT_MODEL}'（首次需联网下载）…", flush=True)
        _pipe = pipeline("image-to-text", model=DEFAULT_MODEL)
    return _pipe


def _caption(pil_image) -> str:
    try:
        out = _get_pipeline()(pil_image)
        if isinstance(out, list) and out:
            d = out[0]
            if isinstance(d, dict):
                return d.get("generated_text") or d.get("text") or str(d)
            return str(d)
        return str(out)
    except Exception as e:
        return f"[识别失败: {e}]"


def describe_image(path: str) -> str:
    from PIL import Image
    img = Image.open(path).convert("RGB")
    return _caption(img)


def describe_video(path: str, interval_sec: float = None, max_frames: int = None) -> str:
    import cv2
    from PIL import Image

    interval_sec = interval_sec if interval_sec is not None else FRAME_INTERVAL_SEC
    max_frames = max_frames if max_frames is not None else MAX_FRAMES

    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise ValueError(f"无法打开视频: {path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    step = max(1, int(fps * interval_sec))

    frames = []
    idx = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if idx % step == 0:
            frames.append(frame)
            if len(frames) >= max_frames:
                break
        idx += 1
    cap.release()

    if not frames:
        # 兜底：至少取第一帧
        cap = cv2.VideoCapture(path)
        ret, frame = cap.read()
        cap.release()
        if not ret:
            return ""
        frames = [frame]

    captions = []
    for i, bgr in enumerate(frames, 1):
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        c = _caption(Image.fromarray(rgb))
        captions.append(f"第{i}帧: {c}")
    return "；".join(captions)


def extract_frames(path: str, interval_sec: float = None, max_frames: int = None, out_dir: str = None) -> list[str]:
    """从视频抽帧并落盘成 JPEG 图片，返回图片路径列表（供原生视觉上传到 Dify）。

    复用 describe_video 的抽帧节奏（默认每 2s 一帧、最多 8 帧），但不做 caption，
    而是直接把帧图写到磁盘，交给视觉模型看图。
    """
    import os
    import tempfile

    import cv2

    interval_sec = interval_sec if interval_sec is not None else FRAME_INTERVAL_SEC
    max_frames = max_frames if max_frames is not None else MAX_FRAMES
    out_dir = out_dir or tempfile.mkdtemp(prefix="dst_frames_")

    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise ValueError(f"无法打开视频: {path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    step = max(1, int(fps * interval_sec))

    paths = []
    idx = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if idx % step == 0:
            out = os.path.join(out_dir, f"frame_{len(paths):03d}.jpg")
            cv2.imwrite(out, frame)
            paths.append(out)
            if len(paths) >= max_frames:
                break
        idx += 1
    cap.release()

    if not paths:
        # 兜底：至少取第一帧
        cap = cv2.VideoCapture(path)
        ret, frame = cap.read()
        cap.release()
        if ret:
            out = os.path.join(out_dir, "frame_000.jpg")
            cv2.imwrite(out, frame)
            paths.append(out)
    return paths


def describe_media(path: str) -> str:
    """根据扩展名自动识别图片/视频，返回文字描述（失败返回空串）。"""
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext in VIDEO_EXTS:
            return describe_video(path)
        if ext in IMAGE_EXTS:
            return describe_image(path)
        # 未知扩展名：先按图片试，再按视频试
        try:
            return describe_image(path)
        except Exception:
            return describe_video(path)
    except Exception as e:
        print(f"[vision] 识别失败: {e}", file=sys.stderr, flush=True)
        return ""


def main():
    import argparse
    ap = argparse.ArgumentParser(description="图像/视频识别（本地模型）")
    ap.add_argument("media", help="图片或视频文件路径")
    args = ap.parse_args()
    text = describe_media(args.media)
    if text:
        print(text)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
