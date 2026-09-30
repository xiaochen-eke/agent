"""
图片解析器 — 将饥荒游戏截图/场景图转换为结构化文本描述

技术路线（从易到难）：
  Level 1: BLIP/BLIP-2 图像描述 → 自然语言描述
  Level 2: YOLO 物体检测 + 场景分类 → 结构化信息
  Level 3: Qwen-VL / LLaVA / InternVL → 视觉语言理解

当前实现：Level 1（BLIP 图像描述 + 对象关键词增强）

依赖：
  pip install transformers pillow torch
  # BLIP 首次运行会自动下载模型（约 1.5GB）

如果依赖未安装，回退到「模拟模式」，返回占位描述方便开发调试。
"""

import os
import re
from typing import Dict, List, Optional, Tuple
from pathlib import Path

# 饥荒领域关键词（用于增强描述）
DONT_STARVE_KEYWORDS = {
    'creatures': [
        '蜘蛛', '猎犬', '猪人', '兔人', '牛', '高脚鸟', '企鹅',
        '树精卫士', '蜘蛛女王', '黑手党', '熊獾', '龙蝇', '蚁狮',
        '蜜蜂', '蝴蝶', '青蛙', '蚊子', '蠕虫', '影怪',
    ],
    'objects': [
        '营火', '篝火', '冰箱', '科学机器', '炼金引擎', '烹饪锅',
        '箱子', '帐篷', '农田', '浆果丛', '树枝', '燧石', '金块',
        '蜘蛛巢', '蜂巢', '猪人房', '兔人房',
    ],
    'biomes': [
        '森林', '草原', '沼泽', '沙漠', '岩石地', '墓地',
        '地下洞穴', '废墟',
    ],
    'seasons': [
        '春天', '夏天', '秋天', '冬天',
        '绿色草地', '雪花', '红叶', '雨天',
    ],
    'time_of_day': [
        '白天', '黄昏', '夜晚', '满月',
    ],
    'danger_signals': [
        '黑暗', '蜘蛛网', '触手', '火焰', '冰冻',
        '理智值低', '饥饿',
    ],
}


