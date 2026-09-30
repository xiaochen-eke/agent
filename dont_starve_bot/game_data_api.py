"""
《饥荒游戏数据 API 服务器》
这是一个独立的 API 服务，提供游戏数据、物品信息、生物数据等
可以与主聊天机器人分离部署或在同一服务器运行

用途：
1. 作为独立的微服务运行在 localhost:5001
2. 提供游戏数据查询接口
3. 支持物品、生物、建筑、食物等多种数据类型
"""


import sys

# 修复 Windows 控制台 GBK 编码问题
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass


from flask import Flask
from flask_cors import CORS  # 1. 导入插件

app = Flask(__name__)
CORS(app)  # 2. 允许所有来源访问这个 API


import requests
from typing import Dict, List, Optional, Any
from functools import lru_cache
import json


from flask import Flask, request, jsonify
from datetime import datetime
import json

# 创建 Flask 应用
api_app = Flask(__name__)

# ========== 游戏数据库 ==========
# 这些数据模拟了游戏中的真实数据

GAME_DATABASE = {
    # ===== 物品数据库 =====
    "items": {
        "木头": {
            "id": "wood",
            "name": "木头",
            "description": "从树上砍下来的木头，是基础资源",
            "rarity": "common",
            "category": "resource",
            "uses": ["建筑", "燃料", "工具制作"],
            "durability": None,
            "stackable": True,
            "stack_size": 40,
            "weight": 0.5
        },
        "石头": {
            "id": "stone",
            "name": "石头",
            "description": "坚硬的石头，用于建筑和工具",
            "rarity": "common",
            "category": "resource",
            "uses": ["建筑", "工具制作"],
            "durability": None,
            "stackable": True,
            "stack_size": 40,
            "weight": 1.0
        },
        "燧石": {
            "id": "flint",
            "name": "燧石",
            "description": "尖锐的燧石，用于制作工具和生火",
            "rarity": "common",
            "category": "resource",
            "uses": ["工具制作", "火焰", "武器"],
            "durability": None,
            "stackable": True,
            "stack_size": 40,
            "weight": 0.3
        },
        "草": {
            "id": "grass",
            "name": "草",
            "description": "普通的草，可用于制作绳子和其他物品",
            "rarity": "common",
            "category": "resource",
            "uses": ["绳子制作", "食物"],
            "durability": None,
            "stackable": True,
            "stack_size": 40,
            "weight": 0.1
        },
        "蜘蛛丝": {
            "id": "spider_silk",
            "name": "蜘蛛丝",
            "description": "坚韧的蜘蛛丝，用于制作装备和武器",
            "rarity": "uncommon",
            "category": "resource",
            "uses": ["衣服制作", "武器", "工具"],
            "durability": None,
            "stackable": True,
            "stack_size": 40,
            "weight": 0.2
        },
        "蜂蜜": {
            "id": "honey",
            "name": "蜂蜜",
            "description": "甜美的蜂蜜，是高价值食物",
            "rarity": "uncommon",
            "category": "food",
            "uses": ["食物", "蛋糕制作", "治疗"],
            "durability": None,
            "stackable": True,
            "stack_size": 40,
            "weight": 0.3,
            "nutrition": {
                "hunger": 40,
                "health": 0,
                "sanity": 5
            }
        },
        "营火": {
            "id": "campfire",
            "name": "营火",
            "description": "提供光照和温暖的生活必需品",
            "rarity": "essential",
            "category": "building",
            "uses": ["光照", "温暖", "烹饪"],
            "durability": 200,
            "stackable": False,
            "requires": {"grass": 3, "wood": 2},
            "fuel_efficiency": 1.0
        },
        "矛": {
            "id": "spear",
            "name": "矛",
            "description": "简单的武器，用于对抗敌人",
            "rarity": "common",
            "category": "weapon",
            "uses": ["战斗"],
            "durability": 100,
            "stackable": False,
            "damage": 34,
            "requires": {"twigs": 2, "rope": 2, "flint": 1}
        },
        "蜘蛛矛": {
            "id": "spider_spear",
            "name": "蜘蛛矛",
            "description": "用蜘蛛丝加强的矛，伤害更高",
            "rarity": "uncommon",
            "category": "weapon",
            "uses": ["战斗"],
            "durability": 150,
            "stackable": False,
            "damage": 68,
            "requires": {"wood": 3, "spider_silk": 2, "flint": 1}
        },
        "树枝": {
            "id": "twigs",
            "name": "树枝",
            "description": "从小树苗采集的树枝（twig），制作工具的基础材料",
            "rarity": "common",
            "category": "resource",
            "uses": ["工具制作", "燃料"],
            "durability": None,
            "stackable": True,
            "stack_size": 40,
            "weight": 0.1
        },
        "金子": {
            "id": "goldnugget",
            "name": "金子",
            "description": "金块（gold nugget），用于制造科学机器、炼金引擎和高级工具",
            "rarity": "uncommon",
            "category": "resource",
            "uses": ["科技", "高级工具"],
            "durability": None,
            "stackable": True,
            "stack_size": 20,
            "weight": 0.5
        },
        "木炭": {
            "id": "charcoal",
            "name": "木炭",
            "description": "烧树得到的木炭（charcoal），烹饪锅和晾肉架的原料",
            "rarity": "common",
            "category": "resource",
            "uses": ["烹饪", "燃料"],
            "durability": None,
            "stackable": True,
            "stack_size": 40,
            "weight": 0.3
        },
        "齿轮": {
            "id": "gears",
            "name": "齿轮",
            "description": "从发条生物掉落的齿轮（gears），制造冰箱等高级设备",
            "rarity": "rare",
            "category": "resource",
            "uses": ["高级建筑"],
            "durability": None,
            "stackable": True,
            "stack_size": 20,
            "weight": 0.5
        },
        "粪便": {
            "id": "poop",
            "name": "粪便",
            "description": "粪便（manure），农场的肥料",
            "rarity": "common",
            "category": "resource",
            "uses": ["肥料"],
            "durability": None,
            "stackable": True,
            "stack_size": 20,
            "weight": 0.5
        },
        "斧头": {
            "id": "axe",
            "name": "斧头",
            "description": "砍树工具（axe），可砍树获得木头，无需科学机器",
            "rarity": "common",
            "category": "tool",
            "uses": ["砍树"],
            "durability": 100,
            "stackable": False,
            "weight": 1.0,
            "requires": {"twigs": 1, "flint": 1},
            "station": None
        },
        "镐子": {
            "id": "pickaxe",
            "name": "镐子",
            "description": "挖矿工具（pickaxe），可挖石头获得燧石和金子，无需科学机器",
            "rarity": "common",
            "category": "tool",
            "uses": ["挖矿"],
            "durability": 33,
            "stackable": False,
            "weight": 1.0,
            "requires": {"twigs": 2, "flint": 2},
            "station": None
        },
        "铲子": {
            "id": "shovel",
            "name": "铲子",
            "description": "挖掘工具（shovel），可挖树桩/草丛/浆果丛，需要科学机器",
            "rarity": "common",
            "category": "tool",
            "uses": ["挖掘"],
            "durability": 25,
            "stackable": False,
            "weight": 1.0,
            "requires": {"twigs": 2, "flint": 2},
            "station": "science"
        },
        "锤子": {
            "id": "hammer",
            "name": "锤子",
            "description": "拆除工具（hammer），可拆建筑回收材料，也能敲石头",
            "rarity": "common",
            "category": "tool",
            "uses": ["拆除", "挖掘"],
            "durability": 75,
            "stackable": False,
            "weight": 1.0,
            "requires": {"twigs": 3, "stone": 3, "grass": 6},
            "station": None
        },
        "火把": {
            "id": "torch",
            "name": "火把",
            "description": "照明工具（torch），夜晚照明的必备品，可点燃可燃物",
            "rarity": "common",
            "category": "tool",
            "uses": ["照明", "点火"],
            "durability": 75,
            "stackable": False,
            "weight": 0.5,
            "requires": {"grass": 2, "twigs": 2},
            "station": None
        },
        "草绳": {
            "id": "rope",
            "name": "草绳",
            "description": "用草搓成的绳子（rope），许多工具和建筑的材料，需要科学机器",
            "rarity": "common",
            "category": "refined",
            "uses": ["工具制作", "建筑"],
            "durability": None,
            "stackable": True,
            "stack_size": 40,
            "weight": 0.2,
            "requires": {"grass": 3},
            "station": "science"
        },
        "木板": {
            "id": "boards",
            "name": "木板",
            "description": "用木头加工的木板（boards），高级建筑的原料，需要科学机器",
            "rarity": "common",
            "category": "refined",
            "uses": ["建筑"],
            "durability": None,
            "stackable": True,
            "stack_size": 40,
            "weight": 0.5,
            "requires": {"wood": 4},
            "station": "science"
        },
        "石块": {
            "id": "cutstone",
            "name": "石块",
            "description": "打磨过的石块（cut stone），高级建筑的原料，需要科学机器",
            "rarity": "common",
            "category": "refined",
            "uses": ["建筑"],
            "durability": None,
            "stackable": True,
            "stack_size": 40,
            "weight": 1.0,
            "requires": {"stone": 3},
            "station": "science"
        },
        "电子元件": {
            "id": "transistor",
            "name": "电子元件",
            "description": "电子元件（electrical doodad），炼金引擎和高级建筑的原料",
            "rarity": "uncommon",
            "category": "refined",
            "uses": ["高级建筑"],
            "durability": None,
            "stackable": True,
            "stack_size": 40,
            "weight": 0.3,
            "requires": {"goldnugget": 1, "cutstone": 1},
            "station": "science"
        },
        "黄金斧": {
            "id": "goldenaxe",
            "name": "黄金斧",
            "description": "黄金打造的斧头（luxury axe），耐久更高砍得更快，需要炼金引擎",
            "rarity": "uncommon",
            "category": "tool",
            "uses": ["砍树"],
            "durability": 400,
            "stackable": False,
            "weight": 1.0,
            "requires": {"twigs": 4, "goldnugget": 2},
            "station": "alchemy"
        },
        "黄金镐": {
            "id": "goldenpickaxe",
            "name": "黄金镐",
            "description": "黄金打造的镐子（opulent pickaxe），耐久更高挖得更快，需要炼金引擎",
            "rarity": "uncommon",
            "category": "tool",
            "uses": ["挖矿"],
            "durability": 132,
            "stackable": False,
            "weight": 1.0,
            "requires": {"twigs": 4, "goldnugget": 2},
            "station": "alchemy"
        },
        "木甲": {
            "id": "armorwood",
            "name": "木甲",
            "description": "木头做的护甲（log suit），吸收 80% 伤害，需要科学机器",
            "rarity": "common",
            "category": "armor",
            "uses": ["防御"],
            "durability": 315,
            "stackable": False,
            "weight": 2.0,
            "requires": {"wood": 8, "rope": 2},
            "station": "science"
        },
        "草甲": {
            "id": "armorgrass",
            "name": "草甲",
            "description": "草做的护甲（grass suit），吸收 60% 伤害，无需科学机器",
            "rarity": "common",
            "category": "armor",
            "uses": ["防御"],
            "durability": 112,
            "stackable": False,
            "weight": 1.0,
            "requires": {"grass": 10, "twigs": 2},
            "station": None
        }
    },

    # ===== 生物数据库 =====
    "creatures": {
        "蜘蛛": {
            "id": "spider",
            "name": "蜘蛛",
            "description": "常见的敌对生物，白天缩在蜘蛛巢、黄昏夜晚外出，会群体攻击",
            "health": 100,
            "damage": 20,
            "speed": 6,
            "rarity": "common",
            "danger_level": 2,
            "drops": [{"item": "monster_meat", "chance": 0.5}, {"item": "spider_silk", "chance": 0.5}, {"item": "spider_gland", "chance": 0.5}],
            "behavior": "会主动攻击靠近蜘蛛巢的玩家",
            "location": "蜘蛛巢附近",
            "spawn_time": "黄昏和夜晚"
        },
        "蜘蛛女王": {
            "id": "spider_queen",
            "name": "蜘蛛女王",
            "description": "蜘蛛巢长成后出现的强大领主，极其危险，会召唤小蜘蛛",
            "health": 1250,
            "damage": 80,
            "speed": 8,
            "rarity": "rare",
            "danger_level": 5,
            "drops": [{"item": "monster_meat", "chance": 1.0}, {"item": "spider_silk", "chance": 1.0}, {"item": "spider_gland", "chance": 1.0}],
            "behavior": "极具攻击性，会召唤小蜘蛛和蜘蛛战士",
            "location": "长成的蜘蛛巢",
            "spawn_time": "全时段"
        },
        "兔子": {
            "id": "rabbit",
            "name": "兔子",
            "description": "温和的小动物，可用陷阱捕捉，见到玩家会逃进洞穴",
            "health": 25,
            "damage": 0,
            "speed": 12,
            "rarity": "common",
            "danger_level": 0,
            "drops": [{"item": "morsel", "chance": 1.0}],
            "behavior": "会逃跑，不主动攻击",
            "location": "草原洞穴附近",
            "spawn_time": "白天"
        },
        "蜜蜂": {
            "id": "bee",
            "name": "蜜蜂",
            "description": "会采蜜的昆虫，攻击蜂巢才会激怒它",
            "health": 100,
            "damage": 10,
            "speed": 10,
            "rarity": "common",
            "danger_level": 1,
            "drops": [{"item": "honey", "chance": 0.8}, {"item": "stinger", "chance": 0.8}],
            "behavior": "防守蜂巢，被激怒会攻击",
            "location": "蜂巢附近",
            "spawn_time": "白天"
        },
        "猪人": {
            "id": "pig",
            "name": "猪人",
            "description": "中立的猪人（pig），可用肉收买当帮手，月圆夜会变成狂暴猪",
            "health": 250,
            "damage": 33,
            "speed": 6,
            "rarity": "common",
            "danger_level": 2,
            "drops": [{"item": "meat", "chance": 1.0}, {"item": "pig_skin", "chance": 0.75}],
            "behavior": "平时中立，被攻击或月圆时狂暴",
            "location": "猪人村/猪人房附近",
            "spawn_time": "白天"
        },
        "牛": {
            "id": "beefalo",
            "name": "牛",
            "description": "群居的牛（beefalo），会产粪，被激怒会冲撞",
            "health": 500,
            "damage": 34,
            "speed": 7,
            "rarity": "common",
            "danger_level": 2,
            "drops": [{"item": "meat", "chance": 1.0}, {"item": "beefalo_wool", "chance": 0.5}, {"item": "beefalo_horn", "chance": 0.33}],
            "behavior": "成群活动，平时中立，发情期或被打会攻击",
            "location": "草原牛群",
            "spawn_time": "全时段"
        },
        "猎犬": {
            "id": "hound",
            "name": "猎犬",
            "description": "周期来犯的猎犬（hound），成队攻击，会掉狗牙",
            "health": 150,
            "damage": 20,
            "speed": 8,
            "rarity": "uncommon",
            "danger_level": 3,
            "drops": [{"item": "monster_meat", "chance": 1.0}, {"item": "hound_tooth", "chance": 0.5}],
            "behavior": "周期性成群进攻，主动攻击玩家",
            "location": "每 3-13 天随机来袭",
            "spawn_time": "随时"
        },
        "高脚鸟": {
            "id": "tallbird",
            "name": "高脚鸟",
            "description": "高大的敌对鸟类（tallbird），守护鸟蛋，攻击力强",
            "health": 400,
            "damage": 50,
            "speed": 8,
            "rarity": "uncommon",
            "danger_level": 4,
            "drops": [{"item": "meat", "chance": 1.0}, {"item": "tallbird_egg", "chance": 1.0}],
            "behavior": "会主动追击靠近的玩家",
            "location": "岩石地",
            "spawn_time": "白天"
        },
        "树人守卫": {
            "id": "treeguard",
            "name": "树人守卫",
            "description": "砍树太多会唤醒的树人守卫（treeguard），中立但被攻击会反击，掉活木",
            "health": 1400,
            "damage": 62,
            "speed": 3,
            "rarity": "rare",
            "danger_level": 4,
            "drops": [{"item": "living_log", "chance": 1.0}, {"item": "monster_meat", "chance": 1.0}],
            "behavior": "砍树概率唤醒，可种树安抚",
            "location": "树林（砍树触发）",
            "spawn_time": "砍树后"
        },
        "火鸡": {
            "id": "gobbler",
            "name": "火鸡",
            "description": "偷吃浆果的火鸡（gobbler），会逃跑，掉鸡腿",
            "health": 50,
            "damage": 0,
            "speed": 8,
            "rarity": "common",
            "danger_level": 0,
            "drops": [{"item": "drumstick", "chance": 1.0}],
            "behavior": "偷吃浆果后逃跑，不攻击",
            "location": "浆果丛附近",
            "spawn_time": "白天"
        }
    },

    # ===== 建筑数据库 =====
    "buildings": {
        "营火": {
            "id": "campfire",
            "name": "营火",
            "description": "临时火堆，提供光照和温暖，可烹饪；烧完即灭，靠近可燃物会引发火灾",
            "category": "essential",
            "tier": 1,
            "cost": {"grass": 3, "wood": 2},
            "crafting_time": 5,
            "uses": ["光照", "温暖", "烹饪"],
            "stats": {
                "light_range": 15,
                "warmth": 60,
                "fuel_consumption": 1.0,
                "cooking_efficiency": 1.0
            },
            "priority": "CRITICAL"
        },
        "火堆": {
            "id": "fire_pit",
            "name": "火堆",
            "description": "永久火堆（fire pit），可反复添加燃料，比营火更安全、燃料效率翻倍",
            "category": "essential",
            "tier": 1,
            "cost": {"wood": 2, "stone": 12},
            "crafting_time": 8,
            "uses": ["光照", "温暖", "烹饪"],
            "stats": {
                "light_range": 15,
                "warmth": 60,
                "fuel_consumption": 0.5,
                "cooking_efficiency": 1.0
            },
            "priority": "CRITICAL"
        },
        "科学机器": {
            "id": "science_machine",
            "name": "科学机器",
            "description": "一级科技（science machine），解锁草绳/木板/石块/背包等基础配方",
            "category": "research",
            "tier": 1,
            "cost": {"goldnugget": 1, "wood": 4, "stone": 4},
            "crafting_time": 15,
            "uses": ["科技研究"],
            "stats": {
                "research_speed": 1.0,
                "science_points": 1
            },
            "priority": "HIGH"
        },
        "炼金引擎": {
            "id": "alchemy_engine",
            "name": "炼金引擎",
            "description": "二级科技（alchemy engine），解锁高级工具/武器/护甲配方，需要先有科学机器",
            "category": "research",
            "tier": 2,
            "cost": {"boards": 4, "cutstone": 2, "transistor": 2},
            "crafting_time": 20,
            "uses": ["科技研究"],
            "stats": {
                "research_speed": 1.5,
                "science_points": 2
            },
            "priority": "HIGH"
        },
        "烹饪锅": {
            "id": "cooking_pot",
            "name": "烹饪锅",
            "description": "烹饪锅（crock pot），用食材组合烹饪高级料理",
            "category": "cooking",
            "tier": 2,
            "cost": {"cutstone": 3, "charcoal": 6, "twigs": 6},
            "crafting_time": 10,
            "uses": ["烹饪", "食物合成"],
            "stats": {
                "recipes": 15,
                "efficiency": 1.2,
                "capacity": 4
            },
            "priority": "HIGH"
        },
        "冰箱": {
            "id": "fridge",
            "name": "冰箱",
            "description": "冰箱（ice box），减缓食物腐烂，需要炼金引擎",
            "category": "storage",
            "tier": 3,
            "cost": {"goldnugget": 2, "boards": 2, "gears": 2},
            "crafting_time": 20,
            "uses": ["食物保存"],
            "stats": {
                "storage_capacity": 9,
                "rot_slowdown": 0.5,
                "slots": 9
            },
            "priority": "MEDIUM"
        },
        "箱子": {
            "id": "chest",
            "name": "箱子",
            "description": "储物箱（chest），存放物品，需要科学机器",
            "category": "storage",
            "tier": 1,
            "cost": {"boards": 3},
            "crafting_time": 10,
            "uses": ["储物"],
            "stats": {
                "slots": 9
            },
            "priority": "MEDIUM"
        },
        "晾肉架": {
            "id": "drying_rack",
            "name": "晾肉架",
            "description": "晾肉架（drying rack），把生肉晾成肉干，肉干保质期极长",
            "category": "cooking",
            "tier": 2,
            "cost": {"twigs": 3, "charcoal": 2, "rope": 3},
            "crafting_time": 10,
            "uses": ["晾肉"],
            "stats": {
                "capacity": 1
            },
            "priority": "HIGH"
        },
        "农场": {
            "id": "farm",
            "name": "农场",
            "description": "基础农场（basic farm），种植作物，需要科学机器",
            "category": "farming",
            "tier": 2,
            "cost": {"grass": 6, "poop": 4, "wood": 4},
            "crafting_time": 8,
            "uses": ["种植", "食物生产"],
            "stats": {
                "plots": 1,
                "growth_time": 20,
                "yield": 4
            },
            "priority": "HIGH"
        },
        "帐篷": {
            "id": "tent",
            "name": "帐篷",
            "description": "帐篷（tent），睡觉恢复生命和理智，可使用 6 次",
            "category": "survival",
            "tier": 2,
            "cost": {"spider_silk": 6, "twigs": 4, "rope": 3},
            "crafting_time": 10,
            "uses": ["睡眠", "恢复理智"],
            "stats": {
                "sleep_uses": 6
            },
            "priority": "MEDIUM"
        }
    },

    # ===== 食物数据库 =====
    "foods": {
        "浆果": {
            "id": "berry",
            "name": "浆果",
            "description": "从灌木采集的浆果（berries），可直接食用",
            "rarity": "common",
            "type": "raw",
            "nutrition": {"hunger": 9.4, "health": 0, "sanity": 0},
            "spoil_time": 6,
            "stackable": True
        },
        "熟浆果": {
            "id": "berries_cooked",
            "name": "熟浆果",
            "description": "烤过的浆果（roasted berries），比生浆果更补",
            "rarity": "common",
            "type": "cooked",
            "nutrition": {"hunger": 12.5, "health": 1, "sanity": 0},
            "spoil_time": 3,
            "stackable": True,
            "requires": "berry"
        },
        "蝴蝶翅膀": {
            "id": "butterfly_wings",
            "name": "蝴蝶翅膀",
            "description": "蝴蝶掉落的翅膀（butterfly wings），生吃可回血",
            "rarity": "common",
            "type": "raw",
            "nutrition": {"hunger": 9.4, "health": 8, "sanity": 0},
            "spoil_time": 6,
            "stackable": True
        },
        "烤肉": {
            "id": "cooked_meat",
            "name": "烤肉",
            "description": "火烤的大肉（cooked meat），比生肉更补且不降理智",
            "rarity": "common",
            "type": "cooked",
            "nutrition": {"hunger": 18.8, "health": 3, "sanity": 0},
            "spoil_time": 15,
            "stackable": True,
            "requires": "meat"
        },
        "肉丸": {
            "id": "meatballs",
            "name": "肉丸",
            "description": "烹饪锅料理（meatballs）：1 份肉 + 3 份填充（浆果/冰等），高性价比填饱肚子",
            "rarity": "common",
            "type": "cooked",
            "nutrition": {"hunger": 62.5, "health": 3, "sanity": 5},
            "spoil_time": 10,
            "stackable": True,
            "recipe": {"meat": 1, "filler": 3}
        },
        "蜂蜜火腿": {
            "id": "honey_ham",
            "name": "蜂蜜火腿",
            "description": "烹饪锅料理（honey ham）：1.5+ 肉 + 1 蜂蜜，回血又回饥饿",
            "rarity": "uncommon",
            "type": "cooked",
            "nutrition": {"hunger": 75, "health": 30, "sanity": 5},
            "spoil_time": 15,
            "stackable": True,
            "recipe": {"meat": 2, "honey": 1}
        },
        "培根煎蛋": {
            "id": "bacon_and_eggs",
            "name": "培根煎蛋",
            "description": "烹饪锅料理（bacon and eggs）：1.5+ 肉 + 2 蛋，营养全面保质期长",
            "rarity": "uncommon",
            "type": "cooked",
            "nutrition": {"hunger": 75, "health": 20, "sanity": 5},
            "spoil_time": 20,
            "stackable": True,
            "recipe": {"meat": 2, "egg": 2}
        },
        "炖肉": {
            "id": "meat_stew",
            "name": "炖肉",
            "description": "烹饪锅料理（meaty stew）：3+ 肉量，回饥饿最多的大餐",
            "rarity": "uncommon",
            "type": "cooked",
            "nutrition": {"hunger": 150, "health": 12, "sanity": 5},
            "spoil_time": 10,
            "stackable": True,
            "recipe": {"meat": 3, "filler": 1}
        },
        "火龙果派": {
            "id": "dragonpie",
            "name": "火龙果派",
            "description": "烹饪锅料理（dragonpie）：1 火龙果 + 3 填充，回血极佳",
            "rarity": "rare",
            "type": "cooked",
            "nutrition": {"hunger": 75, "health": 40, "sanity": 5},
            "spoil_time": 15,
            "stackable": True,
            "recipe": {"dragonfruit": 1, "filler": 3}
        },
        "果酱": {
            "id": "fist_full_of_jam",
            "name": "果酱",
            "description": "烹饪锅料理（fist full of jam）：浆果熬制，简单回理智",
            "rarity": "common",
            "type": "cooked",
            "nutrition": {"hunger": 37.5, "health": 3, "sanity": 5},
            "spoil_time": 15,
            "stackable": True,
            "recipe": {"berry": 4}
        },
        "火鸡大餐": {
            "id": "turkey_dinner",
            "name": "火鸡大餐",
            "description": "烹饪锅料理（turkey dinner）：2 鸡腿 + 肉 + 蔬菜，回血回饥饿",
            "rarity": "uncommon",
            "type": "cooked",
            "nutrition": {"hunger": 75, "health": 20, "sanity": 5},
            "spoil_time": 6,
            "stackable": True,
            "recipe": {"drumstick": 2, "meat": 1, "vegetable": 1}
        }
    },

    # ===== 季节数据库 =====
    "seasons": {
        "春": {
            "id": "spring",
            "name": "春天",
            "duration": 15,
            "temperature": 20,
            "description": "多雨的季节，淋雨潮湿会掉理智，会有青蛙雨，但植物生长旺盛",
            "features": [
                "持续下雨",
                "植物生长加速",
                "浆果丛和花大量生长",
                "青蛙雨"
            ],
            "challenges": [
                "淋雨潮湿掉理智",
                "青蛙雨袭击",
                "雷电"
            ],
            "resources": {
                "wood": "充足",
                "grass": "充足",
                "berry": "充足"
            }
        },
        "夏": {
            "id": "summer",
            "name": "夏天",
            "duration": 20,
            "temperature": 35,
            "description": "炎热的季节，容易着火",
            "features": [
                "温度升高",
                "容易着火",
                "食物加速腐烂"
            ],
            "challenges": [
                "过热死亡",
                "山林火灾",
                "食物腐烂"
            ],
            "resources": {
                "wood": "减少",
                "food_spoil": "加速"
            }
        },
        "秋": {
            "id": "autumn",
            "name": "秋天",
            "duration": 20,
            "temperature": 15,
            "description": "树木脱叶，准备冬季",
            "features": [
                "树木脱叶",
                "资源丰富",
                "温度下降"
            ],
            "challenges": [
                "树木掉叶",
                "食物准备"
            ],
            "resources": {
                "wood": "极多",
                "vegetable": "充足"
            }
        },
        "冬": {
            "id": "winter",
            "name": "冬天",
            "duration": 15,
            "temperature": -15,
            "description": "严寒季节，最具挑战",
            "features": [
                "温度极低",
                "食物匮乏",
                "敌人减少"
            ],
            "challenges": [
                "冻死风险",
                "食物短缺",
                "农场不生长"
            ],
            "resources": {
                "food": "极缺",
                "enemies": "减少"
            }
        }
    }
}

