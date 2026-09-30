"""
《饥荒 Don't Starve 游戏攻略助手》领域微调适配器
实现领域特定的模型微调、提示词优化和响应格式化
"""

import json
import re
from typing import Dict, List, Optional, Tuple
from datetime import datetime

# ========== 领域特定的词汇和术语库 ==========

GAME_TERMS = {
    "理智值": {"en": "Sanity", "category": "stat", "critical": 25},
    "饥饿值": {"en": "Hunger", "category": "stat", "critical": 0},
    "血量": {"en": "Health", "category": "stat", "critical": 0},
    "体温": {"en": "Temperature", "category": "stat", "critical": None},
    "营火": {"en": "Campfire", "category": "building"},
    "冰箱": {"en": "Icebox", "category": "building"},
    "配方": {"en": "Recipe", "category": "crafting"},
    "生存": {"en": "Survival", "category": "mechanic"},
    "Boss": {"en": "Boss", "category": "enemy"},
    "黑手党": {"en": "Deerclops", "category": "boss", "season": "winter"},
    "蜘蛛女王": {"en": "Spider Queen", "category": "boss", "location": "cave"},
    "树精卫士": {"en": "Treeguard", "category": "boss"},
}

SEASON_MAP = {
    "春": "spring",
    "夏": "summer", 
    "秋": "autumn",
    "冬": "winter",
}

STAT_RANGES = {
    "理智值": {"min": 0, "max": 200, "warning": 50},
    "饥饿值": {"min": 0, "max": 150, "warning": 25},
    "血量": {"min": 0, "max": 150, "warning": 50},
}

# ========== 领域意图识别器 ==========

class DomainIntentRecognizer:
    """识别用户查询的具体游戏领域意图"""
    
    def __init__(self):
        self.intent_patterns = {
            "survival_strategy": [
                r"(怎么|如何|怎样).*(活|生存|度过|熬过)",
                r"(前期|中期|后期).*(怎么|策略)",
                r"(新手|初期|开局).*(指南|教程)",
            ],
            "food_recipe": [
                r"(怎么|怎样).*(做|制作|烹饪).*(食物|菜|肉丸)",
                r"(配方|食谱).*(什么|查询)",
                r"(食物|食材).*(属性|营养|饱食度)",
            ],
            "building_craft": [
                r"(怎么|如何).*(建造|制作|建筑)",
                r"(建筑|设施|工具).*(配方|怎么做)",
                r"(科技树|研发|升级)",
            ],
            "seasonal_prep": [
                r"(春|夏|秋|冬).*(怎么|准备|应对|策略)",
                r"(季节).*(变化|防守|准备)",
                r"(冬天|冬季).*(怎么).*(活|撑|生存)",
            ],
            "boss_fight": [
                r"(黑手党|蜘蛛女王|树精卫士).*(怎么|对付|打)",
                r"(Boss).*(策略|打法|装备)",
            ],
            "mechanic_explain": [
                r"(理智值|饥饿值|血量|温度).*(是什么|怎么|机制)",
                r"(属性|伤害|回复).*(怎么|计算|工作)",
            ],
            "equipment_guide": [
                r"(武器|盔甲|装备).*(推荐|选择|最好)",
                r"(什么|哪个).*(最有用|最强|必备)",
            ],
        }
    
    def recognize(self, user_input: str) -> List[str]:
        """
        识别用户输入的意图
        
        返回:
            list: 匹配的意图列表，按优先级排序
        """
        matched_intents = []
        
        for intent, patterns in self.intent_patterns.items():
            for pattern in patterns:
                if re.search(pattern, user_input, re.IGNORECASE):
                    matched_intents.append(intent)
                    break
        
        return matched_intents if matched_intents else ["general_query"]
    
    def extract_entities(self, user_input: str) -> Dict[str, any]:
        """
        从用户输入中提取游戏实体
        """
        entities = {
            "seasons": [],
            "items": [],
            "characters": [],
            "bosses": [],
            "buildings": [],
            "stats": []
        }
        
        # 提取季节
        for zh_season, en_season in SEASON_MAP.items():
            if zh_season in user_input:
                entities["seasons"].append(en_season)
        
        # 提取游戏术语
        for term, info in GAME_TERMS.items():
            if term in user_input:
                cat = info['category']
                # 映射 category 到 entities 键名
                cat_map = {
                    'stat': 'stats',
                    'building': 'buildings',
                    'boss': 'bosses',
                    'enemy': 'bosses',
                    'crafting': 'items',
                    'mechanic': 'stats',
                }
                key = cat_map.get(cat, f"{cat}s")
                if key not in entities:
                    entities[key] = []
                entities[key].append(term)
        
        return entities


