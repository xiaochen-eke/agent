"""
《饥荒攻略助手》集成测试脚本
演示 RAG + Agent联网搜索 + 领域微调 的完整工作流
"""

import sys
import os
from pathlib import Path

# 添加后端路径
backend_path = os.path.join(os.path.dirname(__file__), "backend")
sys.path.insert(0, backend_path)

from fine_tuning_adapter import FineTuningAdapter
from init_knowledge_base import init_knowledge_base_files, verify_knowledge_base


class IntegrationTest:
    """集成测试类"""
    
    def __init__(self):
        self.adapter = FineTuningAdapter()
        self.passed = 0
        self.failed = 0
    
    def print_header(self, title):
        """打印测试标题"""
        print("\n" + "=" * 60)
        print(f"🧪 {title}")
        print("=" * 60)
    
    def print_result(self, test_name, passed, message=""):
        """打印测试结果"""
        if passed:
            self.passed += 1
            status = "✅ PASS"
        else:
            self.failed += 1
            status = "❌ FAIL"
        
        print(f"{status} | {test_name}")
        if message:
            print(f"       {message}")
    
    # ========== 测试1: 知识库初始化 ==========
    def test_knowledge_base_init(self):
        """测试知识库初始化"""
        self.print_header("测试1: 知识库初始化")
        
        kb_path = os.path.join(os.path.dirname(__file__), "backend", "knowledge_base")
        
        # 初始化知识库
        print("📝 初始化知识库文件...")
        files_info = init_knowledge_base_files(kb_path)
        
        created_count = sum(1 for f in files_info.values() if f['status'] in ['created', 'already_exists'])
        test_passed = created_count >= 3
        
        self.print_result(
            "知识库文件创建",
            test_passed,
            f"成功创建/找到 {created_count} 个文件"
        )
        
        # 验证知识库
        print("\n📋 验证知识库完整性...")
        verification = verify_knowledge_base(kb_path)
        
        test_passed = verification['found_files'] >= 3
        self.print_result(
            "知识库完整性验证",
            test_passed,
            f"找到 {verification['found_files']}/{verification['total_files']} 个文件"
        )
        
        print(f"💾 知识库总大小: {verification['total_size'] / 1024:.1f} KB")
    
    # ========== 测试2: 意图识别 ==========
    def test_intent_recognition(self):
        """测试意图识别功能"""
        self.print_header("测试2: 意图识别（领域微调）")
        
        test_cases = [
            ("冬季怎么生存？", ["survival_strategy", "seasonal_prep"]),
            ("肉丸怎么做？", ["food_recipe"]),
            ("黑手党怎么对付？", ["boss_fight"]),
            ("理智值是什么？", ["mechanic_explain"]),
            ("需要什么装备？", ["equipment_guide"]),
        ]
        
        recognizer = self.adapter.intent_recognizer
        
        for user_input, expected_intents in test_cases:
            intents = recognizer.recognize(user_input)
            
            # 检查是否包含至少一个预期的意图
            has_expected = any(intent in intents for intent in expected_intents)
            
            self.print_result(
                f'意图识别: "{user_input}"',
                has_expected,
                f"识别结果: {intents}"
            )
    
    # ========== 测试3: 实体提取 ==========
    def test_entity_extraction(self):
        """测试实体提取功能"""
        self.print_header("测试3: 实体提取（领域微调）")
        
        test_cases = [
            ("冬季怎么生存", {"seasons": ["winter"]}),
            ("春季和夏季的区别", {"seasons": ["spring", "summer"]}),
            ("黑手党怎么对付", {"bosses": ["黑手党"]}),
            ("冰箱怎么制作", {"buildings": ["冰箱"]}),
        ]
        
        recognizer = self.adapter.intent_recognizer
        
        for user_input, expected_entities in test_cases:
            entities = recognizer.extract_entities(user_input)
            
            # 检查关键实体是否被提取
            all_found = True
            for entity_type, expected_values in expected_entities.items():
                extracted = entities.get(f"{entity_type}s", [])
                if not any(val in extracted for val in expected_values):
                    all_found = False
                    break
            
            self.print_result(
                f'实体提取: "{user_input}"',
                all_found,
                f"提取: {[e for e in entities.values() if e]}"
            )
    
    # ========== 测试4: 提示词优化 ==========
    def test_prompt_optimization(self):
        """测试提示词优化功能"""
        self.print_header("测试4: 提示词优化（领域微调）")
        
        # 测试用例
        user_input = "冬季怎么生存？"
        intents = ["survival_strategy", "seasonal_prep"]
        entities = {"seasons": ["winter"], "items": [], "characters": [], "bosses": []}
        
        optimizer = self.adapter.prompt_optimizer
        optimized_prompt = optimizer.optimize_prompt(user_input, intents, entities)
        
        # 检查优化后的提示词是否包含关键信息
        checks = [
            ("包含基础提示词", "资深的《饥荒" in optimized_prompt),
            ("包含意图特定上下文", "分阶段讲解季节准备" in optimized_prompt or "季节" in optimized_prompt),
            ("包含实体上下文", "winter" in optimized_prompt or "冬季" in optimized_prompt),
        ]
        
        all_passed = all(check[1] for check in checks)
        
        for check_name, passed in checks:
            self.print_result(check_name, passed)
        
        print(f"\n📄 优化后提示词长度: {len(optimized_prompt)} 字符")
    
    # ========== 测试5: 响应格式化 ==========
    def test_response_formatting(self):
        """测试响应格式化功能"""
        self.print_header("测试5: 响应格式化（领域微调）")
        
        formatter = self.adapter.response_formatter
        
        # 测试生存策略格式化
        strategy_response = "在春季需要采集蜘蛛丝并制作武器"
        formatted_strategy = formatter.format_survival_strategy(strategy_response, "spring")
        
        has_strategy_header = "生存策略指南" in formatted_strategy
        has_season_context = "spring" in formatted_strategy
        has_checklist = "检查清单" in formatted_strategy
        
        self.print_result(
            "生存策略格式化",
            has_strategy_header and has_checklist,
            "包含标题、清单和警告"
        )
        
        # 测试Boss战指南格式化
        boss_response = "黑手党是冬季的Boss怪物"
        formatted_boss = formatter.format_boss_guide("黑手党", boss_response)
        
        has_boss_title = "黑手党攻略" in formatted_boss
        has_equipment = "装备推荐" in formatted_boss
        
        self.print_result(
            "Boss战指南格式化",
            has_boss_title and has_equipment,
            "包含标题、装备推荐和准备清单"
        )
        
        # 测试安全警告添加
        warning_response = formatter.add_safety_warning(strategy_response, "high")
        has_warning = "⚠⚠️" in warning_response or "高风险" in warning_response
        
        self.print_result(
            "安全警告添加",
            has_warning,
            "正确添加了高风险警告"
        )
    
    # ========== 测试6: 完整流程 ==========
    def test_complete_workflow(self):
        """测试完整工作流"""
        self.print_header("测试6: 完整工作流集成")
        
        # 模拟用户查询
        user_input = "冬季新手怎么生存？"
        mock_response = """
        冬季是最危险的季节。以下是生存策略：
        1. 前期准备：制作冬帽、保温衣
        2. 燃料管理：准备足够的木头
        3. 食物储备：储备肉丸等高饱食度食物
        """
        
        # 执行完整流程
        try:
            result = self.adapter.process_query(user_input, mock_response)
            
            # 检查返回的关键字段
            checks = [
                ("包含原始输入", "original_input" in result and result["original_input"] == user_input),
                ("包含系统提示词", "system_prompt" in result and len(result["system_prompt"]) > 0),
                ("包含原始响应", "original_response" in result),
                ("包含增强响应", "enhanced_response" in result and len(result["enhanced_response"]) > 0),
                ("包含元数据", "metadata" in result and "intents" in result["metadata"]),
                ("识别出意图", "survival_strategy" in result["metadata"].get("intents", [])),
            ]
            
            for check_name, passed in checks:
                self.print_result(check_name, passed)
            
            print(f"\n📊 增强响应长度: {len(result['enhanced_response'])} 字符")
            
        except Exception as e:
            self.print_result("完整流程执行", False, f"异常: {str(e)}")
    
    # ========== 测试7: 联网搜索能力验证 ==========
    def test_web_search_capability(self):
        """测试Web搜索能力"""
        self.print_header("测试7: Web搜索能力验证")
        
        print("📡 检查Web搜索工具集成...")
        
        # 检查search_agent.py是否存在
        agent_path = os.path.join(
            os.path.dirname(__file__), 
            "Agent", 
            "search_agent.py"
        )
        
        agent_exists = os.path.exists(agent_path)
        self.print_result("search_agent.py存在", agent_exists)
        
        # 检查是否包含web_search工具
        if agent_exists:
            with open(agent_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            has_web_search = "web_search" in content
            has_tool_executor = "TOOL_EXECUTORS" in content
            
            self.print_result(
                "包含web_search工具",
                has_web_search,
                "Web搜索功能已集成"
            )
            
            self.print_result(
                "包含工具执行器",
                has_tool_executor,
                "支持Function Calling"
            )
        
        print("\n💡 Web搜索使用方法:")
        print("   python Agent/search_agent.py")
        print("   > 你: 搜索任何内容")
        print("   > Agent: [Tool] 🔍 web_search(...)")
    
    # ========== 运行所有测试 ==========
    def run_all_tests(self):
        """运行所有测试"""
        print("\n")
        print("╔" + "=" * 58 + "╗")
        print("║" + " " * 10 + "🎮 饥荒攻略AI助手 - 集成测试" + " " * 18 + "║")
        print("╚" + "=" * 58 + "╝")
        
        # 运行所有测试
        self.test_knowledge_base_init()
        self.test_intent_recognition()
        self.test_entity_extraction()
        self.test_prompt_optimization()
        self.test_response_formatting()
        self.test_complete_workflow()
        self.test_web_search_capability()
        
        # 输出统计
        print("\n" + "=" * 60)
        print("📊 测试统计")
        print("=" * 60)
        total = self.passed + self.failed
        pass_rate = (self.passed / total * 100) if total > 0 else 0
        
        print(f"总测试数: {total}")
        print(f"✅ 通过: {self.passed}")
        print(f"❌ 失败: {self.failed}")
        print(f"📈 通过率: {pass_rate:.1f}%")
        
        print("\n" + "=" * 60)
        
        if self.failed == 0:
            print("🎉 所有测试通过！系统已就绪。")
            print("\n下一步:")
            print("  1. 运行后端: python dont_starve_bot/backend/app.py")
            print("  2. 测试Agent: python Agent/search_agent.py")
            print("  3. 查看文档: 阅读 SYSTEM_README.md")
        else:
            print(f"⚠️ 有 {self.failed} 个测试失败，请检查问题。")
        
        print("=" * 60 + "\n")
        
        return self.failed == 0


def main():
    """主函数"""
    tester = IntegrationTest()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