# ========== API 路由 ==========

@api_app.route('/api/game-data/health', methods=['GET'])
def health():
    """健康检查"""
    return jsonify({
        'status': 'ok',
        'service': 'Dont Starve Game Data API',
        'version': '1.0.0',
        'timestamp': datetime.now().isoformat()
    }), 200


@api_app.route('/api/game-data/items', methods=['GET'])
def get_all_items():
    """获取所有物品列表"""
    return jsonify({
        'status': 'success',
        'count': len(GAME_DATABASE['items']),
        'items': list(GAME_DATABASE['items'].keys())
    }), 200


@api_app.route('/api/game-data/items/<item_name>', methods=['GET'])
def get_item(item_name):
    """获取特定物品详情"""
    if item_name in GAME_DATABASE['items']:
        item_data = GAME_DATABASE['items'][item_name]
        return jsonify({
            'status': 'success',
            'item_name': item_name,
            'data': item_data
        }), 200
    else:
        return jsonify({
            'status': 'error',
            'message': f'物品 "{item_name}" 未找到',
            'available_items': list(GAME_DATABASE['items'].keys())
        }), 404


@api_app.route('/api/game-data/creatures', methods=['GET'])
def get_all_creatures():
    """获取所有生物列表"""
    return jsonify({
        'status': 'success',
        'count': len(GAME_DATABASE['creatures']),
        'creatures': list(GAME_DATABASE['creatures'].keys())
    }), 200