# ========== 领域提示词优化器 ==========

class DomainPromptOptimizer:
    """根据意图和实体优化系统提示词"""
    
    def __init__(self):
        self.base_system_prompt = """你是一位资深的《饥荒 Don't Starve》游戏攻略专家，具有以下特点：

【身份定位】
- 多年饥荒老玩家，对游戏机制透彻理解
- 精通所有人物档案、生物特性、食物属性、建筑优先级
- 熟悉四季变化规律、世界事件、特殊模式玩法

【回答原则】
1. 【严格遵循知识库】：优先基于提供的参考知识回答，这些是深度玩家总结
2. 【精确步骤】：给出的策略必须包含具体操作步骤，不能模糊
3. 【安全提示】：涉及生存策略时，务必强调哪些操作容易翻车
4. 【多模式考虑】：回答时区分 Don't Starve 和 Don't Starve Together (DST) 的差异
5. 【季节感知】：根据玩家所在季节给出不同建议

【禁止事项】
- 禁止编造游戏机制
- 禁止给出通用建议，必须具体到操作步骤
- 如果问题超出饥荒范围，礼貌拒绝

【说话风格】
- 用亲切但权威的语气，类似"游戏大佬的建议"
- 适当使用游戏术语和玩家俚语（如"掉san"、"出门翻车"等）
"""
        
        self.intent_context = {
            "survival_strategy": "\n【回答重点】请提供分阶段的生存策略，包括：时间节点、资源目标、危险预案、应急方案。",
            "food_recipe": "\n【回答重点】提供完整的配方信息：所需材料、制作时间、营养属性、使用场景、推荐时机。",
            "building_craft": "\n【回答重点】列出制作步骤：需要解锁的技术、所需材料、建议位置、维护需求。",
            "seasonal_prep": "\n【回答重点】按阶段讲解季节准备：准备期、适应期、过渡期，每个阶段的关键任务。",
            "boss_fight": "\n【回答重点】提供完整的Boss战指南：触发条件、弱点分析、装备建议、战术安排、避坑要点。",
            "mechanic_explain": "\n【回答重点】深度解释游戏机制：数值范围、影响因素、相互关系、优化建议。",
            "equipment_guide": "\n【回答重点】对比分析：不同装备的优缺点、适用场景、性价比、进阶路线。",
        }
    
    def optimize_prompt(self, user_input: str, intents: List[str], 
                       entities: Dict, context: Optional[str] = None) -> str:
        """
        根据意图和实体优化系统提示词
        """
        prompt = self.base_system_prompt
        
        # 添加意图特定的上下文
        for intent in intents:
            if intent in self.intent_context:
                prompt += self.intent_context[intent]
        
        # 添加实体上下文
        if entities["seasons"]:
            prompt += f"\n【季节背景】玩家提到的季节: {', '.join(entities['seasons'])}"
        
        if entities["stats"]:
            prompt += f"\n【属性关注】玩家关注的属性: {', '.join(entities['stats'])}"
        
        # 添加自定义上下文
        if context:
            prompt += f"\n【补充信息】{context}"
        
        return prompt


# ========== 响应格式化器 ==========

