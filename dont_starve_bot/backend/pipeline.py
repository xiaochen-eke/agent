"""
《饥荒 Don't Starve 游戏攻略助手》统一流水线架构

User Query → AgentController → TaskRouter → RAGStage → GenerationStage → PostProcessor → Answer

各层职责：
- AgentController : 意图识别 + 任务拆解 + 联网搜索判断
- TaskRouter      : 根据意图路由到不同执行路径
- RAGStage        : 向量检索 + 知识库查询
- GenerationStage : LLM 调用（虚拟 LoRA，领域提示词注入）
- PostProcessor   : 格式化 + 安全控制 + 工具结果整合
"""

import os
import sys
import json
import time
import re
from typing import Dict, List, Optional, Tuple
from openai import OpenAI

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

try:
    import torch
    HAS_TORCH = True
except ImportError:
    torch = None
    HAS_TORCH = False

# 导入现有模块
from fine_tuning_adapter import (
    DomainIntentRecognizer,
    DomainPromptOptimizer,
    ResponseFormatter,
    DomainKnowledgeEnhancer,
    SEASON_MAP,
    GAME_TERMS,
)


# ============================================================
# Layer 1: AgentController — 意图识别 + 任务拆解
# ============================================================

class AgentController:
    """
    升级版意图识别器：
    - 游戏领域意图分类（复用 DomainIntentRecognizer）
    - 联网搜索需求判断
    - 复杂问题任务拆解
    """

    # 需要联网搜索的关键词
    WEB_SEARCH_SIGNALS = [
        r'最新', r'今天', r'今日', r'新闻', r'热点', r'现在', r'当前',
        r'最近', r'刚刚', r'实时', r'发生', r'出了', r'更新',
    ]

    # 任务拆解分隔词
    TASK_SPLIT_SIGNALS = [
        r'(还要|并且|同时|另外|此外|以及|和|跟|还有).*(怎么|如何|怎样|什么)',
    ]

    def __init__(self):
        self.intent_recognizer = DomainIntentRecognizer()

    def analyze(self, user_input: str) -> Dict:
        """
        分析用户输入，返回：
        {
            'intents': ['survival_strategy', ...],   # 游戏意图
            'entities': {'seasons': [...], ...},     # 游戏实体
            'needs_web_search': bool,                # 是否需要联网
            'sub_tasks': [str, ...],                # 拆解后的子任务
            'main_query': str,                       # 主查询
        }
        """
        # 1. 游戏领域意图
        intents = self.intent_recognizer.recognize(user_input)

        # 2. 游戏实体提取
        entities = self.intent_recognizer.extract_entities(user_input)

        # 3. 联网搜索判断
        needs_web = self._detect_web_search(user_input)

        # 4. 任务拆解
        sub_tasks = self._decompose(user_input)

        return {
            'intents': intents,
            'entities': entities,
            'needs_web_search': needs_web,
            'sub_tasks': sub_tasks,
            'main_query': user_input,
        }

    def _detect_web_search(self, text: str) -> bool:
        """检测是否需要联网搜索"""
        for sig in self.WEB_SEARCH_SIGNALS:
            if re.search(sig, text):
                return True
        return False

    def _decompose(self, text: str) -> List[str]:
        """智能任务拆解"""
        tasks = []

        # 规则1：连接词拆分
        connectors = r'(还要|并且|同时|另外|此外|以及|然后|之后|接着|和|跟|还有)'
        parts = re.split(connectors, text)
        if len(parts) >= 2:
            # 合并连接词和后续内容
            merged = []
            i = 0
            while i < len(parts):
                # 跳过连接词，直接拿后面的内容
                if re.fullmatch(connectors, parts[i]):
                    merged[-1] = merged[-1] + ' ' + parts[i] + parts[i+1] if merged else parts[i] + parts[i+1]
                    i += 2
                else:
                    merged.append(parts[i])
                    i += 1
            meaningful = [p.strip() for p in merged if len(p.strip()) > 4]
            if len(meaningful) >= 2:
                return meaningful

        # 规则2：按疑问词拆
        q_matches = re.findall(r'[^，,；;。．]*?[怎么|如何|怎样|什么|哪][^，,；;。．]*', text)
        if len(q_matches) >= 2:
            return [q.strip() for q in q_matches if len(q.strip()) > 4]

        # 规则3：关键词固定拆法
        PAIRS = [
            (r'冬季.*生存.*打.*[Bb]oss', ['冬季生存攻略', '冬季Boss打法', '整合防守策略']),
            (r'(新手|前期|开局).*(发育|生存)', ['前期资源收集', '基地建设规划', '度过第一个季节']),
            (r'打.*[Bb]oss.*装备', ['Boss弱点分析', '装备推荐', '战术安排']),
        ]
        for pat, subtasks in PAIRS:
            if re.search(pat, text):
                return subtasks

        return [text]

    def extract_memory(self, query: str, response: str) -> Dict[str, str]:
        """从对话中提取记忆点"""
        mem = {}
        # 季节
        for s in ['春', '夏', '秋', '冬']:
            if s in query or s in response:
                mem['current_season'] = s
        # Boss
        for boss in ['黑手党', 'Deerclops', '蜘蛛女王', '树精卫士', '熊獾', '龙蝇', '蚁狮']:
            if boss in query or boss in response:
                mem['last_boss'] = boss
        # 食物
        for food in ['肉丸', '肉汤', '火龙果派', '腊肉', '太妃糖', '蝴蝶松饼']:
            if food in query:
                mem['last_recipe'] = food
        # 角色
        for char in ['威尔逊', '薇洛', '沃尔夫冈', '温蒂', 'WX-78', '薇格弗德', '老奶奶']:
            if char in query or char in response:
                mem['last_character'] = char
        # 新手水平
        if any(w in query for w in ['新手', '前期', '开局', '刚玩']):
            mem['user_level'] = '新手'
        elif any(w in query for w in ['中后期', '后期', '大后期', '远古']):
            mem['user_level'] = '老手'
        return mem