@api_app.route('/api/game-data/creatures/<creature_name>', methods=['GET'])
def get_creature(creature_name):
    """获取特定生物详情"""
    if creature_name in GAME_DATABASE['creatures']:
        creature_data = GAME_DATABASE['creatures'][creature_name]
        return jsonify({
            'status': 'success',
            'creature_name': creature_name,
            'data': creature_data
        }), 200
    else:
        return jsonify({
            'status': 'error',
            'message': f'生物 "{creature_name}" 未找到',
            'available_creatures': list(GAME_DATABASE['creatures'].keys())
        }), 404


@api_app.route('/api/game-data/buildings', methods=['GET'])
def get_all_buildings():
    """获取所有建筑列表"""
    return jsonify({
        'status': 'success',
        'count': len(GAME_DATABASE['buildings']),
        'buildings': list(GAME_DATABASE['buildings'].keys())
    }), 200


@api_app.route('/api/game-data/buildings/<building_name>', methods=['GET'])
def get_building(building_name):
    """获取特定建筑详情"""
    if building_name in GAME_DATABASE['buildings']:
        building_data = GAME_DATABASE['buildings'][building_name]
        return jsonify({
            'status': 'success',
            'building_name': building_name,
            'data': building_data
        }), 200
    else:
        return jsonify({
            'status': 'error',
            'message': f'建筑 "{building_name}" 未找到',
            'available_buildings': list(GAME_DATABASE['buildings'].keys())
        }), 404


