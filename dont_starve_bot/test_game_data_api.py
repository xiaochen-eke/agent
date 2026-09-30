#!/usr/bin/env python3
"""
游戏数据 API 完整演示和测试脚本
展示如何使用自定义的游戏数据 API
"""

from game_data_api_client import GameDataAPIClient
import json
import sys

# 颜色输出
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_header(text):
    print(f"\n{Colors.BOLD}{Colors.HEADER}{'=' * 60}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.HEADER}{text.center(60)}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.HEADER}{'=' * 60}{Colors.ENDC}\n")

def print_success(text):
    print(f"{Colors.OKGREEN}✅ {text}{Colors.ENDC}")

def print_warning(text):
    print(f"{Colors.WARNING}⚠️  {text}{Colors.ENDC}")

def print_error(text):
    print(f"{Colors.FAIL}❌ {text}{Colors.ENDC}")

def print_info(text):
    print(f"{Colors.OKCYAN}ℹ️  {text}{Colors.ENDC}")

def print_json(data, indent=2):
    print(json.dumps(data, ensure_ascii=False, indent=indent))

def demo_1_server_check(client):
    """演示 1: 检查服务器状态"""
    print_header("演示 1: 服务器状态检查")
    
    print("正在检查 API 服务器...")
    if client.health_check():
        print_success("API 服务器在线")
        print("服务器地址: http://localhost:5001")
        print("API 前缀: /api/game-data")
    else:
        print_error("API 服务器离线")
        print_warning("请确保已启动 game_data_api.py")
        return False
    
    return True

def demo_2_items(client):
    """演示 2: 物品信息查询"""
    print_header("演示 2: 物品信息查询")
    
    # 获取所有物品列表
    print("获取所有物品...")
    items_list = client.get_all_items()
    if items_list.get('status') == 'success':
        print_success(f"成功获取 {items_list['count']} 个物品")
        print(f"物品列表: {', '.join(items_list['items'][:5])}...")
    else:
        print_error("获取物品列表失败")
        return False
    
    # 获取特定物品详情
    print("\n查询特定物品: 木头")
    wood = client.get_item('木头')
    if wood.get('status') == 'success':
        print_success("成功获取物品详情")
        data = wood['data']
        print(f"  名称: {data['name']}")
        print(f"  描述: {data['description']}")
        print(f"  稀有度: {data['rarity']}")
        print(f"  分类: {data['category']}")
        print(f"  用途: {', '.join(data['uses'])}")
        print(f"  可堆叠: {data['stackable']}")
        print(f"  重量: {data['weight']}")
    else:
        print_error("获取物品详情失败")
        return False
    
    return True

def demo_3_creatures(client):
    """演示 3: 生物信息查询"""
    print_header("演示 3: 生物信息查询")
    
    # 获取所有生物
    print("获取所有生物...")
    creatures_list = client.get_all_creatures()
    if creatures_list.get('status') == 'success':
        print_success(f"成功获取 {creatures_list['count']} 个生物")
        print(f"生物列表: {', '.join(creatures_list['creatures'])}")
    else:
        print_error("获取生物列表失败")
        return False
    
    # 获取蜘蛛信息
    print("\n查询生物: 蜘蛛")
    spider = client.get_creature('蜘蛛')
    if spider.get('status') == 'success':
        print_success("成功获取生物详情")
        data = spider['data']
        print(f"  名称: {data['name']}")
        print(f"  描述: {data['description']}")
        print(f"  生命值: {data['health']}")
        print(f"  伤害: {data['damage']}")
        print(f"  速度: {data['speed']}")
        print(f"  危险等级: {data['danger_level']}/5")
        print(f"  行为: {data['behavior']}")
        print(f"  掉落物: {data['drops']}")
    else:
        print_error("获取生物详情失败")
        return False
    
    # 获取蜘蛛女王（强敌）
    print("\n查询强敌: 蜘蛛女王")
    spider_queen = client.get_creature('蜘蛛女王')
    if spider_queen.get('status') == 'success':
        print_success("成功获取强敌详情")
        data = spider_queen['data']
        print(f"  名称: {data['name']}")
        print(f"  生命值: {data['health']} (普通蜘蛛的 {data['health']//10}倍!)")
        print(f"  伤害: {data['damage']} (非常危险!)")
        print(f"  危险等级: {data['danger_level']}/5 ⚠️")
    else:
        print_error("获取蜘蛛女王详情失败")
        return False
    
    return True