# ============================================================
# Layer 2: TaskRouter — 意图路由
# ============================================================

# ============================================================
# Layer 2: DecisionArbiter — 统一仲裁器（三方打分 + 规则加权 + softmax）
# ============================================================

class DecisionArbiter:
    """
    三方独立打分 → 规则加权（不覆盖）→ softmax 归一化 → 裁决

    原则：
    - 规则只给引擎加权，不直接决定路由
    - softmax 把分数变成可比较的概率分布
    - 最高分胜出，冲突由 score 说话
    """

    # 意图加权表（规则只 boost，不 override）
    RULE_BOOST = {
        'mechanic_explain':   {'rag': 0.30, 'lora': 0.10},
        'food_recipe':        {'rag': 0.25, 'lora': 0.15},
        'building_craft':     {'rag': 0.25, 'lora': 0.10},
        'equipment_guide':    {'rag': 0.20, 'lora': 0.15},
        'survival_strategy':  {'rag': 0.25, 'lora': 0.25},
        'seasonal_prep':      {'rag': 0.30, 'lora': 0.15},
        'boss_fight':         {'rag': 0.30, 'lora': 0.10},
        'general_query':      {'lora': 0.10},
    }

    def decide(self, rag_score: float, lora_score: float, agent_score: float,
               intents: List[str], needs_web: bool = False) -> Dict:
        """
        输入三方原始评分 → 输出仲裁结果

        Returns:
            {'choice': str, 'raw': dict, 'boosted': dict, 'final': dict, 'weights_applied': dict}
        """
        import math

        raw = {'rag': rag_score, 'lora': lora_score, 'agent': agent_score}

        # 规则加权
        boosted = dict(raw)
        weights_applied = {}
        for intent in intents:
            boost = self.RULE_BOOST.get(intent, {})
            for engine, w in boost.items():
                boosted[engine] += w
                weights_applied[intent] = boost

        # 截断到 [0, 1]
        for k in boosted:
            boosted[k] = max(0.0, min(1.0, boosted[k]))

        # softmax 归一化
        vals = list(boosted.values())
        max_v = max(vals) if vals else 0
        exp_vals = [math.exp(v - max_v) for v in vals]
        total = sum(exp_vals) or 1.0
        final = {}
        for k, ev in zip(boosted.keys(), exp_vals):
            final[k] = round(ev / total, 4)

        # 最高分引擎
        choice = max(final, key=final.get)

        # 联网信号强 → 强制 Agent（覆盖 softmax）
        if needs_web and boosted.get('agent', 0) > 0.5:
            choice = 'agent'

        return {
            'choice': choice,
            'raw': {k: round(v, 4) for k, v in raw.items()},
            'boosted': {k: round(v, 4) for k, v in boosted.items()},
            'final': final,
            'weights_applied': weights_applied,
        }


# ============================================================
# Layer 2.5: ToolExecutor — 游戏数据工具调用
# ============================================================