@api_app.route('/api/game-data/foods', methods=['GET'])
def get_all_foods():
    """获取所有食物列表"""
    return jsonify({
        'status': 'success',
        'count': len(GAME_DATABASE['foods']),
        'foods': list(GAME_DATABASE['foods'].keys())
    }), 200


@api_app.route('/api/game-data/foods/<food_name>', methods=['GET'])
def get_food(food_name):
    """获取特定食物详情"""
    if food_name in GAME_DATABASE['foods']:
        food_data = GAME_DATABASE['foods'][food_name]
        return jsonify({
            'status': 'success',
            'food_name': food_name,
            'data': food_data
        }), 200
    else:
        return jsonify({
            'status': 'error',
            'message': f'食物 "{food_name}" 未找到',
            'available_foods': list(GAME_DATABASE['foods'].keys())
        }), 404


@api_app.route('/api/game-data/seasons', methods=['GET'])
def get_all_seasons():
    """获取所有季节列表"""
    return jsonify({
        'status': 'success',
        'count': len(GAME_DATABASE['seasons']),
        'seasons': list(GAME_DATABASE['seasons'].keys())
    }), 200


@api_app.route('/api/game-data/seasons/<season_name>', methods=['GET'])
def get_season(season_name):
    """获取特定季节详情"""
    if season_name in GAME_DATABASE['seasons']:
        season_data = GAME_DATABASE['seasons'][season_name]
        return jsonify({
            'status': 'success',
            'season_name': season_name,
            'data': season_data
        }), 200
    else:
        return jsonify({
            'status': 'error',
            'message': f'季节 "{season_name}" 未找到',
            'available_seasons': list(GAME_DATABASE['seasons'].keys())
        }), 404


