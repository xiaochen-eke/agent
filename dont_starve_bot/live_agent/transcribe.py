#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
transcribe.py — 语音识别（ASR），把玩家语音转成文字喂给 Dify 工作流。

技术选型（面试可讲）：
  用 OpenAI Whisper（本地开源，openai-whisper 包），不依赖任何云 API，离线可用、
  隐私友好。中文/英文都能识别。模型越大越准、越慢，默认 base（约 140MB，CPU 可跑）。

  .wav 直接走标准库 wave + numpy 解码（无需 ffmpeg）；mp3/m4a 等压缩格式才需要
  ffmpeg（whisper.load_audio 内部调用），缺失时会给出明确提示。

用法：
    python transcribe.py 录音.wav              # 命令行转文字
    from transcribe import transcribe          # 被 dify_brain 调用
    text = transcribe("a.wav", model_name="small", language="zh")
"""
import os
import sys
import wave

import numpy as np

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# 加载 .env 文件（不依赖 python-dotenv），供 ZHIPU_API_KEY 使用
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

# 默认模型：tiny(快) / base(均衡) / small(较准) / medium / large
DEFAULT_MODEL = "base"
WHISPER_SR = 16000

_model = None
_model_name = None


def _load_wav(path: str):
    """用标准库解码 16bit PCM wav，返回 (float32 mono 数组, 采样率)。无需 ffmpeg。"""
    with wave.open(path, "rb") as w:
        n_ch = w.getnchannels()
        sampwidth = w.getsampwidth()
        sr = w.getframerate()
        frames = w.readframes(w.getnframes())
    if sampwidth != 2:
        raise ValueError(f"仅支持 16bit PCM wav（当前 {sampwidth * 8}bit）")
    audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
    if n_ch == 2:
        audio = audio.reshape(-1, 2).mean(axis=1)  # 立体声 -> 单声道
    return audio, sr


def _resample(audio: np.ndarray, orig_sr: int, target_sr: int = WHISPER_SR) -> np.ndarray:
    """线性插值重采样到 whisper 需要的 16kHz。"""
    if orig_sr == target_sr:
        return audio
    n = int(len(audio) * target_sr / orig_sr)
    idx = np.linspace(0, len(audio) - 1, n)
    return np.interp(idx, np.arange(len(audio)), audio).astype(np.float32)


def _load_audio(path: str):
    """加载任意音频到 (float32 mono 16kHz)。wav 无需 ffmpeg，其余交给 whisper。"""
    low = path.lower()
    if low.endswith((".wav", ".wave")):
        audio, sr = _load_wav(path)
        return _resample(audio, sr)
    # 压缩格式（mp3/m4a/flac…）需要 ffmpeg
    import whisper
    return whisper.load_audio(path, sr=WHISPER_SR)


def _get_model(model_name: str):
    """惰性加载 + 缓存 whisper 模型（首次会联网下载权重到 ~/.cache/whisper）。"""
    global _model, _model_name
    if _model is None or _model_name != model_name:
        import whisper
        print(f"[transcribe] 加载 whisper 模型 '{model_name}'（首次需联网下载）…", flush=True)
        _model = whisper.load_model(model_name)
        _model_name = model_name
    return _model


def transcribe(path: str, model_name: str = DEFAULT_MODEL, language: str = None) -> str:
    """把音频文件转成文字。返回去除首尾空白后的文本（失败返回空串）。"""
    try:
        audio = _load_audio(path)
        model = _get_model(model_name)
        kwargs = {}
        if language:
            kwargs["language"] = language
        result = model.transcribe(audio, **kwargs)
        return (result.get("text") or "").strip()
    except Exception as e:
        # 常见：ffmpeg 缺失 / 文件不存在 / 模型下载失败
        msg = f"语音识别失败: {e}"
        if "ffmpeg" in str(e).lower():
            msg += "（压缩格式需要 ffmpeg，.wav 则无需）"
        print(f"[transcribe] {msg}", file=sys.stderr, flush=True)
        return ""


def transcribe_glm(path: str) -> str:
    """用智谱 GLM-4-Voice 做语音理解（原生音频输入，而非纯 ASR）。

    需环境变量 ``ZHIPU_API_KEY``（可写在 live_agent/.env）。返回模型对音频的理解
    文本（失败返回空串）。智谱 API 为 OpenAI 兼容的 ``/chat/completions``，音频以
    base64 放进 content。GLM 的音频消息是平级字段：``{"type":"input_audio",
    "input_audio":<base64字符串>, "format":"wav"}``（input_audio 直接是字符串，
    不是 {data,format} 嵌套对象）。注意：glm-4-voice 是语音→语音模型，主要支持
    wav，默认返回音频；这里靠 prompt 引导它输出文字，若返回的是 message.audio
    而非 content，需要进一步处理。
    """
    import base64
    import os

    import requests

    key = os.getenv("ZHIPU_API_KEY")
    if not key:
        print("[transcribe] 未设置 ZHIPU_API_KEY，跳过 GLM-4-Voice", file=sys.stderr, flush=True)
        return ""

    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    fmt = os.path.splitext(path)[1].lstrip(".").lower() or "wav"

    try:
        r = requests.post(
            "https://open.bigmodel.cn/api/paas/v4/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": "glm-4-voice",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_audio", "input_audio": b64, "format": fmt},
                            {"type": "text", "text": "请转写并理解这段语音，直接输出内容。"},
                        ],
                    }
                ],
            },
            timeout=120,
        )
        r.raise_for_status()
        data = r.json()
        return (data["choices"][0]["message"]["content"] or "").strip()
    except Exception as e:
        print(f"[transcribe] GLM-4-Voice 识别失败: {e}", file=sys.stderr, flush=True)
        return ""


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Whisper 语音识别")
    ap.add_argument("audio", help="音频文件路径")
    ap.add_argument("--model", default=DEFAULT_MODEL, help="whisper 模型：tiny/base/small/medium/large")
    ap.add_argument("--language", default=None, help="语言代码，如 zh / en（留空自动检测）")
    args = ap.parse_args()
    text = transcribe(args.audio, model_name=args.model, language=args.language)
    if text:
        print(text)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