class ToolExecutor:
    """
    游戏领域专用工具执行器 — 从 game_data_api 获取权威数据。
    不是"文本拼接"，而是实际的工具调用（类似 Function Calling）。
    """
    TOOL_SCHEMA = {
        "search_recipes": {
            "desc": "查询饥荒食物配方和属性",
            "keywords": ["食谱", "食物", "配方", "肉丸", "肉汤", "怎么做", "吃什么", "烹饪", "料理"],
        },
        "search_creatures": {
            "desc": "查询怪物属性、掉落、打法",
            "keywords": ["怪物", "Boss", "怎么打", "蜘蛛", "猎犬", "龙蝇", "熊獾", "掉落", "女王", "黑手党"],
        },
        "search_items": {
            "desc": "查询物品、建筑、合成配方",
            "keywords": ["合成", "配方", "怎么做", "建造", "建筑", "材料", "工具", "武器", "防具", "装备"],
        },
        "search_seasons": {
            "desc": "查询季节生存攻略",
            "keywords": ["春季", "夏季", "秋季", "冬季", "春天", "夏天", "秋天", "冬天", "季节", "生存"],
        },
    }

    def __init__(self):
        self._game_db = self._load_game_db()

    def _load_game_db(self) -> Dict:
        """整合：本地知识库 md + fine_tuning_adapter 术语表 + 硬编码速查"""
        db = {
            "recipes": {
                "肉丸": {"配方": "肉度≥1 + 填充物×3", "饱食度": 62.5, "理智": 12.5, "血量": 0, "烹饪时间": "20s", "技巧": "性价比最高，前期必做。怪物肉最多1个否则变怪物千层面"},
                "肉汤": {"配方": "大肉×2 + 怪物肉×1 + 填充物", "饱食度": 150, "理智": 5, "血量": 12, "烹饪时间": "30s", "技巧": "高饱食战斗专用"},
                "火龙果派": {"配方": "火龙果×1 + 填充物×3", "饱食度": 75, "理智": 5, "血量": 40, "烹饪时间": "40s", "技巧": "种田玩家首选"},
                "蝴蝶松饼": {"配方": "蝴蝶翅膀×1 + 蜂蜜×1 + 树枝×2", "饱食度": 37.5, "理智": 100, "血量": 15, "烹饪时间": "40s", "技巧": "高理智回复神器"},
                "太妃糖": {"配方": "蜂蜜×3 + 树枝×1", "饱食度": 25, "理智": 15, "血量": -3, "烹饪时间": "40s", "技巧": "平民回理智，扣3血忽略不计"},
                "冰淇淋": {"配方": "奶制品×1 + 蜂蜜×1 + 冰块×2", "饱食度": 25, "理智": 50, "血量": 0, "烹饪时间": "10s", "技巧": "超高回理智+强降温，夏天必备"},
                "饺子": {"配方": "蛋×1 + 肉×1 + 蔬菜×1 + 填充物", "饱食度": 37.5, "理智": 5, "血量": 40, "烹饪时间": "20s", "技巧": "高回血，Boss战必备"},
                "曼德拉草汤": {"配方": "曼德拉草×1 + 树枝×3", "饱食度": 150, "理智": 50, "血量": 100, "烹饪时间": "60s", "技巧": "满状态复活药，全图就几个曼德拉草省着用"},
                "蛙腿三明治": {"配方": "蛙腿×1 + 蔬菜×1 + 填充物×2", "饱食度": 37.5, "理智": 5, "血量": 20, "烹饪时间": "40s", "技巧": "青蛙池塘边随便做"},
                "腊肉": {"配方": "肉×1 + 盐×1 + 填充物×2", "饱食度": 50, "理智": 12.5, "血量": 20, "烹饪时间": "60s(干燥架)", "技巧": "保质期极长，冬季囤货必需品"},
            },
            "creatures": {
                "蜘蛛": {"血量": 100, "伤害": 10, "掉落": "蜘蛛丝、蜘蛛腺体、怪物肉", "打法": "1-2下风筝，白天引出来打。不要打巢边太多会被群殴"},
                "蜘蛛女王": {"血量": 2500, "伤害": 80, "掉落": "蜘蛛卵、女王帽、大量蜘蛛丝", "打法": "引到猪人村，猪群围殴。自己远程补刀。别在巢边打"},
                "猎犬": {"血量": 150, "伤害": 20, "掉落": "狗牙、怪物肉", "打法": "单个风筝，群了引到陷阱阵。红狗死后会着火"},
                "树精卫士": {"血量": 2000, "伤害": 50-150, "掉落": "活木×6、怪物肉", "打法": "打4走1，戴猪皮帽硬刚。不想打就种树苗安抚"},
                "黑手党(Deerclops)": {"血量": 4000, "伤害": 150, "掉落": "鹿角、大肉×8", "打法": "冬季Boss。提前在基地外围建陷阱。用火堆卡位风筝。听到叫声远离基地"},
                "熊獾": {"血量": 6000, "伤害": 200, "掉落": "熊皮、大肉×8", "打法": "秋天来偷吃。引到松树林让它当伐木工。打的时候打2走1"},
                "龙蝇": {"血量": 27500, "伤害": "150(近战)+火焰", "掉落": "龙鳞、大肉×8、金块×8", "打法": "夏天Boss。做冰火+冰杖远程冻结。用墙卡位防召唤虫子"},
                "蚁狮": {"血量": 6000, "伤害": "100", "掉落": "沙之石、金块", "打法": "夏天沙漠Boss。供奉玩具延缓地震。直接打用冷/暖石卡位"},
                "高脚鸟": {"血量": 400, "伤害": "50", "掉落": "大肉×2", "打法": "打2走1。偷蛋孵宠物但长大后会攻击你"},
            },
            "items": {
                "冬帽": {"材料": "树枝×2 + 蜘蛛丝×6", "效果": "保暖60秒", "解锁": "无需科技"},
                "保温石": {"材料": "石头×10 + 燧石×3", "效果": "保温(可加热)", "解锁": "科学机器"},
                "火腿棒": {"材料": "树枝×2 + 大肉×2 + 猪皮×1", "效果": "伤害59(满新鲜度), 耐久随新鲜度下降", "解锁": "炼金引擎"},
                "眼球伞": {"材料": "眼球×1 + 树枝×15 + 骨头碎片×4", "效果": "100%防雨 + 防热", "解锁": "炼金引擎"},
                "排箫": {"材料": "芦苇×5 + 曼德拉草×1 + 绳子×1", "效果": "全屏强制催眠", "解锁": "魔法栏"},
                "狗牙陷阱": {"材料": "狗牙×1 + 木头×1 + 绳子×1", "效果": "60伤害自动触发", "解锁": "科学机器"},
                "科学机器": {"材料": "金子×1 + 木头×4 + 石头×4", "效果": "解锁一级科技", "解锁": "无需"},
                "炼金引擎": {"材料": "金子×6 + 木板×4 + 石砖×2", "效果": "解锁二级科技", "解锁": "科学机器"},
                "冰箱": {"材料": "金块×2 + 石砖×2 + 木板×2", "效果": "减缓食物腐烂", "解锁": "炼金引擎"},
                "烹饪锅": {"材料": "石砖×3 + 木炭×3 + 树枝×3", "效果": "做高级料理", "解锁": "科学机器"},
                "避雷针": {"材料": "金块×3 + 石砖×3", "效果": "防雷击范围40地皮", "解锁": "科学机器"},
            },
            "seasons": {
                "秋": "开局季节。气温温和无特殊危险。目标：探图→建基地→科技→囤食物。注意：秋季结束前务必做好冬帽和保温石，准备过冬。",
                "冬": "极寒季节。保暖第一：冬帽+保温石+精炼火堆。食物储备3000+饱食度。第10天左右出黑手党(Deerclops)一定要提前建陷阱。地下洞穴冬天最安全。",
                "春": "多雨季节。做雨伞+眼球伞防湿。蜘蛛和青蛙大量繁殖趁机刷资源。春天Boss麋鹿鹅(Moose/Goose)在集结点刷新。",
                "夏": "极热季节。做冰火+冰箱+西瓜帽。基地全覆盖灭火器防野火。避雷针防雷。中午避开烈日出门。夏天Boss龙蝇出现。",
            },
        }
        # 合并知识库提取的数据
        try:
            from build_lora_dataset import extract_entities
            kb_dir = os.path.join(os.path.dirname(__file__), '..', 'knowledge_base')
            for fname in os.listdir(kb_dir) if os.path.isdir(kb_dir) else []:
                if fname.endswith('.md'):
                    items = extract_entities(open(os.path.join(kb_dir, fname), encoding='utf-8').read())
                    for item in items:
                        if '配方' in fname and item.get('props'):
                            db['recipes'][item['name']] = {k: v for k, v in item['props'].items()}
        except Exception:
            pass
        return db

    def execute(self, tool_name: str, query: str) -> Dict:
        """执行工具调用，返回 {'found': bool, 'data': ..., 'text': '...'}"""
        query_lower = query.lower()

        if tool_name == "search_recipes":
            matches = {}
            for name, info in self._game_db.get("recipes", {}).items():
                if name in query or any(k in query for k in [name, '食谱', '食物', '配方']):
                    matches[name] = info
            if not matches:
                return {"found": False, "data": {}, "text": f"未找到「{query}」相关食谱"}
            text = "\n".join(f"【{n}】{info}" for n, info in list(matches.items())[:3])
            return {"found": True, "data": matches, "text": text}

        elif tool_name == "search_creatures":
            matches = {}
            for name, info in self._game_db.get("creatures", {}).items():
                if any(k in query for k in [name, '怪物', 'Boss', '怎么打']):
                    matches[name] = info
            if not matches:
                return {"found": False, "data": {}, "text": f"未找到「{query}」相关怪物数据"}
            text = "\n".join(f"【{n}】血量{info.get('血量','?')} 伤害{info.get('伤害','?')} 掉落:{info.get('掉落','?')} 打法:{info.get('打法','?')}"
                             for n, info in list(matches.items())[:3])
            return {"found": True, "data": matches, "text": text}

        elif tool_name == "search_items":
            matches = {}
            for name, info in self._game_db.get("items", {}).items():
                if any(k in query for k in [name, '合成', '配方', '怎么做', '建造', '材料', '工具', '武器', '防具', '装备']):
                    matches[name] = info
            if not matches:
                return {"found": False, "data": {}, "text": f"未找到「{query}」相关物品"}
            text = "\n".join(f"【{n}】{info}" for n, info in list(matches.items())[:3])
            return {"found": True, "data": matches, "text": text}

        elif tool_name == "search_seasons":
            matches = {}
            for name, info in self._game_db.get("seasons", {}).items():
                if any(k in query for k in [name, '季节', '春季', '夏季', '秋季', '冬季', '春天', '夏天', '秋天', '冬天']):
                    matches[name] = info
            if not matches:
                return {"found": False, "data": {}, "text": f"未找到「{query}」相关季节攻略"}
            text = "\n".join(f"【{n}季】{info}" for n, info in matches.items())
            return {"found": True, "data": matches, "text": text}

        return {"found": False, "data": {}, "text": f"未知工具: {tool_name}"}

    def detect_tools(self, query: str) -> List[str]:
        """检测 query 需要哪些工具"""
        needed = []
        for tool_name, schema in self.TOOL_SCHEMA.items():
            score = sum(1 for kw in schema["keywords"] if kw in query)
            if score >= 1:
                needed.append(tool_name)
        return needed or ["search_seasons"]  # 默认查季节