def _fuzzy_match(query, name, desc, eid=""):
    """模糊匹配：先精确子串，失败则按 2 字滑动窗口（bigram）回退。

    name/desc 是中文，eid 是英文 id（DST prefab，如 spider/campfire/winter），
    让英文关键词（模型更常用）也能命中词条。
    """
    if not query:
        return False
    haystacks = (name, desc, eid)
    if any(query in h for h in haystacks):
        return True
    # 中文 bigram 兜底：只对含中文的查询启用（英文用精确子串即可，避免 sp→spring 误命中）
    if any('一' <= c <= '鿿' for c in query):
        for i in range(len(query) - 1):
            gram = query[i:i + 2]
            if any(gram in h for h in haystacks):
                return True
    return False


@api_app.route('/api/game-data/search', methods=['GET'])
def search_game_data():
    """搜索游戏数据（全文搜索，含中文 bigram 模糊回退）"""
    query = request.args.get('q', '').lower()
    category = request.args.get('category', 'all')  # items, creatures, buildings, foods, seasons

    if not query:
        return jsonify({
            'status': 'error',
            'message': '请提供搜索关键词'
        }), 400

    results = {
        'query': query,
        'results': {}
    }

    # 搜索物品
    if category in ['all', 'items']:
        item_matches = {
            name: data for name, data in GAME_DATABASE['items'].items()
            if _fuzzy_match(query, name.lower(), data.get('description', '').lower(), data.get('id', '').lower())
        }
        if item_matches:
            results['results']['items'] = item_matches

    # 搜索生物
    if category in ['all', 'creatures']:
        creature_matches = {
            name: data for name, data in GAME_DATABASE['creatures'].items()
            if _fuzzy_match(query, name.lower(), data.get('description', '').lower(), data.get('id', '').lower())
        }
        if creature_matches:
            results['results']['creatures'] = creature_matches

    # 搜索建筑
    if category in ['all', 'buildings']:
        building_matches = {
            name: data for name, data in GAME_DATABASE['buildings'].items()
            if _fuzzy_match(query, name.lower(), data.get('description', '').lower(), data.get('id', '').lower())
        }
        if building_matches:
            results['results']['buildings'] = building_matches

    # 搜索食物
    if category in ['all', 'foods']:
        food_matches = {
            name: data for name, data in GAME_DATABASE['foods'].items()
            if _fuzzy_match(query, name.lower(), data.get('description', '').lower(), data.get('id', '').lower())
        }
        if food_matches:
            results['results']['foods'] = food_matches

    # 搜索季节
    if category in ['all', 'seasons']:
        season_matches = {
            name: data for name, data in GAME_DATABASE['seasons'].items()
            if _fuzzy_match(query, name.lower(), data.get('description', '').lower(), data.get('id', '').lower())
        }
        if season_matches:
            results['results']['seasons'] = season_matches
    
    if results['results']:
        return jsonify({
            'status': 'success',
            **results
        }), 200
    else:
        return jsonify({
            'status': 'success',
            'message': '未找到匹配的结果',
            'query': query,
            'category': category
        }), 200


