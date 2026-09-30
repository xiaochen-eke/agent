"""
多模态统一路由器 — 所有输入类型（文本/图片/语音）统一转换成文本

工作流:
    Input (text / image / audio)
        ↓
    MultimodalRouter.route()
        ↓
    统一 text prompt
        ↓
    Pipeline.run()
"""

from typing import Dict, List, Optional, Union
from pathlib import Path
import os
import base64

from .image_parser import get_image_parser
from .speech_to_text import get_speech_to_text


class MultimodalRouter:
    """
    多模态统一路由

    用法:
        router = MultimodalRouter()
        result = router.route({"type": "text", "text": "冬季怎么生存"})
        result = router.route({"type": "image", "image_path": "screenshot.png"})
        result = router.route({"type": "audio", "audio_path": "question.wav"})

        # 混合输入
        result = router.route({
            "type": "image",
            "image_path": "screenshot.png",
            "caption": "请分析这张图里的危险"
        })
    """

    def __init__(self, image_parser=None, speech_to_text=None):
        self.image_parser = image_parser or get_image_parser()
        self.speech_to_text = speech_to_text or get_speech_to_text()

    def route(self, input_data: Dict) -> Dict:
        """
        路由多模态输入 → 统一文本输出

        Args:
            input_data: {
                'type': 'text' | 'image' | 'audio',
                # text
                'text': str (可选，用户附加文字说明),
                # image
                'image_path': str (图片文件路径),
                'image_bytes': bytes (base64 编码的图片，API 场景),
                # audio
                'audio_path': str (音频文件路径),
                'audio_bytes': bytes (base64 编码的音频),
            }

        Returns:
            {
                'text_prompt': str,        # 统一文本 — 可直接送入 Pipeline
                'input_type': str,         # 原始输入类型
                'parsed_info': {           # 解析详情
                    'caption': str,         # 图片描述 / 语音转录
                    'objects': List[str],   # 图片物体 / 空
                    'scene': str,           # 场景分类 / 空
                },
                'extra_context': str,      # 额外的上下文（注入 pipeline）
                'success': bool,
                'engine': str,             # 使用的引擎
            }
        """
        input_type = input_data.get('type', 'text')
        user_caption = input_data.get('caption', '') or input_data.get('text', '')

        result = {
            'input_type': input_type,
            'parsed_info': {},
            'extra_context': '',
            'success': True,
            'engine': 'none',
        }

        # 1. 文本 — 直接透传
        if input_type == 'text':
            result['text_prompt'] = user_caption or input_data.get('text', '')
            result['engine'] = 'text-pass-through'

        # 2. 图片 — BLIP 描述 + 游戏场景识别
        elif input_type == 'image':
            image_result = self._handle_image(input_data)
            result['parsed_info'] = {
                'caption': image_result.get('caption', ''),
                'objects': image_result.get('objects', []),
                'scene': image_result.get('scene', ''),
            }
            result['extra_context'] = image_result.get('game_context', '')
            result['success'] = image_result.get('success', False)
            result['engine'] = image_result.get('engine', 'fallback')

            # 构建 prompt
            prompt_parts = []
            if image_result.get('caption'):
                prompt_parts.append(f"[图片描述] {image_result['caption']}")
            if image_result.get('objects'):
                prompt_parts.append(f"[识别物体] {', '.join(image_result['objects'])}")
            if image_result.get('scene'):
                prompt_parts.append(f"[场景] {image_result['scene']}")
            if user_caption:
                prompt_parts.append(f"\n[玩家问题] {user_caption}")

            result['text_prompt'] = '\n'.join(prompt_parts) if prompt_parts else user_caption

        # 3. 音频 — Whisper 转录
        elif input_type == 'audio':
            audio_result = self._handle_audio(input_data)
            result['parsed_info'] = {
                'caption': audio_result.get('text', ''),
                'objects': [],
                'scene': '',
            }
            result['extra_context'] = ''
            result['success'] = audio_result.get('success', False)
            result['engine'] = audio_result.get('engine', 'fallback')

            transcribed = audio_result.get('text', '')
            if user_caption:
                result['text_prompt'] = f"[语音转录] {transcribed}\n[附加说明] {user_caption}"
            else:
                result['text_prompt'] = transcribed

        else:
            result['text_prompt'] = user_caption
            result['success'] = False
            result['engine'] = f'unknown-type-{input_type}'

        return result

    def _handle_image(self, data: Dict) -> Dict:
        """处理图片输入"""
        image_path = data.get('image_path', '')

        # 如果有 base64 编码的图片字节，先存成临时文件
        if not image_path and data.get('image_data'):
            import tempfile
            try:
                img_bytes = base64.b64decode(data['image_data'])
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                    tmp.write(img_bytes)
                    image_path = tmp.name
            except Exception:
                return {
                    'caption': '[无法解码图片数据]',
                    'objects': [],
                    'scene': '未知',
                    'game_context': '',
                    'success': False,
                    'engine': 'error',
                }

        if image_path:
            result = self.image_parser.parse(image_path)

            # 清理临时文件
            if data.get('image_data') and image_path:
                try:
                    os.unlink(image_path)
                except Exception:
                    pass

            return result

        return {
            'caption': '[未提供图片]',
            'objects': [],
            'scene': '未知',
            'game_context': '',
            'success': False,
            'engine': 'no-input',
        }

    def _handle_audio(self, data: Dict) -> Dict:
        """处理音频输入"""
        audio_path = data.get('audio_path', '')

        if not audio_path and data.get('audio_data'):
            import tempfile
            try:
                audio_bytes = base64.b64decode(data['audio_data'])
                suffix = data.get('audio_format', '.wav')
                with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                    tmp.write(audio_bytes)
                    audio_path = tmp.name
            except Exception:
                return {
                    'text': '[无法解码音频数据]',
                    'language': 'unknown',
                    'success': False,
                    'engine': 'error',
                }

        if audio_path:
            result = self.speech_to_text.transcribe(audio_path)

            # 清理临时文件
            if data.get('audio_data') and audio_path:
                try:
                    os.unlink(audio_path)
                except Exception:
                    pass

            return result

        return {
            'text': '[未提供音频]',
            'language': 'unknown',
            'success': False,
            'engine': 'no-input',
        }


# ========== 便捷函数 ==========

_global_router: Optional[MultimodalRouter] = None


def get_router() -> MultimodalRouter:
    """获取全局 MultimodalRouter 单例"""
    global _global_router
    if _global_router is None:
        _global_router = MultimodalRouter()
    return _global_router


def multimodal_to_text(input_data: Dict) -> str:
    """便捷函数：多模态 → 纯文本"""
    result = get_router().route(input_data)
    return result.get('text_prompt', '')