class ImageParser:
    """
    图片解析器

    用法:
        parser = ImageParser()
        result = parser.parse("screenshots/spider_attack.png")
        # result = {
        #     "caption": "一片森林里，玩家靠近一个蜘蛛巢，周围有蜘蛛在移动",
        #     "objects": ["蜘蛛", "蜘蛛巢", "森林"],
        #     "scene": "森林危险区域",
        #     "game_context": "你在森林区域，附近有蜘蛛巢。注意不要引太多蜘蛛..."
        # }
    """

    def __init__(self, device: str = None):
        """
        Args:
            device: 'cpu' | 'cuda' | None（自动检测）
        """
        self._model = None
        self._processor = None
        self._device = device
        self._available = None  # None = 未检测, True/False

    def _load_model(self) -> bool:
        """懒加载 BLIP 模型"""
        if self._available is not None:
            return self._available

        try:
            from PIL import Image
            import torch
            from transformers import BlipProcessor, BlipForConditionalGeneration

            # 国内优先使用 HF 镜像，避免下载超时
            os.environ.setdefault('HF_ENDPOINT', 'https://hf-mirror.com')
            os.environ.setdefault('no_proxy', '*')

            if self._device is None:
                self._device = "cuda" if torch.cuda.is_available() else "cpu"

            model_name = "Salesforce/blip-image-captioning-base"
            print(f"   [Multimodal] 加载 BLIP 模型: {model_name}")
            print(f"   [Multimodal] HF_ENDPOINT={os.environ.get('HF_ENDPOINT', 'default')}")
            self._processor = BlipProcessor.from_pretrained(model_name)
            self._model = BlipForConditionalGeneration.from_pretrained(model_name)
            self._model.to(self._device)
            self._available = True
            print(f"   [Multimodal] BLIP 加载完成 (device={self._device})")
            return True

        except ImportError as e:
            print(f"   [Multimodal] BLIP 依赖未安装 ({e})，使用模拟模式")
            print(f"   [Multimodal] 安装: pip install transformers pillow torch")
            self._available = False
            return False
        except Exception as e:
            print(f"   [Multimodal] BLIP 加载失败: {e}，使用模拟模式")
            self._available = False
            return False

    def parse(self, image_path: str) -> Dict:
        """
        解析图片，返回结构化描述

        Args:
            image_path: 图片文件路径

        Returns:
            {
                'caption': str,           # 自然语言描述
                'objects': List[str],     # 检测到的对象
                'scene': str,             # 场景分类
                'game_context': str,      # 游戏上下文提示
                'success': bool,          # 是否成功
                'engine': str,            # 使用的引擎
            }
        """
        if not os.path.exists(image_path):
            return {
                'caption': f'[图片路径不存在: {image_path}]',
                'objects': [],
                'scene': '未知',
                'game_context': '',
                'success': False,
                'engine': 'none',
            }

        if self._load_model():
            return self._parse_with_blip(image_path)
        else:
            return self._parse_fallback(image_path)

    def _parse_with_blip(self, image_path: str) -> Dict:
        """使用 BLIP 模型解析"""
        import torch
        from PIL import Image

        try:
            image = Image.open(image_path).convert("RGB")
            inputs = self._processor(image, return_tensors="pt").to(self._device)

            with torch.no_grad():
                out = self._model.generate(**inputs, max_length=60)

            caption = self._processor.decode(out[0], skip_special_tokens=True)

            # 饥荒领域关键词增强
            objects = self._extract_game_objects(caption)
            scene = self._classify_scene(caption, objects)
            game_context = self._build_game_context(caption, objects, scene)

            return {
                'caption': caption,
                'objects': objects,
                'scene': scene,
                'game_context': game_context,
                'success': True,
                'engine': 'BLIP (Salesforce/blip-image-captioning-base)',
            }

        except Exception as e:
            print(f"   [Multimodal] BLIP 推理失败: {e}")
            return self._parse_fallback(image_path)

    def _parse_fallback(self, image_path: str) -> Dict:
        """
        模拟模式（无模型时）
        基于文件名/路径做启发式分析，返回占位描述
        """
        fname = os.path.basename(image_path).lower()

        caption = f"[模拟模式] 图片已接收: {os.path.basename(image_path)}"
        objects = self._extract_game_objects(fname)
        scene = self._classify_scene(fname, objects)
        game_context = (
            f"⚠️ 图片解析模型未加载。"
            f"请运行: pip install transformers pillow torch\n"
            f"当前使用文件名推测: {', '.join(objects) if objects else '未识别到游戏元素'}"
        )

        return {
            'caption': caption,
            'objects': objects,
            'scene': scene,
            'game_context': game_context,
            'success': False,
            'engine': 'fallback (文件名推测)',
        }

    def _extract_game_objects(self, text: str) -> List[str]:
        """从文本中提取饥荒领域对象"""
        found = []
        for category, keywords in DONT_STARVE_KEYWORDS.items():
            for kw in keywords:
                if kw in text:
                    found.append(kw)
        # 去重保序
        seen = set()
        result = []
        for obj in found:
            if obj not in seen:
                seen.add(obj)
                result.append(obj)
        return result

    def _classify_scene(self, caption: str, objects: List[str]) -> str:
        """分类场景类型"""
        # 检查生物群落
        for biome in DONT_STARVE_KEYWORDS['biomes']:
            if biome in caption:
                # 进一步检查是否危险
                for danger in DONT_STARVE_KEYWORDS['danger_signals']:
                    if danger in caption:
                        return f"{biome}危险区域"
                return f"{biome}安全区域"

        # 检查是否有敌人
        has_enemy = any(
            creature in caption
            for creature in DONT_STARVE_KEYWORDS['creatures']
        )
        if has_enemy:
            return "战斗场景"

        # 检查时间
        for tod in DONT_STARVE_KEYWORDS['time_of_day']:
            if tod in caption:
                return f"{tod}探索"

        return "常规区域"

    def _build_game_context(self, caption: str, objects: List[str], scene: str) -> str:
        """根据识别结果构建游戏上下文"""
        parts = []

        if '蜘蛛' in objects or '蜘蛛巢' in objects:
            parts.append("注意蜘蛛仇恨范围，白天引出来逐个击杀，不要引到蜘蛛战士")
        if '猎犬' in objects:
            parts.append("猎犬即将来袭，准备武器和防具，可以引到陷阱阵")
        if '黑手党' in objects:
            parts.append("黑手党(Deerclops)冬季Boss，远离基地打，用火堆卡位")
        if '夜晚' in scene or '黑暗' in scene:
            parts.append("夜晚注意光照，远离黑暗区域避免查理攻击")
        if '冬天' in scene or '雪花' in objects:
            parts.append("冬季保暖优先：冬帽+保温石+精炼火堆")
        if '夏天' in scene:
            parts.append("夏季防过热：冰箱+冰火+西瓜帽，基地覆盖灭火器")

        if not parts:
            if '危险' in scene:
                parts.append("建议装备武器和防具，保持理智值充足")
            else:
                parts.append("当前场景看起来安全，可以收集资源和探索")

        return '；'.join(parts)


# ========== 便捷函数 ==========

_global_parser: Optional[ImageParser] = None


def get_image_parser(device: str = None) -> ImageParser:
    """获取全局 ImageParser 单例"""
    global _global_parser
    if _global_parser is None:
        _global_parser = ImageParser(device=device)
    return _global_parser


def parse_image(image_path: str) -> Dict:
    """便捷函数：直接解析图片"""
    return get_image_parser().parse(image_path)
