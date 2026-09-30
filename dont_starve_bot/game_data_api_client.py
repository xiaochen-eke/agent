"""
游戏数据 API 客户端
用于与独立的游戏数据 API 服务器通信
"""

import requests
from typing import Dict, List, Optional, Any
from functools import lru_cache
import json

class GameDataAPIClient:
    """游戏数据 API 客户端"""
    
    def __init__(self, base_url: str = "http://localhost:5001", timeout: int = 5):
        """
        初始化客户端
        
        Args:
            base_url: API 基础 URL
            timeout: 请求超时时间（秒）
        """
        self.base_url = base_url
        self.timeout = timeout
        self.api_prefix = "/api/game-data"
    
    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """
        发送 HTTP 请求
        
        Args:
            endpoint: API 端点
            params: 查询参数
            
        Returns:
            响应的 JSON 数据
        """
        url = f"{self.base_url}{self.api_prefix}{endpoint}"
        
        try:
            response = requests.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.ConnectionError:
            return {
                'status': 'error',
                'message': f'无法连接到 API 服务器: {self.base_url}',
                'code': 'CONNECTION_ERROR'
            }
        except requests.exceptions.Timeout:
            return {
                'status': 'error',
                'message': f'请求超时 ({self.timeout}s)',
                'code': 'TIMEOUT'
            }
        except requests.exceptions.RequestException as e:
            return {
                'status': 'error',
                'message': f'请求失败: {str(e)}',
                'code': 'REQUEST_ERROR'
            }
        except json.JSONDecodeError:
            return {
                'status': 'error',
                'message': '响应不是有效的 JSON',
                'code': 'JSON_ERROR'
            }
    
    def health_check(self) -> bool:
        """
        检查 API 服务器是否在线
        
        Returns:
            True 如果服务器在线，否则 False
        """
        response = self._make_request('/health')
        return response.get('status') == 'ok'
    
    @lru_cache(maxsize=128)
    def get_item(self, item_name: str) -> Dict:
        """
        获取物品详情
        
        Args:
            item_name: 物品名称
            
        Returns:
            物品数据字典
        """
        response = self._make_request(f'/items/{item_name}')
        return response
    
    def get_all_items(self) -> Dict:
        """
        获取所有物品列表
        
        Returns:
            包含所有物品名称的列表
        """
        response = self._make_request('/items')
        return response
    
    @lru_cache(maxsize=128)
    def get_creature(self, creature_name: str) -> Dict:
        """
        获取生物详情
        
        Args:
            creature_name: 生物名称
            
        Returns:
            生物数据字典
        """
        response = self._make_request(f'/creatures/{creature_name}')
        return response
    
    def get_all_creatures(self) -> Dict:
        """
        获取所有生物列表
        
        Returns:
            包含所有生物名称的列表
        """
        response = self._make_request('/creatures')
        return response
    
    @lru_cache(maxsize=128)
    def get_building(self, building_name: str) -> Dict:
        """
        获取建筑详情
        
        Args:
            building_name: 建筑名称
            
        Returns:
            建筑数据字典
        """
        response = self._make_request(f'/buildings/{building_name}')
        return response
    
    def get_all_buildings(self) -> Dict:
        """
        获取所有建筑列表
        
        Returns:
            包含所有建筑名称的列表
        """
        response = self._make_request('/buildings')
        return response
    
    @lru_cache(maxsize=128)
    def get_food(self, food_name: str) -> Dict:
        """
        获取食物详情
        
        Args:
            food_name: 食物名称
            
        Returns:
            食物数据字典
        """
        response = self._make_request(f'/foods/{food_name}')
        return response
    
    def get_all_foods(self) -> Dict:
        """
        获取所有食物列表
        
        Returns:
            包含所有食物名称的列表
        """
        response = self._make_request('/foods')
        return response
    
    @lru_cache(maxsize=128)
    def get_season(self, season_name: str) -> Dict:
        """
        获取季节详情
        
        Args:
            season_name: 季节名称
            
        Returns:
            季节数据字典
        """
        response = self._make_request(f'/seasons/{season_name}')
        return response
    
    def get_all_seasons(self) -> Dict:
        """
        获取所有季节列表
        
        Returns:
            包含所有季节名称的列表
        """
        response = self._make_request('/seasons')
        return response
    
    def search(self, query: str, category: str = 'all') -> Dict:
        """
        全文搜索游戏数据
        
        Args:
            query: 搜索关键词
            category: 搜索类别 (all, items, creatures, buildings, foods, seasons)
            
        Returns:
            搜索结果
        """
        params = {
            'q': query,
            'category': category
        }
        response = self._make_request('/search', params=params)
        return response
    
    @lru_cache(maxsize=128)
    def get_recipe(self, food_name: str) -> Dict:
        """
        获取食物配方
        
        Args:
            food_name: 食物名称
            
        Returns:
            配方数据
        """
        response = self._make_request(f'/recipe/{food_name}')
        return response
    
    @lru_cache(maxsize=128)
    def get_crafting_cost(self, building_name: str) -> Dict:
        """
        获取建筑的制作成本
        
        Args:
            building_name: 建筑名称
            
        Returns:
            制作成本信息
        """
        response = self._make_request(f'/crafting/{building_name}')
        return response
    
    def get_tips(self) -> Dict:
        """
        获取随机游戏提示
        
        Returns:
            游戏提示列表
        """
        response = self._make_request('/tips')
        return response
    
    def get_database_stats(self) -> Dict:
        """
        获取数据库统计信息
        
        Returns:
            数据库统计
        """
        response = self._make_request('/database-stats')
        return response


