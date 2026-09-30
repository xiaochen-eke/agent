#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
realtime_voice.py — 实时语音闭环（麦克风 → 转文字 → Dify 大脑 → 建议 → 双通道反馈）

这是一个「常驻监听」进程，让玩家边玩边说，说完自动出建议：
    [麦克风] ──VAD/热键──> [说话片段 .wav] ──Whisper/GLM──> [文字]
        → dify_brain.run_dify() → 建议
        → ① 回灌游戏内（dify_brain.push_advice → state_api /advice → bridge → dify_advice.json）
        → ② 语音播报（edge-tts 生成中文语音 → 播放）

两种触发方式（可同时开）：
  1. VAD 能量检测：自动检测「开始说话 / 说完静音」，说完自动识别。解放双手。
     （建议戴耳机，避免游戏外放声音回灌到麦克风造成误触发）
  2. Push-to-talk：按住热键录音、松开识别。最稳，不受游戏音干扰。

技术要点（面试可讲）：
  - 实时音频用 sounddevice 以 16kHz/16bit/30ms 帧流式采集，VAD 用 numpy 算 RMS
    能量阈值（零第三方 VAD 依赖），启动时自动校准噪声底、阈值 = 噪声 × 倍数。
  - 音频线程只做「采集 + 状态机」，识别/大脑在主管道串行处理，互不阻塞；
    用 queue 解耦，避免麦克风丢帧。
  - 语音播报用 edge-tts（微软神经网络中文语音，免费无需 key）+ miniaudio 解码，
    播放时自动抑制 VAD，避免「听到自己的回答又当成提问」。

用法：
    python realtime_voice.py                 # VAD + 热键 + TTS 全开
    python realtime_voice.py --no-vad        # 只要热键
    python realtime_voice.py --no-tts        # 不要语音播报（只回灌游戏文字）
    python realtime_voice.py --hotkey f8     # 自定义热键（默认 f9）
    python realtime_voice.py --asr glm       # 语音转文字用 GLM（默认 whisper 本地）