@api_app.route('/api/game-data/recipe/<food_name>', methods=['GET'])
def get_recipe(food_name):
    """获取食物配方"""
    if food_name in GAME_DATABASE['foods']:
        food_data = GAME_DATABASE['foods'][food_name]
        if 'recipe' in food_data:
            return jsonify({
                'status': 'success',
                'food_name': food_name,
                'recipe': food_data['recipe'],
                'description': f"制作 {food_name} 需要："
            }), 200
        else:
            return jsonify({
                'status': 'success',
                'message': f'{food_name} 是原始食物，不需要配方',
                'food_name': food_name,
                'type': food_data.get('type', 'unknown')
            }), 200
    else:
        return jsonify({
            'status': 'error',
            'message': f'食物 "{food_name}" 未找到'
        }), 404


@api_app.route('/api/game-data/crafting/<building_name>', methods=['GET'])
def get_crafting_cost(building_name):
    """获取建筑的制作成本"""
    if building_name in GAME_DATABASE['buildings']:
        building_data = GAME_DATABASE['buildings'][building_name]
        return jsonify({
            'status': 'success',
            'building_name': building_name,
            'cost': building_data.get('cost', {}),
            'crafting_time': building_data.get('crafting_time', 0),
            'description': building_data.get('description', '')
        }), 200
    else:
        return jsonify({
            'status': 'error',
            'message': f'建筑 "{building_name}" 未找到'
        }), 404