# ============================================================
# RAG 缓存 — LRU + TTL + Key 归一化
# ============================================================
from collections import OrderedDict

class RAGCache:
    """LRU 缓存 + TTL 过期，防止内存无限增长"""

    def __init__(self, maxsize: int = 256, ttl: float = 1800.0):
        self._cache = OrderedDict()
        self.maxsize = maxsize
        self.ttl = ttl  # 30 分钟默认

    @staticmethod
    def normalize_key(query: str) -> str:
        """Key 归一化：去空白 + 小写 + 截断，避免相似查询重复嵌入"""
        return query.strip().lower()[:200]

    def get(self, key: str):
        k = self.normalize_key(key)
        if k not in self._cache:
            return None
        value, timestamp = self._cache[k]
        if time.time() - timestamp > self.ttl:
            del self._cache[k]
            return None
        self._cache.move_to_end(k)
        return value

    def put(self, key: str, value):
        k = self.normalize_key(key)
        if k in self._cache:
            self._cache.move_to_end(k)
        self._cache[k] = (value, time.time())
        while len(self._cache) > self.maxsize:
            self._cache.popitem(last=False)


# ============================================================
# Layer 3: RAGStage — 向量知识库检索
# ============================================================

class RAGStage:
    """封装向量知识库检索 + 简单缓存"""

    def __init__(self, knowledge_base):
        self.kb = knowledge_base
        self._cache = RAGCache(maxsize=256, ttl=1800)  # LRU + TTL + Key 归一化

    def retrieve(self, query: str, k: int = 3) -> Tuple[str, List[str]]:
        """返回 (context_str, sources_list) — 含 LRU cache"""
        cached = self._cache.get(query)
        if cached is not None:
            if isinstance(cached, tuple) and len(cached) == 3:
                return cached[0], cached[1]  # ignore score
            return cached[0], cached[1]

        if self.kb.get_doc_count() == 0:
            self._cache.put(query, ("", [], 0.0))
            return "", []

        docs = self.kb.retrieve(query, k=k)
        if not docs:
            self._cache.put(query, ("", [], 0.0))
            return "", []

        sources = []
        context = "【📚 参考知识库 — 以下来自深度玩家攻略】\n"
        best_sim = 0.0
        for doc in docs:
            source = doc.get('metadata', {}).get('source', '未知')
            sources.append(source)
            content = doc.get('content', '')
            snippet = content[:200] + "..." if len(content) > 200 else content
            context += f"\n### {source}\n{snippet}\n"
            # ChromaDB 用 cosine 距离，相似度 = 1 - distance
            dist = doc.get('similarity', 1.0)
            sim = max(0.0, 1.0 - dist)
            best_sim = max(best_sim, sim)

        result = (context, sources, best_sim)
        self._cache.put(query, result)
        return context, sources

    def get_similarity(self, query: str) -> float:
        """获取最高 RAG 相似度 (0~1) — 优先走缓存"""
        cached = self._cache.get(query)
        if cached is not None:
            if isinstance(cached, tuple) and len(cached) == 3:
                return cached[2]
        _, _ = self.retrieve(query)
        cached = self._cache.get(query)
        if cached is not None and isinstance(cached, tuple) and len(cached) == 3:
            return cached[2]
        return 0.0


# ============================================================
# Layer 4: GenerationStage — 虚拟 LoRA（领域提示词注入）
# ============================================================

