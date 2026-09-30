"""
语音转文字 — 将玩家语音问题转成文本，再进入 pipeline

技术方案：OpenAI Whisper
  - base 模型约 145MB，适合 CPU 实时推理
  - 中文/英文混合识别效果良好
  - 首次使用自动下载模型

依赖：
  pip install openai-whisper
  # 或 pip install whisper（旧版）

如果依赖未安装，回退到「模拟模式」。
"""

import os
import tempfile
from typing import Dict, List, Optional
from pathlib import Path


class SpeechToText:
    """
    语音转文字

    用法:
        stt = SpeechToText()
        result = stt.transcribe("player_question.wav")
        # result = {
        #     "text": "饥荒冬季怎么保暖",
        #     "language": "zh",
        #     "success": True,
        #     "engine": "whisper-base",
        # }
    """

    # 支持的音频格式
    SUPPORTED_FORMATS = {'.wav', '.mp3', '.m4a', '.ogg', '.flac', '.webm', '.mp4'}

    def __init__(self, model_size: str = "base"):
        """
        Args:
            model_size: 'tiny' | 'base' | 'small' | 'medium' | 'large'
                        base 推荐起步（145MB，CPU 可用）
                        tiny 更轻量但中文效果差
        """
        self._model = None
        self._model_size = model_size
        self._available = None

    def _load_model(self) -> bool:
        """懒加载 Whisper 模型"""
        if self._available is not None:
            return self._available

        try:
            import whisper
            print(f"   [Multimodal] 加载 Whisper 模型: {self._model_size}")
            self._model = whisper.load_model(self._model_size)
            self._available = True
            print(f"   [Multimodal] Whisper 加载完成 (size={self._model_size})")
            return True

        except ImportError:
            print(f"   [Multimodal] Whisper 未安装，使用模拟模式")
            print(f"   [Multimodal] 安装: pip install openai-whisper")
            self._available = False
            return False
        except Exception as e:
            print(f"   [Multimodal] Whisper 加载失败: {e}，使用模拟模式")
            self._available = False
            return False

    def transcribe(self, audio_path: str) -> Dict:
        """
        转录音频文件

        Args:
            audio_path: 音频文件路径 (.wav, .mp3, .m4a, etc.)

        Returns:
            {
                'text': str,          # 转录文本
                'language': str,      # 语言代码 (zh/en/...)
                'success': bool,
                'engine': str,
            }
        """
        if not os.path.exists(audio_path):
            return {
                'text': '',
                'language': 'unknown',
                'success': False,
                'engine': 'none',
                'error': f'文件不存在: {audio_path}',
            }

        # 检查格式
        ext = Path(audio_path).suffix.lower()
        if ext not in self.SUPPORTED_FORMATS:
            return {
                'text': '',
                'language': 'unknown',
                'success': False,
                'engine': 'none',
                'error': f'不支持的音频格式: {ext}，支持: {", ".join(sorted(self.SUPPORTED_FORMATS))}',
            }

        if self._load_model():
            return self._transcribe_with_whisper(audio_path)
        else:
            return self._transcribe_fallback(audio_path)

    def transcribe_bytes(self, audio_bytes: bytes, suffix: str = '.wav') -> Dict:
        """转录音频字节流（用于 API 上传）"""
        try:
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(audio_bytes)
                tmp.flush()
                result = self.transcribe(tmp.name)
            os.unlink(tmp.name)
            return result
        except Exception as e:
            return {
                'text': '',
                'language': 'unknown',
                'success': False,
                'engine': 'none',
                'error': f'转录异常: {e}',
            }

    def _transcribe_with_whisper(self, audio_path: str) -> Dict:
        """使用 Whisper 模型转录"""
        try:
            result = self._model.transcribe(
                audio_path,
                language=None,          # 自动检测语言
                task="transcribe",      # transcribe（原文） / translate（翻译为英文）
                fp16=False,             # CPU 用 fp32
                verbose=False,
            )

            text = result.get('text', '').strip()
            lang = result.get('language', 'unknown')

            return {
                'text': text,
                'language': lang,
                'success': True,
                'engine': f'whisper-{self._model_size}',
            }

        except Exception as e:
            print(f"   [Multimodal] Whisper 转录失败: {e}")
            return {
                'text': '',
                'language': 'unknown',
                'success': False,
                'engine': f'whisper-{self._model_size}',
                'error': str(e),
            }

    def _transcribe_fallback(self, audio_path: str) -> Dict:
        """模拟模式 — 返回占位文本"""
        fname = os.path.basename(audio_path)
        return {
            'text': f'[模拟模式] 语音文件 {fname} 已接收，请安装 openai-whisper 启用真实转录',
            'language': 'zh',
            'success': False,
            'engine': 'fallback (模拟)',
        }


# ========== 便捷函数 ==========

_global_stt: Optional[SpeechToText] = None


def get_speech_to_text(model_size: str = "base") -> SpeechToText:
    """获取全局 SpeechToText 单例"""
    global _global_stt
    if _global_stt is None:
        _global_stt = SpeechToText(model_size=model_size)
    return _global_stt


def transcribe_audio(audio_path: str) -> Dict:
    """便捷函数：直接转录"""
    return get_speech_to_text().transcribe(audio_path)