@api_app.route('/api/game-data/items-meta', methods=['GET'])
def get_items_meta():
    """返回所有物品/食物/建筑的 id、稀有度、配方（一次拿全，免 N+1 请求）。

    供 agent 动态构建「可合成白名单」和「风险分级清单」——game_meta.py 会拉这个端点，
    翻译成 DST prefab 后并入硬编码兜底清单。
    """
    craftables = []
    for name, d in GAME_DATABASE['items'].items():
        craftables.append({
            'id': d['id'], 'name': name, 'rarity': d.get('rarity', 'common'),
            'category': d.get('category'), 'cost': d.get('requires'),
        })
    for name, d in GAME_DATABASE['foods'].items():
        craftables.append({
            'id': d['id'], 'name': name, 'rarity': d.get('rarity', 'common'),
            'category': 'food', 'cost': d.get('recipe'),
        })
    for name, d in GAME_DATABASE['buildings'].items():
        craftables.append({
            'id': d['id'], 'name': name, 'rarity': 'essential',
            'category': 'building', 'cost': d.get('cost'),
        })
    return jsonify({'status': 'success', 'count': len(craftables), 'craftables': craftables})


@api_app.route('/api/game-data/tips', methods=['GET'])
def get_game_tips():
    """获取游戏提示"""
    tips = [
        "营火是第一天的最高优先级 - 必须在日落前完成，夜晚黑暗会持续掉理智",
        "理智值过低会出现影怪攻击，可用烤绿蘑菇、采花、睡觉恢复理智",
        "肉丸（1 肉 + 3 浆果/冰）是前期最高性价比的填饱肚子料理",
        "蜘蛛女王极其危险，不要在没有装备的情况下靠近长成的蜘蛛巢",
        "冬天严寒会冻死人，需提前备足燃料和保暖衣物",
        "农场在冬天不生长，必须靠储备食物、晾肉架肉干或陷阱狩猎",
        "睡觉（帐篷）是恢复理智和生命最有效的方法",
        "火堆比营火更划算：可反复加燃料、燃料效率翻倍、不会引燃周围",
        "生肉和怪物肉会掉理智，烤熟或烹饪锅加工后再吃",
        "冰箱需要齿轮（从发条生物掉落），是保存食物过冬的关键"
    ]
    
    import random
    selected_tips = random.sample(tips, min(3, len(tips)))
    
    return jsonify({
        'status': 'success',
        'tips': selected_tips,
        'total_available_tips': len(tips)
    }), 200