# 饥荒领域核心系统提示词（精简版，减少 LLM 首 token 延迟）
LORA_SYSTEM_PROMPT = """你是一位资深《饥荒》游戏攻略专家，用"老玩家带新手"的语气回答。

【核心机制】
- 三围属性：理智(Sanity 0-200)、饥饿(0-150)、血量(0-150)、体温
- 四季：春(蜘蛛青蛙多)、夏(过热/火灾)、秋(储备)、冬(冻死+黑手党Boss)
- 食物：肉丸(+62.5饱食/12.5理智)、蝴蝶松饼(+100理智)、太妃糖(+15理智)、冰淇淋(+50理智+降温)
- Boss：树精(怕火)、蜘蛛女王(洞穴)、Deerclops(冬)
- 建造：营火、冰箱、科学机器、烹饪锅

【原则】给具体步骤和数值，不泛泛而谈。高危操作必须加安全提示。DST和单机版区分清楚。不编造机制和数值。"""


class GenerationStage:
    """
    LLM 调用层 — 优先用真实 LoRA，否则用虚拟 LoRA（领域提示词注入）

    两种模式：
    1. 真实 LoRA: 如果 backend/lora_model/lora_info.json 存在，加载 PEFT 模型
    2. 虚拟 LoRA: 注入 LORA_SYSTEM_PROMPT 模拟领域知识
    """

    def __init__(self, api_key: str):
        # 用 httpx.Timeout 做硬 HTTP 超时（float timeout 在智谱 API 上不生效）
        if HAS_HTTPX:
            _timeout = httpx.Timeout(45.0, connect=10.0)
        else:
            _timeout = 45.0
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://open.bigmodel.cn/api/paas/v4/",
            timeout=_timeout,
            max_retries=0,  # 不重试，超时就快速失败
        )

        # LoRA — 启动时同步加载（约 10 秒）
        self.lora_model = None
        self.lora_tokenizer = None
        self.lora_info = None
        self.lora_available = False
        self._try_load_lora()
        self.lora_available = self.lora_model is not None
        if self.lora_available:
            print("   [LoRA] OK PeftModel.from_pretrained() 成功, 推理引擎已激活")
        else:
            print("   [LoRA] FAIL 未加载, 使用 GLM-4-Flash")

    def _try_load_lora(self):
        """加载 LoRA 模型（同步，不阻塞其他模块加载）"""
        self.lora_model = None
        self.lora_tokenizer = None
        self.lora_info = None

        lora_dir = os.path.join(os.path.dirname(__file__), 'lora_model')
        info_path = os.path.join(lora_dir, 'lora_info.json')

        if not os.path.exists(info_path):
            print("   [LoRA] 未检测到模型，使用 GLM-4-Flash 虚拟 LoRA")
            return

        try:
            with open(info_path, 'r') as f:
                info = json.load(f)
            if not info.get('trained'):
                return

            base_model_name = info.get('base_model', 'gpt2')
            r = info.get('lora_r', 8)
            alpha = info.get('lora_alpha', 16) if 'lora_alpha' in info else 16

            print(f"   [LoRA] ========================================")
            print(f"   [LoRA] 基座: {base_model_name}")
            print(f"   [LoRA] LoRA: r={r} alpha={alpha} 数据={info.get('dataset_size','?')}条")
            print(f"   [LoRA] 权重: {lora_dir}/adapter_model.safetensors")
            print(f"   [LoRA] 加载中...")

            os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
            os.environ["no_proxy"] = "*"

            import torch as _torch
            from transformers import AutoTokenizer, AutoModelForCausalLM
            from peft import PeftModel

            tokenizer = AutoTokenizer.from_pretrained(
                base_model_name, local_files_only=True
            )
            if tokenizer.pad_token is None:
                tokenizer.pad_token = tokenizer.eos_token
            print(f"   [LoRA] tokenizer 加载完")

            model = AutoModelForCausalLM.from_pretrained(
                base_model_name, local_files_only=True
            )
            print(f"   [LoRA] 基座类型: {type(model).__name__}")

            model = PeftModel.from_pretrained(model, lora_dir)
            print(f"   [LoRA] PeftModel.from_pretrained() 完成!")
            print(f"   [LoRA] 最终类型: {type(model).__name__}")

            # 旁路验证: 同 prompt 跑两次对比
            print(f"   [LoRA] ------------------------------------------------")
            print(f"   [LoRA] 旁路验证: 同一 prompt 对比 LoRA vs 裸模型")
            test_prompt = "### 问题: 饥荒冬季怎么保暖\n### 回答:"
            try:
                base_model_tmp = AutoModelForCausalLM.from_pretrained(base_model_name, local_files_only=True)
                base_model_tmp.to("cpu")
                base_inputs = tokenizer(test_prompt, return_tensors="pt", max_length=64, truncation=True)
                with _torch.no_grad():
                    base_out = base_model_tmp.generate(**base_inputs, max_new_tokens=60, do_sample=False,
                        pad_token_id=tokenizer.eos_token_id)
                base_text = tokenizer.decode(base_out[0], skip_special_tokens=True)[len(test_prompt):]
                del base_model_tmp

                model.to("cpu")
                lora_inputs = tokenizer(test_prompt, return_tensors="pt", max_length=64, truncation=True)
                with _torch.no_grad():
                    lora_out = model.generate(**lora_inputs, max_new_tokens=60, do_sample=False,
                        pad_token_id=tokenizer.eos_token_id)
                lora_text = tokenizer.decode(lora_out[0], skip_special_tokens=True)[len(test_prompt):]

                print(f"   [LoRA] 裸模型: {base_text[:80]}...")
                print(f"   [LoRA] +LoRA:  {lora_text[:80]}...")
                if base_text == lora_text:
                    print(f"   [LoRA] WARNING: 输出相同, LoRA 未改变 forward!")
                else:
                    print(f"   [LoRA] PASS: 输出不同, LoRA 参与 forward 计算!")
            except Exception as e:
                print(f"   [LoRA] 验证跳过: {e}")
            print(f"   [LoRA] ------------------------------------------------")

            self.lora_model = model
            self.lora_tokenizer = tokenizer
            self.lora_info = info

        except ImportError as e:
            print(f"   [LoRA] 缺少依赖 ({e})，使用 GLM-4-Flash")
        except FileNotFoundError as e:
            print(f"   [LoRA] 模型文件缺失: {e}")
        except Exception as e:
            import traceback
            print(f"   [LoRA] 加载失败: {e}")
            traceback.print_exc()
            print(f"   [LoRA] 回退到 GLM-4-Flash 虚拟 LoRA")

    def _generate_with_lora(self, query: str, rag_context: str = "",
                             extra_context: str = "") -> str:
        """LoRA 推理 — 不带质量过滤，原生输出"""
        if not HAS_TORCH or not self.lora_model:
            return ""

        prompt = f"### 问题: {query}\n### 回答:"

        inputs = self.lora_tokenizer(prompt, return_tensors="pt", truncation=True, max_length=480)
        device = "cuda" if torch.cuda.is_available() else "cpu"
        self.lora_model.to(device)
        inputs = {k: v.to(device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self.lora_model.generate(
                **inputs, max_new_tokens=200, temperature=0.8,
                do_sample=True, top_p=0.9, top_k=50,
                repetition_penalty=1.2, no_repeat_ngram_size=4,
                pad_token_id=self.lora_tokenizer.eos_token_id,
                eos_token_id=self.lora_tokenizer.eos_token_id,
            )

        full = self.lora_tokenizer.decode(outputs[0], skip_special_tokens=True)
        return full[len(prompt):].strip()

    def _generate_virtual(self, query: str, rag_context: str = "",
                           extra_context: str = "",
                           intent_context: str = "") -> str:
        """虚拟 LoRA — 通过领域提示词注入，GLM-4-Flash（快）"""
        context_parts = []
        if rag_context:
            context_parts.append(rag_context)
        if extra_context:
            context_parts.append(extra_context)
        context_block = "\n\n".join(context_parts) if context_parts else ""

        system = LORA_SYSTEM_PROMPT
        if intent_context:
            system += "\n" + intent_context

        if context_block:
            user_prompt = f"{context_block}\n\n【用户问题】\n{query}"
        else:
            user_prompt = query

        # 统一使用免费模型 glm-4-flash
        model = "glm-4-flash"
        call_timeout = httpx.Timeout(60.0, connect=8.0) if HAS_HTTPX else 60.0

        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=2048,
                timeout=call_timeout,
            )
            return response.choices[0].message.content
        except Exception as e:
            err_msg = str(e)
            if 'timeout' in err_msg.lower() or 'timed out' in err_msg.lower():
                return "⏳ AI 服务响应超时，请稍后再试。如果频繁出现，可以尝试简化问题或换个问法。"
            return f"❌ 模型调用失败: {err_msg}"

    def generate(self, query: str, rag_context: str = "",
                 extra_context: str = "",
                 intent_context: str = "") -> Tuple[str, str]:
        """
        推理策略：
        - 有 RAG/工具上下文 → GLM-4-Flash（快、整合检索结果）
        - 无上下文 → LoRA（领域微调模型，秒级响应）
        """
        if rag_context or extra_context:
            answer = self._generate_virtual(query, rag_context, extra_context, intent_context)
            engine = 'GLM-4-Flash (+RAG)' if rag_context else 'GLM-4-Flash'
            return answer, engine

        # 无上下文 → LoRA 直接回答
        if self.lora_available:
            answer = self._generate_with_lora(query)
            if answer:
                return answer, 'LoRA (PeftModelForCausalLM)'
            return self._generate_virtual(query, '', '', intent_context), 'GLM-4-Flash (LoRA 输出为空)'

        return self._generate_virtual(query, '', '', intent_context), 'GLM-4-Flash (无 LoRA)'

    def generate_without_tools(self, query: str, agent_steps: List[Dict]) -> str:
        """让模型基于 Agent 搜索结果总结回答（不带工具）"""
        search_context = ""
        for s in agent_steps:
            search_context += f"\n【{s['tool']} 结果】\n{s['result_preview']}"

        msgs = [
            {"role": "system", "content": "你是小搜，智能搜索助手。根据搜索结果用中文总结回答，结果不相关就说不知道。"},
            {"role": "user", "content": f"问题: {query}\n\n{search_context}\n\n请根据以上搜索结果回答。"},
        ]
        call_timeout = httpx.Timeout(40.0, connect=8.0) if HAS_HTTPX else 40.0
        try:
            response = self.client.chat.completions.create(
                model="glm-4-flash",
                messages=msgs,
                temperature=0.7,
                max_tokens=2048,
                timeout=call_timeout,
            )
            return response.choices[0].message.content
        except Exception:
            return f"很抱歉，搜索「{query}」时遇到问题，请稍后重试。"

    # get_lora_confidence 已废弃 — 评分统一由 Pipeline.run() 从 rag_stage 同源派生


# ============================================================
# Layer 5: PostProcessor — 格式化 + 安全控制
# ============================================================

class PostProcessor:
    """后处理：格式增强 + 安全检查 + 术语标准化 + 交叉引用"""

    def __init__(self):
        self.formatter = ResponseFormatter()
        self.enhancer = DomainKnowledgeEnhancer()

    def process(self, raw_answer: str, analysis: Dict,
                sources: List[str], apis_used: List[str],
                agent_steps: List[Dict] = None,
                engine: str = 'GLM-4-Flash') -> Dict:
        """返回处理后的完整结果"""
        intents = analysis.get('intents', [])

        # 1. 数值验证
        answer = self.enhancer.validate_stat_values(raw_answer)

        # 2. 术语标准化
        answer = self.enhancer.standardize_terminology(answer)

        # 3. 意图特定格式化
        if 'survival_strategy' in intents:
            seasons = analysis.get('entities', {}).get('seasons', []) or []
            season = seasons[0] if seasons else None
            answer = self.formatter.format_survival_strategy(answer, season)

        if 'boss_fight' in intents:
            answer = self.formatter.add_safety_warning(answer, risk_level="high")

        # 4. 交叉引用
        answer = self.enhancer.add_cross_references(answer, analysis.get('entities', {}))

        # 5. 整合 Agent 步骤（如果有）
        if agent_steps:
            answer += f"\n\n---\n🔧 本次搜索使用了 {len(agent_steps)} 个工具"

        return {
            'response': answer,
            'sources': sources,
            'apis_used': apis_used,
            'intent': intents,
            'agent_steps': agent_steps or [],
            'engine': engine,
        }


# ============================================================
# MemoryManager — 会话记忆
# ============================================================

class MemoryManager:
    """跨轮对话记忆：记住用户季节/阶段/Boss/角色/水平"""
    def __init__(self, chat_db):
        self.db = chat_db

    def get_memory(self, session_id: str) -> Dict[str, str]:
        """获取当前会话记忆"""
        mem = {}
        try:
            rows = self.db.get_agent_memory(session_id)
            for row in rows:
                mem[row['key']] = row['value']
        except AttributeError:
            pass  # DB 还没升级
        return mem

    def save_memory(self, session_id: str, memory: Dict[str, str]):
        """保存/更新记忆"""
        try:
            for key, value in memory.items():
                self.db.save_agent_memory(session_id, key, value)
        except AttributeError:
            pass

    def build_memory_context(self, session_id: str) -> str:
        """构建记忆上下文，注入 system prompt"""
        mem = self.get_memory(session_id)
        if not mem:
            return ""

        parts = []
        if 'user_level' in mem:
            parts.append(f"玩家水平: {mem['user_level']}")
        if 'current_season' in mem:
            season = {'春': '春季', '夏': '夏季', '秋': '秋季', '冬': '冬季'}.get(mem['current_season'], mem['current_season'])
            parts.append(f"当前季节: {season}")
        if 'last_boss' in mem:
            parts.append(f"最近提到的Boss: {mem['last_boss']}")
        if 'last_recipe' in mem:
            parts.append(f"最近查过的食谱: {mem['last_recipe']}")
        if 'last_character' in mem:
            parts.append(f"最近讨论的角色: {mem['last_character']}")

        if not parts:
            return ""
        return "\n【🧠 Agent 记忆 — 基于对话历史】\n" + "\n".join(f"  • {p}" for p in parts)


# ============================================================
# Pipeline — 主流水线
# ============================================================

class Pipeline:
    """
    统一流水线：把所有层串起来

    用法:
        pipeline = Pipeline(api_key, knowledge_base, chat_db, fine_tuning_adapter, search_agent)
        result = pipeline.run("冬季怎么生存", session_id="xxx")
        # result = {'response': ..., 'sources': [...], 'apis_used': [...], ...}
    """

    def __init__(self, api_key: str, knowledge_base, chat_db,
                 fine_tuning_adapter, search_agent_wrapper=None):
        self.api_key = api_key
        self.kb = knowledge_base
        self.db = chat_db
        self.ft = fine_tuning_adapter

        # 新架构层级
        self.controller = AgentController()
        self.arbiter = DecisionArbiter()     # 统一仲裁器
        self.tools = ToolExecutor()
        self.memory = MemoryManager(chat_db) # 🧠 记忆管理
        self.rag_stage = RAGStage(knowledge_base)
        self.generator = GenerationStage(api_key)
        self.post = PostProcessor()

        # Agent（可选）
        self.agent = search_agent_wrapper

    def run(self, user_input: str, session_id: str = "default") -> Dict:
        """
        主流程：User Query → Planning → Tool Use → RAG → LoRA → PostProcess → Memory
        """
        t_start = time.time()
        timing = {}  # 各阶段耗时 (ms)

        sources = []
        apis_used = []
        agent_steps = []
        tool_results_list = []
        plan = []
        extra_context = ""
        trace = []

        def add_step(n, title, detail, result=""):
            trace.append({"step": n, "title": title, "detail": detail, "result": result})

        # ===== Layer 1: 语义打分 =====
        t0 = time.time()
        analysis = self.controller.analyze(user_input)
        intents = analysis['intents']
        needs_web = analysis['needs_web_search']
        timing['intent_ms'] = int((time.time() - t0) * 1000)

        add_step(1, "输入解析", f"Query: {user_input[:60]}",
                 f"意图: {', '.join(intents)} | 联网: {'是' if needs_web else '否'} | ⏱ {timing['intent_ms']}ms")

        # 三方独立评分
        t0 = time.time()
        rag_score = self.rag_stage.get_similarity(user_input)
        timing['rag_score_ms'] = int((time.time() - t0) * 1000)
        # 三方评分 — 统一从 RAG 向量相似度派生（同一 embedding 空间）
        # LoRA 训练数据 = 同一份知识库 → LoRA 分 = RAG 分 × 折扣系数
        lora_score = min(1.0, rag_score * 0.85) if self.generator.lora_available else 0.0
        agent_score = 0.85 if needs_web else 0.0

        add_step(2, "语义评分（同源 embedding）",
                 f"RAG={rag_score:.0%} | LoRA=RAG×0.85={lora_score:.0%} | Agent={'0.85' if needs_web else '0'}",
                 f"三方评分同源完成 | ⏱ {timing['rag_score_ms']}ms")

        # ===== Layer 2: DecisionArbiter 统一裁决 =====
        verdict = self.arbiter.decide(rag_score, lora_score, agent_score, intents, needs_web)

        add_step(3, "规则加权",
                 f"规则 boost: {verdict['weights_applied']}",
                 f"加权后: RAG={verdict['boosted']['rag']:.4f} | LoRA={verdict['boosted']['lora']:.4f} | Agent={verdict['boosted']['agent']:.4f}")
        add_step(4, "Softmax 归一化",
                 f"RAG={verdict['final']['rag']:.2%} | LoRA={verdict['final']['lora']:.2%} | Agent={verdict['final']['agent']:.2%}",
                 f"最终选择: {verdict['choice']}")
        add_step(5, "执行", f"调用 {verdict['choice']} 引擎生成回答", "")

        # 🧠 注入记忆上下文
        memory_ctx = self.memory.build_memory_context(session_id)
        if memory_ctx:
            extra_context += "\n" + memory_ctx

        # ===== Planning — 任务拆解 =====
        plan = self.controller._decompose(user_input)
        if len(plan) > 1:
            extra_context += f"\n【📋 Agent 计划】已拆解为 {len(plan)} 个子任务:\n"
            extra_context += "\n".join(f"  {i+1}. {t}" for i, t in enumerate(plan))

        # ===== Tool Use — 游戏数据工具 =====
        t0 = time.time()
        needed_tools = self.tools.detect_tools(user_input)
        if needed_tools:
            extra_context += "\n【🔧 工具调用】\n"
            for tname in needed_tools[:3]:
                tool_result = self.tools.execute(tname, user_input)
                if tool_result['found']:
                    extra_context += f"\n[{tname}] 查询成功:\n{tool_result['text']}\n"
                    tool_results_list.append({"tool": tname, "result": tool_result['text'][:300]})
                    apis_used.append(tname)
                else:
                    extra_context += f"\n[{tname}] {tool_result['text']}\n"
        timing['tools_ms'] = int((time.time() - t0) * 1000)

        # ===== 引擎执行: RAG / Agent =====
        rag_context = ""
        choice = verdict['choice']

        t0 = time.time()
        if choice in ('rag', 'lora'):
            rag_context, sources = self.rag_stage.retrieve(user_input, k=2)
        timing['rag_retrieve_ms'] = int((time.time() - t0) * 1000)

        t0 = time.time()
        if choice == 'agent' and self.agent:
            try:
                agent_result = self.agent.search(user_input)
                agent_steps = agent_result.get('steps', [])
                if agent_result.get('answer') and 'agent' in choice:
                    extra_context += f"\n【🌐 联网搜索结果】\n{agent_result['answer'][:800]}"
                    apis_used.append('web_search')
                if agent_steps:
                    for s in agent_steps:
                        extra_context += f"\n   [{s['tool']}] {s['result_preview'][:200]}"
            except Exception as e:
                extra_context += f"\n⚠️ 联网搜索暂不可用: {e}"
        timing['agent_ms'] = int((time.time() - t0) * 1000)

        # ===== Layer: Generation =====
        intent_context = self._build_intent_context(intents)

        t0 = time.time()
        raw_answer, engine = self.generator.generate(
            query=user_input,
            rag_context=rag_context,
            extra_context=extra_context,
            intent_context=intent_context,
        )
        timing['generation_ms'] = int((time.time() - t0) * 1000)

        add_step(6, "输出融合", f"引擎: {engine} | 长度: {len(raw_answer)} 字 | ⏱ {timing['generation_ms']}ms", "完成")

        # ===== Layer 5: PostProcessor =====
        t0 = time.time()
        result = self.post.process(
            raw_answer=raw_answer,
            analysis=analysis,
            sources=sources,
            apis_used=apis_used,
            agent_steps=agent_steps,
            engine=engine,
        )
        timing['postprocess_ms'] = int((time.time() - t0) * 1000)

        # ===== Layer 6: Memory =====
        new_mem = self.controller.extract_memory(user_input, raw_answer)
        if new_mem:
            self.memory.save_memory(session_id, new_mem)
            result['memory'] = new_mem

        # Agent 完整信息
        result['plan'] = plan if len(plan) > 1 else []
        result['tool_calls'] = tool_results_list
        result['trace'] = trace  # 决策过程

        # ⏱ 耗时打点
        timing['total_ms'] = int((time.time() - t_start) * 1000)
        result['elapsed_ms'] = timing['total_ms']
        result['timing'] = timing

        # ===== 持久化 =====
        self.db.save_conversation(
            session_id=session_id,
            user_msg=user_input,
            bot_msg=result['response'],
            sources=sources,
            api_used=','.join(apis_used) if apis_used else None,
        )

        return result

    def agent_search(self, query: str, session_id: str = "default") -> Dict:
        """专门走 Agent 路径的搜索"""
        if not self.agent:
            return {'answer': '⚠️ Agent 未初始化', 'steps': [],
                    'tool_calls_count': 0, 'elapsed_ms': 0}

        agent_result = self.agent.search(query)
        steps = agent_result.get('steps', [])
        answer = agent_result.get('answer', '')

        # 如果 Agent 返回为空，用 Generation 做 fallback
        if not answer or '⚠️' in answer[:10]:
            answer = self.generator.generate_without_tools(query, steps)

        # 持久化
        self.db.save_agent_search(
            session_id=session_id,
            query=query,
            answer=answer,
            steps=steps,
            tool_calls_count=len(steps),
        )

        return {
            'answer': answer,
            'steps': steps,
            'tool_calls_count': len(steps),
            'elapsed_ms': agent_result.get('elapsed_ms', 0),
        }

    def _build_intent_context(self, intents: List[str]) -> str:
        """根据意图构建领域指令"""
        intent_hints = {
            'survival_strategy': '\n【回答重点】按阶段给出生存策略：时间节点、资源目标、危险预案。',
            'food_recipe': '\n【回答重点】完整配方：材料、属性（饱食/理智/血量）、使用场景、烹饪时间。',
            'building_craft': '\n【回答重点】列出制作步骤、解锁技术、所需材料、建议位置。',
            'seasonal_prep': '\n【回答重点】分阶段：准备期→适应期→过渡期，每个阶段关键任务。',
            'boss_fight': '\n【回答重点】完整Boss攻略：触发条件、弱点、装备建议、战术、避坑要点。',
            'mechanic_explain': '\n【回答重点】深度解释：数值范围、影响因素、相互关系、优化建议。',
            'equipment_guide': '\n【回答重点】对比分析：优缺点、适用场景、性价比、进阶路线。',
        }
        parts = []
        for intent in intents:
            if intent in intent_hints:
                parts.append(intent_hints[intent])
        return '\n'.join(parts)