# 使用示例和测试函数
if __name__ == '__main__':
    print("🎮 游戏数据 API 客户端测试")
    print("=" * 50)
    print("")
    
    # 创建客户端
    client = GameDataAPIClient()
    
    # 1. 检查服务器
    print("1️⃣ 检查服务器状态...")
    if client.health_check():
        print("✅ 服务器在线")
    else:
        print("❌ 服务器离线，请先启动 game_data_api.py")
        exit(1)
    
    print("")
    
    # 2. 获取物品信息
    print("2️⃣ 获取物品信息...")
    item_response = client.get_item('木头')
    if item_response.get('status') == 'success':
        print(f"✅ 成功获取物品: {item_response['item_name']}")
        print(f"   描述: {item_response['data']['description']}")
    
    print("")
    
    # 3. 获取生物信息
    print("3️⃣ 获取生物信息...")
    creature_response = client.get_creature('蜘蛛')
    if creature_response.get('status') == 'success':
        print(f"✅ 成功获取生物: {creature_response['creature_name']}")
        print(f"   生命值: {creature_response['data']['health']}")
        print(f"   伤害: {creature_response['data']['damage']}")
        print(f"   危险等级: {creature_response['data']['danger_level']}/5")
    
    print("")
    
    # 4. 获取建筑信息
    print("4️⃣ 获取建筑信息...")
    building_response = client.get_building('营火')
    if building_response.get('status') == 'success':
        print(f"✅ 成功获取建筑: {building_response['building_name']}")
        print(f"   制作成本: {building_response['data']['cost']}")
    
    print("")
    
    # 5. 获取食物信息和配方
    print("5️⃣ 获取食物配方...")
    recipe_response = client.get_recipe('蛋糕')
    if recipe_response.get('status') == 'success':
        print(f"✅ 获取配方: {recipe_response['food_name']}")
        if 'recipe' in recipe_response:
            print(f"   配方: {recipe_response['recipe']}")
    
    print("")
    
    # 6. 搜索游戏数据
    print("6️⃣ 搜索游戏数据...")
    search_response = client.search('蜘蛛', category='all')
    if search_response.get('status') == 'success':
        print(f"✅ 搜索 '蜘蛛' 的结果:")
        for category, matches in search_response.get('results', {}).items():
            print(f"   {category}: {list(matches.keys())}")
    
    print("")
    
    # 7. 获取游戏提示
    print("7️⃣ 获取游戏提示...")
    tips_response = client.get_tips()
    if tips_response.get('status') == 'success':
        print(f"✅ 随机提示:")
        for i, tip in enumerate(tips_response.get('tips', []), 1):
            print(f"   {i}. {tip}")
    
    print("")
    
    # 8. 获取数据库统计
    print("8️⃣ 获取数据库统计...")
    stats_response = client.get_database_stats()
    if stats_response.get('status') == 'success':
        stats = stats_response['statistics']
        print(f"✅ 数据库统计:")
        print(f"   物品: {stats['items']} 个")
        print(f"   生物: {stats['creatures']} 个")
        print(f"   建筑: {stats['buildings']} 个")
        print(f"   食物: {stats['foods']} 个")
        print(f"   季节: {stats['seasons']} 个")
        print(f"   总计: {stats['total_entries']} 条记录")
    
    print("")
    print("=" * 50)
    print("✅ 所有测试完成！")