"""

import argparse
import asyncio
import os
import queue
import sys
import tempfile
import threading
import time
import wave

import numpy as np
import sounddevice as sd

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# 加载 .env（ZHIPU_API_KEY 等）
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

import dify_brain
import transcribe

# ============ 配置（均可被环境变量覆盖） ============
SAMPLE_RATE = 16000                 # 采集采样率（Whisper/VAD 都用 16k）
FRAME_MS = 30                       # 每帧时长
FRAME_SAMPLES = int(SAMPLE_RATE * FRAME_MS / 1000)   # 480 采样/帧
BYTES_PER_MS = SAMPLE_RATE * 2 // 1000               # 16bit 单声道，每毫秒字节数

HOTKEY = os.getenv("DST_VOICE_HOTKEY", "f9")                  # 按住说话热键
TTS_VOICE = os.getenv("DST_TTS_VOICE", "zh-CN-XiaoxiaoNeural")  # edge-tts 音色
VAD_SILENCE_MS = int(os.getenv("DST_VAD_SILENCE_MS", "700"))  # 静音多久判定「说完」
MIN_UTTERANCE_MS = int(os.getenv("DST_VAD_MIN_MS", "350"))    # 短于此的片段丢弃
MAX_UTTERANCE_MS = int(os.getenv("DST_VAD_MAX_MS", "15000"))  # 单段最长（超长截断）
ENERGY_RATIO = float(os.getenv("DST_VAD_ENERGY_RATIO", "4.0"))  # 阈值 = 噪声RMS × 倍数

# ============ 状态（音频线程 + 热键线程 + 主线程共享） ============
_vad_state = "IDLE"                 # IDLE / SPEAKING（含静音拖尾）
_vad_buf = bytearray()
_vad_silent_frames = 0
_ptt_recording = False
_ptt_buf = bytearray()
_ptt_lock = threading.Lock()
_suppress_vad = False               # 播放 TTS 时抑制 VAD（防回声）
_noise_rms = 300.0
_speech_thresh = 1200.0
_calib_frames = 0
_done_queue = queue.Queue()         # 已完成片段 → 主线程识别


def _rms(b: bytes) -> float:
    """一帧 int16 字节的均方根能量。"""
    if not b:
        return 0.0
    a = np.frombuffer(b, dtype=np.int16)
    return float(np.sqrt(np.mean(a.astype(np.float32) ** 2)))


def _finalize(buf: bytearray, tag: str):
    """把已收满的语音片段落盘成 wav 并入队（太短则丢弃）。"""
    if len(buf) < MIN_UTTERANCE_MS * BYTES_PER_MS:
        buf.clear()
        return
    path = os.path.join(tempfile.gettempdir(), f"dst_{tag}_{int(time.time() * 1000)}.wav")
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(bytes(buf))
    buf.clear()
    _done_queue.put(path)


def _audio_callback(indata, frames, tinfo, status):
    """音频回调（sounddevice 后台线程）：VAD 状态机 + PTT 录制。"""
    global _vad_state, _vad_silent_frames, _noise_rms, _speech_thresh, _calib_frames

    b = indata[:, 0].tobytes()
    r = _rms(b)

    # —— 启动校准：前 ~0.9s 测噪声底，算语音阈值 ——
    if _calib_frames < 30:
        _calib_frames += 1
        _noise_rms = 0.9 * _noise_rms + 0.1 * r
        if _calib_frames == 30:
            _speech_thresh = max(_noise_rms * ENERGY_RATIO, 500.0)
            print(f"[voice] 校准完成：噪声RMS≈{_noise_rms:.0f}，语音阈值={_speech_thresh:.0f}", flush=True)
        return

    # —— Push-to-talk 录制（热键按住期间累计） ——
    with _ptt_lock:
        if _ptt_recording:
            _ptt_buf.extend(b)

    # —— VAD 状态机（TTS 播放期间抑制，防回声） ——
    if _suppress_vad:
        return
    if r > _speech_thresh:
        _vad_silent_frames = 0
        if _vad_state == "IDLE":
            _vad_state = "SPEAKING"
            _vad_buf.clear()
            print("[voice] 🎤 检测到说话…", flush=True)
        _vad_buf.extend(b)
        if len(_vad_buf) >= MAX_UTTERANCE_MS * BYTES_PER_MS:
            _finalize(_vad_buf, "vad")
            _vad_state = "IDLE"
    elif _vad_state == "SPEAKING":
        _vad_buf.extend(b)          # 拖尾静音也收进来，避免截断尾音
        _vad_silent_frames += 1
        if _vad_silent_frames >= VAD_SILENCE_MS // FRAME_MS:
            _finalize(_vad_buf, "vad")
            _vad_state = "IDLE"
            print("[voice] 说完，识别中…", flush=True)


# ============ Push-to-talk（全局热键） ============
def _ptt_press(key):
    global _ptt_recording
    with _ptt_lock:
        _ptt_buf.clear()
        _ptt_recording = True
    print("[voice] 🎙️ 按住说话…", flush=True)


def _ptt_release(key):
    global _ptt_recording
    with _ptt_lock:
        _ptt_recording = False
        buf = bytes(_ptt_buf)
        _ptt_buf.clear()
    if len(buf) < MIN_UTTERANCE_MS * BYTES_PER_MS:
        print("[voice] 太短，忽略", flush=True)
        return
    print("[voice] 松开，识别中…", flush=True)
    path = os.path.join(tempfile.gettempdir(), f"dst_ptt_{int(time.time() * 1000)}.wav")
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(buf)
    _done_queue.put(path)


# ============ TTS 播报 ============
async def _tts_to_mp3(text: str, path: str):
    import edge_tts
    await edge_tts.Communicate(text, TTS_VOICE).save(path)


def _speak(text: str):
    """把建议用 edge-tts 生成中文语音并播放（失败静默返回，不影响主流程）。"""
    global _suppress_vad
    path = os.path.join(tempfile.gettempdir(), f"dst_tts_{int(time.time() * 1000)}.mp3")
    try:
        asyncio.run(_tts_to_mp3(text, path))
        import miniaudio
        dec = miniaudio.decode_file(path)
        a = np.array(dec.samples)
        if a.dtype == np.int16:
            a = a.astype(np.float32) / 32768.0
        elif a.dtype == np.int32:
            a = a.astype(np.float32) / 2147483648.0
        elif a.dtype != np.float32:
            a = a.astype(np.float32)
        if a.ndim == 1:
            a = a.reshape(-1, 1)
        _suppress_vad = True
        sd.play(a, dec.sample_rate)
        sd.wait()
    except Exception as e:
        print(f"[voice] 语音播报失败: {e}", flush=True)
    finally:
        _suppress_vad = False
        try:
            os.remove(path)
        except Exception:
            pass


# ============ 单段处理 ============
def _handle_utterance(wav: str, args):
    try:
        if args.asr == "glm":
            text = dify_brain.run_transcribe(wav)      # GLM-4-Voice → Whisper 兜底
        else:
            text = transcribe.transcribe(wav)          # 本地 Whisper（低延迟）
    finally:
        try:
            os.remove(wav)
        except Exception:
            pass

    if not text:
        print("[voice] 没听清，再说一次？", flush=True)
        return

    print(f"[voice] 你说了：{text}", flush=True)

    memory, last_action = dify_brain.load_memory()
    inputs = {
        "goal": dify_brain.GOAL,
        "memory": memory,
        "last_action": last_action,
        "voice_query": text,
        "vision_summary": "",
    }
    outputs = dify_brain.run_dify(inputs)
    if outputs is None:
        print("[voice] Dify 未返回，稍后再试", flush=True)
        return

    advice = dify_brain.extract_advice(outputs)
    plan = dify_brain.extract_plan(outputs)
    if plan:
        dify_brain.save_memory(plan, advice if advice else last_action)

    if not advice:
        print("[voice] 大脑只产出了计划、没给出可播报建议", flush=True)
        return

    # —— 双通道反馈：游戏内文字 + 语音 ——
    ok = dify_brain.push_advice(advice)
    print(f"[voice] {'✅ 已回灌游戏' if ok else '❌ 回灌失败'}: {advice}", flush=True)
    if not args.no_tts:
        _speak(advice)

    # —— Phase 3：LLM 决策动作（玩家主动提问时，把建议转成可执行动作） ——
    action = dify_brain.extract_action(advice, plan)
    if action:
        ok2 = dify_brain.push_action(action["verb"], action["prefab"])
        print(f"[voice] {'✅ 已推动作' if ok2 else '❌ 推动作失败'}: {action['verb']} {action['prefab']}", flush=True)


def _beep(ms=120, freq=880):
    """启动提示音：让玩家知道麦克风已就绪。"""
    t = np.linspace(0, ms / 1000, int(SAMPLE_RATE * ms / 1000), False)
    tone = (np.sin(2 * np.pi * freq * t) * 0.25).astype(np.float32).reshape(-1, 1)
    try:
        sd.play(tone, SAMPLE_RATE)
        sd.wait()
    except Exception:
        pass


def main():
    global _suppress_vad
    ap = argparse.ArgumentParser(description="饥荒实时语音 co-pilot（麦克风 → Dify → 建议）")
    ap.add_argument("--no-vad", action="store_true", help="关闭 VAD，只用热键触发")
    ap.add_argument("--no-tts", action="store_true", help="关闭语音播报，只回灌游戏文字")
    ap.add_argument("--hotkey", default=HOTKEY, help=f"按住说话热键（默认 {HOTKEY}）")
    ap.add_argument("--asr", default="whisper", choices=["whisper", "glm"], help="转文字引擎（默认 whisper 本地）")
    args = ap.parse_args()

    print("[voice] 状态服务:", dify_brain.STATE_API)
    print("[voice] Dify 工作流:", dify_brain.DIFY_API_URL)
    print("[voice] 目标:", dify_brain.GOAL)
    print("[voice] 转文字引擎:", args.asr)

    # —— 启动音频流 ——
    stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16",
                            blocksize=FRAME_SAMPLES, callback=_audio_callback)
    stream.start()

    # —— 启动全局热键（按住说话）。失败则降级为纯 VAD ——
    try:
        import keyboard
        keyboard.on_press_key(args.hotkey, _ptt_press)
        keyboard.on_release_key(args.hotkey, _ptt_release)
        print(f"[voice] 热键就绪：按住 [{args.hotkey}] 说话，松开识别", flush=True)
    except Exception as e:
        print(f"[voice] ⚠️ 热键注册失败（{e}），仅 VAD 可用", flush=True)

    if args.no_vad:
        print("[voice] VAD 已关闭，请按住热键说话", flush=True)
    else:
        print("[voice] VAD 已开启：直接说话，说完停顿 0.7s 自动识别（戴耳机避免游戏音误触发）", flush=True)
    print("[voice] 正在校准麦克风噪声底…（请保持安静 1 秒）", flush=True)
    print("[voice] Ctrl+C 退出\n", flush=True)

    _beep()

    # —— 主循环：串行消费已完成片段 ——
    try:
        while True:
            try:
                wav = _done_queue.get(timeout=0.2)
            except queue.Empty:
                continue
            _handle_utterance(wav, args)
    except KeyboardInterrupt:
        print("\n[voice] 已退出", flush=True)
    finally:
        try:
            stream.stop()
            stream.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