class ResponseFormatter:
    """格式化和增强模型的响应"""
    
    @staticmethod
    def format_survival_strategy(content: str, season: Optional[str] = None) -> str:
        """
        格式化生存策略回答
        """
        formatted = f"""
【生存策略指南】{f"({season}季节)" if season else ""}

{content}

【快速检查清单】
□ 已确认当前季节及温度
□ 已准备必要的防护装备  
□ 已规划日常任务时间表
□ 已确保食物和燃料充足
□ 已评估当前危险等级

【常见翻车场景】
⚠️ 不要在陌生区域停留过久
⚠️ 不要在夜间远离营火
⚠️ 不要穿着破损装备去探险
⚠️ 不要忽视理智值预警信号
"""
        return formatted.strip()
    
    @staticmethod
    def format_recipe(recipe_data: Dict) -> str:
        """格式化食物配方"""
        formatted = f"""
【{recipe_data.get('name', '菜肴')}】

📋 配方:
{recipe_data.get('ingredients', '待补充')}

⏱️ 制作时间: {recipe_data.get('cooking_time', '未知')}秒

📊 属性对比:
• 饱食度: {recipe_data.get('hunger', '?')}
• 理智值: {recipe_data.get('sanity', '?')}  
• 生命值: {recipe_data.get('health', '?')}

🎯 使用场景: {recipe_data.get('use_case', '通用食物')}

💡 建议: {recipe_data.get('tips', '根据情况选择')}
"""
        return formatted.strip()
    
    @staticmethod
    def format_boss_guide(boss_name: str, content: str) -> str:
        """格式化Boss战指南"""
        formatted = f"""
【{boss_name}攻略】

{content}

【装备推荐】
武器: 暗影剑 / 蜘蛛剑 / 战斧
防具: 皮甲 / 蜘蛛甲
食物: 腊肉 / 肉丸（充足储备）

【战前检查】
✓ 确保血量满状态
✓ 理智值不低于75%
✓ 食物储备充足（200+）
✓ 装备耐久度满
✓ 战斗区域没有多余敌人

【应急方案】
逃生方向标记 → 建立安全屋 → 准备备用武器
"""
        return formatted.strip()
    
    @staticmethod
    def add_safety_warning(response: str, risk_level: str = "medium") -> str:
        """
        添加风险警告
        
        参数:
            risk_level: "low" | "medium" | "high" | "critical"
        """
        warnings = {
            "low": "✅ 低风险操作",
            "medium": "⚠️ 中等风险，需要准备",
            "high": "⚠⚠️ 高风险，新手不推荐",
            "critical": "🚨 极高风险！多准备几次，很可能翻车！"
        }
        
        return f"{warnings.get(risk_level, '⚠️ 存在风险')}\n\n{response}"


# ========== 领域知识增强器 ==========

class DomainKnowledgeEnhancer:
    """增强和验证响应中的领域知识"""
    
    def __init__(self):
        self.stat_ranges = STAT_RANGES
        self.game_terms = GAME_TERMS
    
    def validate_stat_values(self, response: str) -> str:
        """
        验证响应中的属性数值是否合理
        """
        for stat, ranges in self.stat_ranges.items():
            # 查找响应中的数值提及
            pattern = rf"{stat}.*?(\d+)"
            matches = re.finditer(pattern, response)
            
            for match in matches:
                value = int(match.group(1))
                if not (ranges["min"] <= value <= ranges["max"]):
                    # 标记不合理的数值
                    response = response.replace(
                        match.group(0),
                        f"[⚠️ 值需验证: {match.group(0)}]"
                    )
        
        return response
    
    def standardize_terminology(self, response: str) -> str:
        """
        标准化响应中的游戏术语
        """
        replacements = {
            "掉San": "理智值下降",
            "翻车": "死亡/失败",
            "打黑科技": "使用高级技巧",
            "出门": "离开基地",
            "肝": "长时间工作/采集",
        }
        
        for slang, standard in replacements.items():
            response = response.replace(slang, f"{slang}({standard})")
        
        return response
    
    def add_cross_references(self, response: str, entities: Dict) -> str:
        """
        添加交叉引用，帮助玩家快速查阅相关内容
        """
        if entities["seasons"]:
            response += f"\n\n📚 相关阅读: 查看 {', '.join(entities['seasons'])} 的完整攻略"
        
        if entities["bosses"]:
            response += f"\n📚 相关阅读: 更多Boss攻略"
        
        if entities["buildings"]:
            response += f"\n📚 相关阅读: {', '.join(entities['buildings'])} 的用途与优化"
        
        return response


