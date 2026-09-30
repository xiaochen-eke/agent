"""
多模态处理层 — 图片/语音 → 文本 → pipeline

Level 1 实现（推荐先做）：
- BLIP/BLIP-2 图片描述
- Whisper 语音转文字
- 统一路由接口

环境变量（国内网络必需）：
  HF_ENDPOINT=https://hf-mirror.com  # HuggingFace 镜像
  no_proxy=*                          # 绕过系统代理
"""

import os

# 国内网络：HuggingFace 镜像 + 绕过代理（在其他导入之前设置）
os.environ.setdefault('HF_ENDPOINT', 'https://hf-mirror.com')
os.environ.setdefault('no_proxy', '*')

from .router import MultimodalRouter
from .image_parser import ImageParser
from .speech_to_text import SpeechToText