@api_app.route('/api/game-data/database-stats', methods=['GET'])
def get_database_stats():
    """获取游戏数据库统计"""
    return jsonify({
        'status': 'success',
        'statistics': {
            'items': len(GAME_DATABASE['items']),
            'creatures': len(GAME_DATABASE['creatures']),
            'buildings': len(GAME_DATABASE['buildings']),
            'foods': len(GAME_DATABASE['foods']),
            'seasons': len(GAME_DATABASE['seasons']),
            'total_entries': sum(len(v) for v in GAME_DATABASE.values())
        },
        'api_version': '1.0.0',
        'game': 'Dont Starve'
    }), 200


# ========== 错误处理 ==========

@api_app.errorhandler(404)
def not_found(error):
    """处理 404 错误"""
    return jsonify({
        'status': 'error',
        'message': '端点未找到',
        'available_endpoints': [
            '/api/game-data/health',
            '/api/game-data/items',
            '/api/game-data/creatures',
            '/api/game-data/buildings',
            '/api/game-data/foods',
            '/api/game-data/seasons',
            '/api/game-data/search?q=keyword',
            '/api/game-data/recipe/<food_name>',
            '/api/game-data/crafting/<building_name>',
            '/api/game-data/tips',
            '/api/game-data/database-stats'
        ]
    }), 404


@api_app.errorhandler(500)
def server_error(error):
    """处理 500 错误"""
    return jsonify({
        'status': 'error',
        'message': '服务器错误',
        'error': str(error)
    }), 500


if __name__ == '__main__':
    print("🎮 饥荒游戏数据 API 服务器启动")
    print("📍 运行地址: http://localhost:5001")
    print("")
    print("可用的 API 端点：")
    print("  GET  /api/game-data/health              - 健康检查")
    print("  GET  /api/game-data/items               - 获取所有物品")
    print("  GET  /api/game-data/items/<name>        - 获取物品详情")
    print("  GET  /api/game-data/creatures           - 获取所有生物")
    print("  GET  /api/game-data/creatures/<name>    - 获取生物详情")
    print("  GET  /api/game-data/buildings           - 获取所有建筑")
    print("  GET  /api/game-data/buildings/<name>    - 获取建筑详情")
    print("  GET  /api/game-data/foods               - 获取所有食物")
    print("  GET  /api/game-data/foods/<name>        - 获取食物详情")
    print("  GET  /api/game-data/seasons             - 获取所有季节")
    print("  GET  /api/game-data/seasons/<name>      - 获取季节详情")
    print("  GET  /api/game-data/search?q=keyword    - 全文搜索")
    print("  GET  /api/game-data/recipe/<food>       - 获取食物配方")
    print("  GET  /api/game-data/crafting/<building> - 获取建筑制作成本")
    print("  GET  /api/game-data/tips                - 获取游戏提示")
    print("  GET  /api/game-data/database-stats      - 获取数据库统计")
    print("")
    print("按 Ctrl+C 停止服务器")
    print("")
    
    api_app.run(debug=True, port=5001)