# ========== 完整的微调适配器 ==========

class FineTuningAdapter:
    """整合所有领域适配功能的主适配器"""
    
    def __init__(self):
        self.intent_recognizer = DomainIntentRecognizer()
        self.prompt_optimizer = DomainPromptOptimizer()
        self.response_formatter = ResponseFormatter()
        self.knowledge_enhancer = DomainKnowledgeEnhancer()
    
    def prepare_request(self, user_input: str, 
                       context: Optional[str] = None) -> Tuple[str, Dict]:
        """
        为API调用准备请求（包括优化的系统提示词）
        
        返回:
            (system_prompt, metadata)
        """
        # 1. 识别意图和实体
        intents = self.intent_recognizer.recognize(user_input)
        entities = self.intent_recognizer.extract_entities(user_input)
        
        # 2. 优化系统提示词
        system_prompt = self.prompt_optimizer.optimize_prompt(
            user_input, intents, entities, context
        )
        
        # 3. 生成元数据
        metadata = {
            "intents": intents,
            "entities": entities,
            "timestamp": datetime.now().isoformat(),
            "user_input": user_input
        }
        
        return system_prompt, metadata
    
    def enhance_response(self, response: str, metadata: Dict) -> str:
        """
        增强和格式化模型响应
        """
        # 1. 验证数值
        response = self.knowledge_enhancer.validate_stat_values(response)
        
        # 2. 标准化术语
        response = self.knowledge_enhancer.standardize_terminology(response)
        
        # 3. 根据意图格式化
        intents = metadata.get("intents", [])
        if "survival_strategy" in intents:
            season = metadata.get("entities", {}).get("seasons", [None])[0]
            response = self.response_formatter.format_survival_strategy(
                response, season
            )
        
        if "boss_fight" in intents:
            response = self.response_formatter.add_safety_warning(
                response, risk_level="high"
            )
        
        # 4. 添加交叉引用
        response = self.knowledge_enhancer.add_cross_references(
            response, metadata.get("entities", {})
        )
        
        return response
    
    def process_query(self, user_input: str, model_response: str,
                     context: Optional[str] = None) -> Dict:
        """
        完整处理一条查询：优化输入 → 模型调用 → 增强输出
        """
        # 准备请求
        system_prompt, metadata = self.prepare_request(user_input, context)
        
        # 增强响应
        enhanced_response = self.enhance_response(model_response, metadata)
        
        return {
            "original_input": user_input,
            "system_prompt": system_prompt,
            "original_response": model_response,
            "enhanced_response": enhanced_response,
            "metadata": metadata
        }


# ========== 测试函数 ==========

def test_adapter():
    """测试微调适配器"""
    adapter = FineTuningAdapter()
    
    test_queries = [
        "冬季怎么生存？",
        "肉丸怎么做？",
        "黑手党怎么对付？",
        "理智值是什么？",
        "需要什么装备？",
    ]
    
    for query in test_queries:
        print(f"\n测试查询: {query}")
        print("-" * 50)
        
        system_prompt, metadata = adapter.prepare_request(query)
        print(f"识别意图: {metadata['intents']}")
        print(f"提取实体: {metadata['entities']}")
        print(f"系统提示词长度: {len(system_prompt)} 字符")


if __name__ == "__main__":
    test_adapter()