def demo_4_buildings(client):
    """演示 4: 建筑信息查询"""
    print_header("演示 4: 建筑信息查询")
    
    # 获取所有建筑
    print("获取所有建筑...")
    buildings_list = client.get_all_buildings()
    if buildings_list.get('status') == 'success':
        print_success(f"成功获取 {buildings_list['count']} 个建筑")
        print(f"建筑列表: {', '.join(buildings_list['buildings'])}")
    else:
        print_error("获取建筑列表失败")
        return False
    
    # 获取营火信息
    print("\n查询建筑: 营火")
    campfire = client.get_building('营火')
    if campfire.get('status') == 'success':
        print_success("成功获取建筑详情")
        data = campfire['data']
        print(f"  名称: {data['name']}")
        print(f"  描述: {data['description']}")
        print(f"  优先级: {data['priority']} (最关键!)")
        print(f"  耐久度: {data['durability']}")
        print(f"  制作时间: {data['crafting_time']} 秒")
        print(f"  用途: {', '.join(data['uses'])}")
        print(f"  属性:")
        for key, value in data['stats'].items():
            print(f"    - {key}: {value}")
    else:
        print_error("获取建筑详情失败")
        return False
    
    # 获取建筑制作成本
    print("\n查询建筑制作成本: 烹饪锅")
    cost = client.get_crafting_cost('烹饪锅')
    if cost.get('status') == 'success':
        print_success("成功获取制作成本")
        print(f"  建筑: {cost['building_name']}")
        print(f"  成本: {cost['cost']}")
        print(f"  制作时间: {cost['crafting_time']} 秒")
    else:
        print_error("获取制作成本失败")
        return False
    
    return True

def demo_5_foods(client):
    """演示 5: 食物信息查询"""
    print_header("演示 5: 食物信息查询")
    
    # 获取所有食物
    print("获取所有食物...")
    foods_list = client.get_all_foods()
    if foods_list.get('status') == 'success':
        print_success(f"成功获取 {foods_list['count']} 种食物")
        print(f"食物列表: {', '.join(foods_list['foods'])}")
    else:
        print_error("获取食物列表失败")
        return False
    
    # 获取蛋糕信息（最重要的食物）
    print("\n查询食物: 蛋糕 (最强食物)")
    cake = client.get_food('蛋糕')
    if cake.get('status') == 'success':
        print_success("成功获取食物详情")
        data = cake['data']
        print(f"  名称: {data['name']}")
        print(f"  描述: {data['description']}")
        print(f"  类型: {data['type']}")
        print(f"  保质期: {data['spoil_time']} 天")
        print(f"  营养值:")
        for nutrient, value in data['nutrition'].items():
            symbol = "🍗" if nutrient == "hunger" else "❤️" if nutrient == "health" else "🧠"
            print(f"    {symbol} {nutrient}: {value}")
    else:
        print_error("获取食物详情失败")
        return False
    
    # 获取食物配方
    print("\n查询食物配方: 蛋糕")
    recipe = client.get_recipe('蛋糕')
    if recipe.get('status') == 'success':
        print_success("成功获取配方")
        print(f"  食物: {recipe['food_name']}")
        if 'recipe' in recipe:
            print(f"  所需材料:")
            for item, amount in recipe['recipe'].items():
                print(f"    - {item}: {amount} 个")
    else:
        print_error("获取配方失败")
        return False
    
    return True

def demo_6_seasons(client):
    """演示 6: 季节信息查询"""
    print_header("演示 6: 季节信息查询")
    
    # 获取所有季节
    print("获取所有季节...")
    seasons_list = client.get_all_seasons()
    if seasons_list.get('status') == 'success':
        print_success(f"成功获取 {seasons_list['count']} 个季节")
        print(f"季节列表: {', '.join(seasons_list['seasons'])}")
    else:
        print_error("获取季节列表失败")
        return False
    
    # 获取冬季信息
    print("\n查询季节: 冬季 (最具挑战)")
    winter = client.get_season('冬')
    if winter.get('status') == 'success':
        print_success("成功获取季节详情")
        data = winter['data']
        print(f"  季节: {data['name']}")
        print(f"  描述: {data['description']}")
        print(f"  持续时间: {data['duration']} 天")
        print(f"  温度: {data['temperature']}°C")
        print(f"  特征:")
        for feature in data['features']:
            print(f"    - {feature}")
        print(f"  挑战:")
        for challenge in data['challenges']:
            print(f"    ⚠️ {challenge}")
    else:
        print_error("获取季节详情失败")
        return False
    
    return True

def demo_7_search(client):
    """演示 7: 全文搜索"""
    print_header("演示 7: 全文搜索功能")
    
    # 搜索蜘蛛
    print("搜索关键词: '蜘蛛'")
    results = client.search('蜘蛛', category='all')
    if results.get('status') == 'success':
        print_success("搜索成功")
        search_results = results.get('results', {})
        if search_results:
            for category, matches in search_results.items():
                print(f"\n  {category}:")
                for name in matches.keys():
                    print(f"    - {name}")
        else:
            print_warning("没有搜索结果")
    else:
        print_error("搜索失败")
        return False
    
    return True

def demo_8_tips(client):
    """演示 8: 获取游戏提示"""
    print_header("演示 8: 随机游戏提示")
    
    print("获取随机游戏提示...")
    tips = client.get_tips()
    if tips.get('status') == 'success':
        print_success("成功获取提示")
        print(f"共有 {tips['total_available_tips']} 条提示，当前显示的是:")
        for i, tip in enumerate(tips['tips'], 1):
            print(f"\n  💡 提示 {i}:")
            print(f"     {tip}")
    else:
        print_error("获取提示失败")
        return False
    
    return True

def demo_9_stats(client):
    """演示 9: 数据库统计"""
    print_header("演示 9: 数据库统计信息")
    
    print("获取数据库统计...")
    stats = client.get_database_stats()
    if stats.get('status') == 'success':
        print_success("成功获取统计信息")
        data = stats['statistics']
        print(f"\n  数据库统计:")
        print(f"    🎮 物品: {data['items']} 个")
        print(f"    🐛 生物: {data['creatures']} 个")
        print(f"    🏠 建筑: {data['buildings']} 个")
        print(f"    🍖 食物: {data['foods']} 个")
        print(f"    🌍 季节: {data['seasons']} 个")
        print(f"    ━━━━━━━━━━")
        print(f"    📊 总计: {data['total_entries']} 条记录")
    else:
        print_error("获取统计失败")
        return False
    
    return True

def main():
    """主程序"""
    print_header("🎮 饥荒游戏数据 API - 完整演示")
    
    # 创建客户端
    print("正在初始化 API 客户端...")
    client = GameDataAPIClient()
    print_success("客户端初始化完成\n")
    
    # 演示列表
    demos = [
        ("服务器状态检查", demo_1_server_check),
        ("物品信息查询", demo_2_items),
        ("生物信息查询", demo_3_creatures),
        ("建筑信息查询", demo_4_buildings),
        ("食物信息查询", demo_5_foods),
        ("季节信息查询", demo_6_seasons),
        ("全文搜索功能", demo_7_search),
        ("随机游戏提示", demo_8_tips),
        ("数据库统计", demo_9_stats),
    ]
    
    # 执行所有演示
    success_count = 0
    for i, (name, demo_func) in enumerate(demos, 1):
        try:
            if demo_func(client):
                success_count += 1
            else:
                print_error(f"演示 {i} 失败")
        except Exception as e:
            print_error(f"演示 {i} 出错: {str(e)}")
    
    # 总结
    print_header(f"演示完成 ({success_count}/{len(demos)} 成功)")
    
    if success_count == len(demos):
        print_success("所有演示都成功完成！")
        print("\n" + "=" * 60)
        print("✨ API 功能完整，可以开始使用！")
        print("=" * 60 + "\n")
    else:
        print_warning(f"{len(demos) - success_count} 个演示失败")
        print("请检查 API 服务器是否正在运行。\n")

if __name__ == '__main__':
    main()