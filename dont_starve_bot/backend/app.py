"""
《饥荒 Don't Starve 游戏攻略助手》后端应用
垂直领域：独立游戏攻略 + 生存策略指导

功能模块：
- RAG（检索增强生成）：外部知识库检索与大模型融合
- Agent（智能体）：联网搜索、工具调用能力
- 领域微调：针对饥荒游戏领域的提示词和响应优化
- 多轮对话：长短期记忆管理
"""

import os
import sys

# 修复 Windows 控制台 GBK 编码问题
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# 绕过系统代理
os.environ.setdefault('no_proxy', '*')
os.environ.setdefault('NO_PROXY', '*')

# 加载 .env 文件（不依赖 python-dotenv）
def _load_dotenv(path=None):
    if path is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    if not os.path.exists(path):
        return
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v
_load_dotenv()

import requests
from fine_tuning_adapter import FineTuningAdapter

# 定义调用你自建 API 的函数
def fetch_game_data(category, name):
    """
    category: 对应你 API 的路径，如 'items', 'foods', 'recipe'
    name: 具体的名称，如 '肉丸'
    """
    url = f"http://127.0.0.1:5001/api/game-data/{category}/{name}"
    try:
        response = requests.get(url, timeout=5) # 设置 5 秒超时，防止卡死
        if response.status_code == 200:
            return response.json() # 返回解析后的字典数据
        else:
            return None
    except Exception as e:
        print(f"API 调用失败: {e}")
        return None

# --- 逻辑分流示例 ---
def handle_user_query(user_input):
    api_data = None
    source_name = ""

    # 1. 简单的关键词触发分流
    if "配方" in user_input or "怎么做" in user_input:
        # 假设从用户输入里提取到了"肉丸"（可以用正则或简单字符串匹配）
        food_name = "肉丸" 
        api_data = fetch_game_data("recipe", food_name)
        source_name = "游戏配方数据库"

    elif "属性" in user_input or "是什么" in user_input:
        item_name = "长矛"
        api_data = fetch_game_data("items", item_name)
        source_name = "物品图鉴"

    # 2. 将 API 数据融合进 Prompt
    if api_data:
        # 将 API 返回的 JSON 转化为一句话，喂给大模型
        extra_info = f"【来自{source_name}的权威数据】：{api_data}"
    else:
        extra_info = "未找到相关的 API 权威数据。"

    return extra_info

import json
import sqlite3
from datetime import datetime
from typing import List, Optional, Dict
from flask import Flask, request, jsonify
from flask_cors import CORS
import chromadb
from chromadb.config import Settings
from openai import OpenAI
from functools import lru_cache

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

# ========== 环境配置 ==========
ZHIPU_API_KEY = os.getenv("ZHIPU_API_KEY", "your-key-here")
# 在 .env 文件或系统环境变量中设置: ZHIPU_API_KEY=你的key

# ========== 系统提示词（核心角色设定） ==========
SYSTEM_PROMPT = """你是一位资深的《饥荒 Don't Starve》游戏攻略专家，具有以下特点：

【身份定位】
- 多年饥荒老玩家，对游戏机制透彻理解
- 精通所有人物档案、生物特性、食物属性、建筑优先级
- 熟悉四季变化规律、世界事件、特殊模式玩法

【回答原则】
1. 【严格遵循知识库】：优先基于提供的参考知识(【参考知识】部分)回答，这些是深度玩家总结
2. 【精确步骤】：给出的策略必须包含具体操作步骤，不能模糊
3. 【安全提示】：涉及生存策略时，务必强调哪些操作容易翻车
4. 【多模式考虑】：回答时区分 Don't Starve 和 Don't Starve Together (DST) 的差异
5. 【季节感知】：根据玩家所在季节给出不同建议

【禁止事项】
- 禁止编造游戏机制（例如：编造某个物品属性、某个生物行为）
- 禁止给出通用建议（例如："保持理智值"没有具体方案）
- 如果问题超出饥荒范围，礼貌拒绝并引导回游戏内容

【说话风格】
- 用亲切但权威的语气，类似"游戏大佬的建议"
- 可适当使用游戏术语和玩家俚语（如"掉san"、"出门翻车"、"打黑科技"等）
- 遇到困难问题时，表现出"让我想想游戏机制..."的思考过程

【必要时使用工具】
- 如果需要查询实时天气来推断游戏内季节变化，调用天气API
- 回答中清楚说明信息来源（出自哪篇攻略）

记住：你的目标是帮助玩家避免翻车，活得更久！🎮
"""

# ========== 1. 数据库初始化 ==========
class ChatDatabase:
    """聊天记录持久化"""
    def __init__(self, db_path: str = "chat_history.db"):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                user_message TEXT NOT NULL,
                bot_response TEXT NOT NULL,
                retrieved_sources TEXT,
                api_used TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT UNIQUE NOT NULL,
                title TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_searches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                query TEXT NOT NULL,
                answer TEXT NOT NULL,
                steps TEXT,
                tool_calls_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_agent_searches_session
            ON agent_searches(session_id, created_at DESC)
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(session_id, key)
            )
        """)
        conn.commit()
        conn.close()
    
    def save_conversation(self, session_id: str, user_msg: str, bot_msg: str, 
                         sources: Optional[List[str]] = None, api_used: Optional[str] = None):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO conversations (session_id, user_message, bot_response, retrieved_sources, api_used)
            VALUES (?, ?, ?, ?, ?)
        """, (session_id, user_msg, bot_msg, json.dumps(sources or []), api_used))
        conn.commit()
        conn.close()
    
    def get_conversation_history(self, session_id: str, limit: int = 20) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT user_message, bot_response, retrieved_sources, api_used, created_at
            FROM conversations
            WHERE session_id = ?
            ORDER BY id DESC
            LIMIT ?
        """, (session_id, limit))
        rows = cursor.fetchall()
        conn.close()
        
        history = []
        for row in rows:
            history.append({
                "user": row[0],
                "bot": row[1],
                "sources": json.loads(row[2]) if row[2] else [],
                "api_used": row[3],
                "timestamp": row[4]
            })
        return list(reversed(history))

    def save_agent_search(self, session_id: str, query: str, answer: str,
                          steps: List[Dict], tool_calls_count: int):
        """保存 Agent 搜索结果"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO agent_searches (session_id, query, answer, steps, tool_calls_count)
            VALUES (?, ?, ?, ?, ?)
        """, (session_id, query, answer, json.dumps(steps, ensure_ascii=False), tool_calls_count))
        conn.commit()
        conn.close()

    def get_agent_history(self, session_id: str, limit: int = 50) -> List[Dict]:
        """获取 Agent 搜索历史"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, query, answer, steps, tool_calls_count, created_at
            FROM agent_searches
            WHERE session_id = ?
            ORDER BY id DESC
            LIMIT ?
        """, (session_id, limit))
        rows = cursor.fetchall()
        conn.close()

        history = []
        for row in rows:
            history.append({
                "id": row[0],
                "query": row[1],
                "answer": row[2],
                "steps": json.loads(row[3]) if row[3] else [],
                "tool_calls_count": row[4],
                "created_at": row[5],
            })
        return history

    def get_agent_search(self, search_id: int) -> Optional[Dict]:
        """获取单条 Agent 搜索结果"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, session_id, query, answer, steps, tool_calls_count, created_at
            FROM agent_searches
            WHERE id = ?
        """, (search_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None
        return {
            "id": row[0],
            "session_id": row[1],
            "query": row[2],
            "answer": row[3],
            "steps": json.loads(row[4]) if row[4] else [],
            "tool_calls_count": row[5],
            "created_at": row[6],
        }

    def save_agent_memory(self, session_id: str, key: str, value: str):
        """保存/更新 Agent 记忆"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO agent_memory (session_id, key, value, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(session_id, key) DO UPDATE SET
                value = excluded.value,
                updated_at = CURRENT_TIMESTAMP
        """, (session_id, key, value))
        conn.commit()
        conn.close()

    def get_agent_memory(self, session_id: str) -> List[Dict]:
        """获取 Agent 记忆"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT key, value, updated_at FROM agent_memory
            WHERE session_id = ?
            ORDER BY updated_at DESC
        """, (session_id,))
        rows = cursor.fetchall()
        conn.close()
        return [{"key": r[0], "value": r[1], "updated_at": r[2]} for r in rows]

# ========== 2. 嵌入服务（轻量级） ==========
class EmbeddingService:
    """统一的向量化服务"""
    def __init__(self, api_key: str):
        _timeout = httpx.Timeout(10.0, connect=5.0) if HAS_HTTPX else 10.0
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://open.bigmodel.cn/api/paas/v4/",
            timeout=_timeout,
            max_retries=0,
        )

    def embed_query(self, text: str) -> List[float]:
        try:
            response = self.client.embeddings.create(
                model="embedding-3",
                input=[text],
                timeout=10.0,
            )
            return response.data[0].embedding
        except Exception as e:
            dim = 1024  # embedding-3 默认维度
            print(f"⚠️ 嵌入 API 调用失败 ({e})，返回零向量占位")
            return [0.0] * dim

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        all_embeddings = []
        batch_size = 16
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            try:
                response = self.client.embeddings.create(
                    model="embedding-3",
                    input=batch,
                    timeout=15.0,
                )
                batch_embeddings = [item.embedding for item in response.data]
                all_embeddings.extend(batch_embeddings)
            except Exception as e:
                dim = 1024
                print(f"⚠️ 嵌入批量调用失败 ({e})，返回零向量占位 ×{len(batch)}")
                all_embeddings.extend([[0.0] * dim for _ in batch])
        return all_embeddings

# ========== 3. 向量数据库与检索 ==========
class KnowledgeBase:
    """知识库管理 - 饥荒垂直领域文档"""
    def __init__(self, persist_dir: str, embedding_service: EmbeddingService):
        self.embedding_service = embedding_service
        self.client = chromadb.PersistentClient(
            path=persist_dir,
            settings=Settings(anonymized_telemetry=False)
        )
        self.collection = self.client.get_or_create_collection(
            name="dont_starve_guides",
            metadata={"hnsw:space": "cosine"}
        )
    
    def add_document(self, doc_id: str, content: str, metadata: Dict):
        """添加单个文档"""
        embedding = self.embedding_service.embed_query(content)
        self.collection.add(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[content],
            metadatas=[metadata]
        )

    def safe_add_document(self, doc_id: str, content: str, metadata: Dict) -> bool:
        """
        安全添加文档，失败时返回 False 而不是抛出异常
        用于启动时批量加载，避免因 API 不可用导致整个应用崩溃
        """
        try:
            # 检查文档是否已存在
            existing = self.collection.get(ids=[doc_id])
            if existing and existing['ids']:
                return True  # 已存在，跳过

            # 尝试嵌入并添加
            try:
                embedding = self.embedding_service.embed_query(content)
                self.collection.add(
                    ids=[doc_id],
                    embeddings=[embedding],
                    documents=[content],
                    metadatas=[metadata]
                )
                return True
            except Exception as e:
                print(f"⚠️ 嵌入文档 '{doc_id}' 失败 (API 可能不可用): {e}")
                return False
        except Exception as e:
            # ChromaDB 本身出错（极少见）
            print(f"⚠️ ChromaDB 操作失败 '{doc_id}': {e}")
            return False

    def has_documents(self) -> bool:
        """检查集合中是否已有文档"""
        return self.collection.count() > 0
    
    def retrieve(self, query: str, k: int = 3) -> List[Dict]:
        """检索相关文档"""
        try:
            query_embedding = self.embedding_service.embed_query(query)
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=k
            )
        except Exception as e:
            print(f"⚠️ 知识库检索失败 (API 或数据库错误): {e}")
            return []

        documents = []
        if results['documents']:
            for i, doc in enumerate(results['documents'][0]):
                documents.append({
                    'content': doc,
                    'metadata': results['metadatas'][0][i] if results['metadatas'] else {},
                    'similarity': results['distances'][0][i] if 'distances' in results else 0.0
                })
        return documents
    
    def get_doc_count(self) -> int:
        return self.collection.count()

# ========== 4. 第三方 API 集成 ==========
class ThirdPartyAPIs:
    """集成外部 API - 如天气、游戏数据等"""
    
    @staticmethod
    @lru_cache(maxsize=100)
    def get_weather(city: str = "成都") -> Dict:
        """
        调用天气 API（模拟）
        在实际应用中可对接高德地图 API
        """
        # 模拟天气数据
        weather_data = {
            "city": city,
            "temp": 25,
            "weather": "晴",
            "humidity": 60,
            "wind_speed": 5,
            "timestamp": datetime.now().isoformat()
        }
        return weather_data
    
    @staticmethod
    def get_game_event(season: str) -> Dict:
        """
        根据真实季节推断游戏内季节事件
        """
        events_map = {
            "春": {"name": "春天", "tips": "蜘蛛巢增多，注意采集草和木头"},
            "夏": {"name": "夏天", "tips": "过热，需要冰箱或冷却装备，灭火"},
            "秋": {"name": "秋天", "tips": "树会脱叶，准备冬季物资"},
            "冬": {"name": "冬天", "tips": "温度下降，需要火焰、衣服等保温"}
        }
        return events_map.get(season, {"name": "未知", "tips": "咨询游戏日历"})
    
    @staticmethod
    def search_game_mechanic(keyword: str) -> Dict:
        """
        模拟调用游戏百科 API
        实际应用可调用 Fandom Wiki 或自建数据库
        """
        mechanics_db = {
            "理智值": {
                "desc": "玩家心理状态，低于临界值会开始行动异常",
                "恢复方式": ["睡眠", "吃精神类食物", "看科学装置"],
                "下降原因": ["在黑暗中", "看到怪物", "饥饿"]
            },
            "饥饿值": {
                "desc": "玩家能量等级",
                "恢复方式": ["吃食物"],
                "影响": "低于0会开始掉血"
            }
        }
        return mechanics_db.get(keyword, {"error": "未找到相关机制"})

# ========== 5. RAG 聊天机器人 ==========
class DontStarveChatBot:
    """整合 RAG + 多轮对话 + 第三方 API 的聊天机器人"""
    
    def __init__(self, api_key: str, kb_dir: str = None, 
                 db_dir: str = None):
        self.api_key = api_key
        _timeout = httpx.Timeout(45.0, connect=10.0) if HAS_HTTPX else 45.0
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://open.bigmodel.cn/api/paas/v4/",
            timeout=_timeout,
            max_retries=0,
        )
        
        # 设置绝对路径（基于脚本所在目录）
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if kb_dir is None:
            kb_dir = os.path.join(base_dir, "knowledge_base")
        if db_dir is None:
            db_dir = os.path.join(base_dir, "backend", "chroma_db")
        
        # 初始化组件
        self.embedding_service = EmbeddingService(api_key)
        self.kb = KnowledgeBase(db_dir, self.embedding_service)
        self.db = ChatDatabase()
        self.third_party = ThirdPartyAPIs()
        
        # 初始化领域微调适配器
        self.fine_tuning_adapter = FineTuningAdapter()
        
        # 加载知识库文档
        self._load_knowledge_base()
    
    def _load_knowledge_base(self):
        """从文件加载知识库文档（并行嵌入，API 不可用时跳过）"""
        import time as _time
        from concurrent.futures import ThreadPoolExecutor, as_completed

        t_start = _time.time()
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        kb_path = os.path.join(base_dir, "knowledge_base")

        if not os.path.exists(kb_path):
            print(f"⚠️ 知识库目录不存在: {kb_path}")
            print(f"💡 请运行初始化: python backend/init_knowledge_base.py")
            return

        # 收集所有知识库文件
        kb_files = []
        for filename in sorted(os.listdir(kb_path)):
            if filename.endswith(('.txt', '.md')):
                kb_files.append(filename)

        if not kb_files:
            print("⚠️ 知识库目录为空，请运行初始化脚本")
            return

        print(f"📚 发现 {len(kb_files)} 个知识库文件，开始加载...")

        # 检查 ChromaDB 中是否已有文档
        existing_count = self.kb.get_doc_count()
        if existing_count > 0:
            print(f"   ChromaDB 中已有 {existing_count} 条记录，将只添加新文档")

        # Phase 1: 读取文件 + 检查是否需要嵌入（串行，本地 IO 很快）
        to_embed = []  # [(doc_id, content, metadata, filename)]
        skip_count = 0

        for filename in kb_files:
            filepath = os.path.join(kb_path, filename)
            doc_id = filename.replace('.', '_')

            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()

                if not content.strip():
                    continue

                # 检查是否已加载
                existing = self.kb.collection.get(ids=[doc_id])
                if existing and existing['ids']:
                    skip_count += 1
                    continue

                to_embed.append((doc_id, content,
                                 {'source': filename, 'type': 'guide'},
                                 filename))

            except Exception as e:
                print(f"   ⚠️ {filename}: 读取失败 ({e})")

        if not to_embed:
            if skip_count == len(kb_files):
                print(f"📊 所有 {skip_count} 个文件已加载，跳过")
            print(f"⏱ 知识库检查完成 (耗时 {_time.time() - t_start:.1f}s)")
            return

        # Phase 2: 并行嵌入（4 线程，大幅加速启动）
        print(f"   🔄 正在并行向量化 {len(to_embed)} 个新文件 (4 线程)...")
        success_count = 0
        fail_count = 0
        batch_ids = []
        batch_embeddings = []
        batch_metadatas = []
        batch_documents = []

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {}
            for doc_id, content, metadata, fname in to_embed:
                future = executor.submit(
                    self.embedding_service.embed_query, content
                )
                futures[future] = (doc_id, content, metadata, fname)

            for future in as_completed(futures):
                doc_id, content, metadata, fname = futures[future]
                try:
                    embedding = future.result(timeout=15)
                    batch_ids.append(doc_id)
                    batch_embeddings.append(embedding)
                    batch_metadatas.append(metadata)
                    batch_documents.append(content[:1000])
                    success_count += 1
                    print(f"   ✅ {fname}")
                except Exception as e:
                    fail_count += 1
                    print(f"   ❌ {fname} (嵌入失败: {e})")

        # Phase 3: 批量写入 ChromaDB（一次性，减少 IO）
        if batch_ids:
            try:
                self.kb.collection.add(
                    ids=batch_ids,
                    embeddings=batch_embeddings,
                    metadatas=batch_metadatas,
                    documents=batch_documents,
                )
            except Exception as e:
                print(f"   ⚠️ ChromaDB 批量写入失败: {e}")
                fail_count = len(to_embed)
                success_count = 0

        total = self.kb.get_doc_count()
        elapsed = _time.time() - t_start
        print(f"📊 知识库状态: 成功 {success_count} / 跳过 {skip_count} / 失败 {fail_count} / 总计 {total} 条")
        print(f"⏱ 知识库加载完成 (耗时 {elapsed:.1f}s)")

        if fail_count > 0:
            print(f"⚠️ 部分文档未能向量化（API 连接问题），RAG 功能可能受限")
            print(f"💡 解决网络问题后重启即可自动补充向量化")
    
    def _detect_intent(self, user_input: str) -> Dict:
        """
        意图识别与路由
        返回：{'type': 'rag'|'weather'|'mechanic'|'general', 'keywords': [...]}
        """
        keywords = {
            'weather': ['天气', '季节', '温度', '下雨'],
            'mechanic': ['机制', '属性', '怎么算', '伤害', '回复'],
            'building': ['建筑', '建造', '科技', '科学机制'],
            'survival': ['生存', '策略', '前期', '中期', '后期', '度过', '怎么过']
        }
        
        detected_types = []
        for key, kws in keywords.items():
            if any(kw in user_input for kw in kws):
                detected_types.append(key)
        
        return {
            'type': detected_types if detected_types else ['rag'],
            'query': user_input
        }
    
    def _format_rag_context(self, retrieved_docs: List[Dict]) -> tuple:
        """格式化 RAG 检索结果"""
        if not retrieved_docs:
            return "", []
        
        sources = []
        context = "【📚 参考知识库】\n"
        for doc in retrieved_docs:
            source = doc['metadata'].get('source', '未知')
            sources.append(source)
            context += f"\n**来自: {source}**\n"
            context += doc['content'][:500] + "...\n" if len(doc['content']) > 500 else doc['content'] + "\n"
        
        return context, sources
    
    def chat(self, user_input: str, session_id: str) -> Dict:
        """
        核心对话方法 - 集成 RAG + 微调 + 多源数据
        返回：{'response': str, 'sources': List[str], 'apis_used': List[str]}
        """
        apis_used = []
        rag_context = ""
        sources = []
        
        # 1. 意图识别（使用微调适配器）
        intent = self._detect_intent(user_input)
        
        # 2. 准备优化的系统提示词（微调适配器）
        system_prompt, metadata = self.fine_tuning_adapter.prepare_request(user_input)
        
        # 3. RAG 检索（大多数问题都走 RAG）
        if 'rag' in intent['type'] or any(t in ['building', 'survival'] for t in intent['type']):
            retrieved_docs = self.kb.retrieve(user_input, k=3)
            rag_context, sources = self._format_rag_context(retrieved_docs)
        
        # 4. 第三方 API 调用（按需）
        extra_context = ""
        if 'weather' in intent['type']:
            weather = self.third_party.get_weather()
            apis_used.append("weather_api")
            extra_context += f"\n\n【⛅ 实时天气】\n城市: {weather['city']}, 温度: {weather['temp']}°C, 天气: {weather['weather']}\n"
        
        if 'mechanic' in intent['type']:
            # 提取关键词，如"理智值"、"饥饿值"等
            keywords = ['理智值', '饥饿值', '血量', '温度']
            for kw in keywords:
                if kw in user_input:
                    mechanic = self.third_party.search_game_mechanic(kw)
                    apis_used.append("game_mechanic_db")
                    extra_context += f"\n\n【⚙️ 游戏机制】\n{json.dumps(mechanic, ensure_ascii=False, indent=2)}\n"
        
        # 5. 构建完整提示词（使用微调后的系统提示词）
        full_prompt = f"{rag_context}\n{extra_context}\n\n【用户问题】\n{user_input}"
        
        # 6. 调用大模型（使用优化的系统提示词）
        try:
            messages = [
                {"role": "system", "content": system_prompt},  # 使用微调后的提示词
                {"role": "user", "content": full_prompt}
            ]
            
            response = self.client.chat.completions.create(
                model="glm-4-flash",
                messages=messages,
                temperature=0.7,
                max_tokens=4096
            )
            
            bot_response = response.choices[0].message.content
            
            # 7. 增强响应（微调适配器）
            enhanced_response = self.fine_tuning_adapter.enhance_response(
                bot_response, metadata
            )
            
        except Exception as e:
            enhanced_response = f"❌ 调用大模型失败: {str(e)}"
        
        # 8. 保存对话记录
        self.db.save_conversation(
            session_id=session_id,
            user_msg=user_input,
            bot_msg=enhanced_response,
            sources=sources,
            api_used=','.join(apis_used) if apis_used else None
        )
        
        return {
            'response': enhanced_response,
            'sources': sources,
            'apis_used': apis_used,
            'intent': intent['type']
        }
    
    def get_history(self, session_id: str) -> List[Dict]:
        """获取会话历史"""
        return self.db.get_conversation_history(session_id)

# ========== 6. Flask 应用 ==========
app = Flask(__name__)
CORS(app)

# 初始化机器人
bot = DontStarveChatBot(api_key=ZHIPU_API_KEY)

# 初始化 Agent 搜索封装器
from search_agent_wrapper import SearchAgentWrapper
search_agent = SearchAgentWrapper(api_key=ZHIPU_API_KEY)

# 初始化统一流水线（5 层架构）
from pipeline import Pipeline
pipeline = Pipeline(
    api_key=ZHIPU_API_KEY,
    knowledge_base=bot.kb,
    chat_db=bot.db,
    fine_tuning_adapter=bot.fine_tuning_adapter,
    search_agent_wrapper=search_agent,
)

# 初始化多模态路由器
from multimodal import MultimodalRouter
multimodal_router = MultimodalRouter()
print(f"   [Multimodal] 多模态路由器已就绪")

@app.route('/api/chat', methods=['POST'])
def chat_endpoint():
    """聊天端点"""
    data = request.json
    user_input = data.get('message', '')
    session_id = data.get('session_id', 'default')
    
    if not user_input.strip():
        return jsonify({'error': '消息不能为空'}), 400
    
    # 使用统一流水线（5 层架构）
    result = pipeline.run(user_input, session_id)
    return jsonify(result)


# ========== Agent 联网搜索接口 ==========

@app.route('/api/agent/search', methods=['POST'])
def agent_search_endpoint():
    """Agent 联网搜索 — 通过统一流水线"""
    data = request.json
    query = data.get('query', '')
    session_id = data.get('session_id', 'default')

    if not query.strip():
        return jsonify({'error': '搜索内容不能为空'}), 400

    result = pipeline.agent_search(query, session_id)
    return jsonify(result)


@app.route('/api/agent/history/<session_id>', methods=['GET'])
def agent_history_endpoint(session_id):
    """获取 Agent 搜索历史"""
    history = bot.db.get_agent_history(session_id)
    return jsonify({'history': history})


@app.route('/api/agent/history/<session_id>/<int:search_id>', methods=['GET'])
def agent_history_detail(session_id, search_id):
    """获取单条 Agent 搜索详情"""
    record = bot.db.get_agent_search(search_id)
    if not record:
        return jsonify({'error': '记录不存在'}), 404
    return jsonify(record)


@app.route('/api/memory/<session_id>', methods=['GET'])
def agent_memory_endpoint(session_id):
    """获取 Agent 记忆"""
    memory = bot.db.get_agent_memory(session_id)
    return jsonify({'memory': memory})


@app.route('/api/history/<session_id>', methods=['GET'])
def get_history_endpoint(session_id):
    """获取会话历史"""
    history = bot.get_history(session_id)
    return jsonify({'history': history})

@app.route('/api/knowledge-base-status', methods=['GET'])
def kb_status():
    """知识库状态"""
    return jsonify({
        'doc_count': bot.kb.get_doc_count(),
        'status': '✅ 就绪' if bot.kb.get_doc_count() > 0 else '⚠️ 文档缺失'
    })

@app.route('/health', methods=['GET'])
def health():
    """健康检查"""
    return jsonify({'status': 'ok'})


# ========== 多模态接口 ==========
import base64
import os
import tempfile

ALLOWED_IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp'}
ALLOWED_AUDIO_EXTENSIONS = {'.wav', '.mp3', '.m4a', '.ogg', '.flac', '.webm', '.mp4'}


@app.route('/api/multimodal/parse', methods=['POST'])
def multimodal_parse_endpoint():
    """
    多模态解析 — 上传图片/语音，返回结构化的文本描述

    Request: multipart/form-data
      - file: 图片或音频文件
      - type: 'image' | 'audio' (可选，自动检测)
      - caption: 附加文本说明（可选）

    Response:
      {
        'text_prompt': str,       # 解析后的统一文本
        'input_type': str,        # 原始输入类型
        'parsed_info': {...},     # 解析详情
        'success': bool,
        'engine': str,
      }
    """
    if 'file' not in request.files:
        return jsonify({'error': '未提供文件', 'success': False}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '文件名为空', 'success': False}), 400

    # 检测文件类型
    ext = os.path.splitext(file.filename)[1].lower()
    input_type = request.form.get('type', '')

    if not input_type:
        if ext in ALLOWED_IMAGE_EXTENSIONS:
            input_type = 'image'
        elif ext in ALLOWED_AUDIO_EXTENSIONS:
            input_type = 'audio'
        else:
            # 尝试作为文本处理
            input_type = 'text'

    user_caption = request.form.get('caption', '')

    try:
        # 保存上传的文件到临时目录
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            file.save(tmp.name)
            temp_path = tmp.name

        # 构建路由输入
        route_input = {
            'type': input_type,
            'image_path' if input_type == 'image' else 'audio_path': temp_path,
        }
        if user_caption:
            route_input['text'] = user_caption

        # 路由解析
        result = multimodal_router.route(route_input)

        # 清理临时文件
        try:
            os.unlink(temp_path)
        except Exception:
            pass

        return jsonify(result)

    except Exception as e:
        return jsonify({
            'text_prompt': f'[解析失败: {str(e)}]',
            'input_type': input_type,
            'success': False,
            'engine': 'error',
            'parsed_info': {},
        }), 500


@app.route('/api/multimodal/chat', methods=['POST'])
def multimodal_chat_endpoint():
    """
    多模态聊天 — 上传图片/语音 + 可选文字 → 完整 pipeline 回答

    Request: multipart/form-data
      - file: 图片或音频文件（可选，如果只有文字则发 /api/chat）
      - type: 'image' | 'audio' | 'text'
      - message: 附加文本说明（可选）
      - session_id: 会话 ID

    Response:
      {
        'response': str,
        'input_type': str,
        'parsed_info': {...},
        'sources': [...],
        'engine': str,
        ...
      }
    """
    session_id = request.form.get('session_id', 'default')
    user_message = request.form.get('message', '')
    input_type = request.form.get('type', 'text')

    # 文本模式 — 直接走 pipeline
    if input_type == 'text' or 'file' not in request.files:
        if not user_message.strip():
            return jsonify({'error': '消息不能为空'}), 400
        result = pipeline.run(user_message, session_id)
        result['input_type'] = 'text'
        return jsonify(result)

    # 多模态模式
    file = request.files['file']
    ext = os.path.splitext(file.filename)[1].lower() if file.filename else ''

    # 自动检测类型
    if input_type == 'image' or ext in ALLOWED_IMAGE_EXTENSIONS:
        input_type = 'image'
    elif input_type == 'audio' or ext in ALLOWED_AUDIO_EXTENSIONS:
        input_type = 'audio'

    try:
        # 保存文件
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            file.save(tmp.name)
            temp_path = tmp.name

        # 多模态路由
        route_input = {
            'type': input_type,
            'image_path' if input_type == 'image' else 'audio_path': temp_path,
        }
        if user_message:
            route_input['text'] = user_message

        route_result = multimodal_router.route(route_input)

        # 清理
        try:
            os.unlink(temp_path)
        except Exception:
            pass

        text_prompt = route_result.get('text_prompt', '')

        if not text_prompt.strip():
            return jsonify({
                'response': f'⚠️ 未能从{input_type}中提取有效内容，请尝试用文字描述',
                'input_type': input_type,
                'parsed_info': route_result.get('parsed_info', {}),
                'sources': [],
                'engine': route_result.get('engine', 'unknown'),
            })

        # 注入游戏上下文到 pipeline
        game_context = route_result.get('extra_context', '')
        if game_context:
            text_prompt = f"{text_prompt}\n\n[游戏场景提示] {game_context}"

        # 走完整 pipeline
        result = pipeline.run(text_prompt, session_id)

        # 附加多模态元信息
        result['input_type'] = input_type
        result['parsed_info'] = route_result.get('parsed_info', {})
        result['multimodal_engine'] = route_result.get('engine', 'unknown')

        return jsonify(result)

    except Exception as e:
        return jsonify({
            'response': f'❌ 多模态处理失败: {str(e)}',
            'input_type': input_type,
            'success': False,
        }), 500


@app.route('/api/multimodal/status', methods=['GET'])
def multimodal_status_endpoint():
    """多模态模块状态"""
    try:
        from multimodal.image_parser import ImageParser
        from multimodal.speech_to_text import SpeechToText
        img_parser = ImageParser()
        img_ok = img_parser._load_model()
        stt = SpeechToText()
        audio_ok = stt._load_model()
    except Exception:
        img_ok = False
        audio_ok = False

    return jsonify({
        'image_parser': '✅ BLIP 就绪' if img_ok else '⚠️ 模拟模式（pip install transformers pillow torch）',
        'speech_to_text': '✅ Whisper 就绪' if audio_ok else '⚠️ 模拟模式（pip install openai-whisper）',
        'router': '✅ 就绪',
    })

if __name__ == '__main__':
    print("🎮 饥荒游戏攻略助手 - 后端启动")
    print(f"📚 知识库状态: {bot.kb.get_doc_count()} 条记录")
    # START_ALL.py 统一启动时设 FLASK_NO_RELOAD=1，避免 reloader 导致模型加载两遍
    use_reloader = os.environ.get('FLASK_NO_RELOAD', '0') != '1'
    debug_mode = os.environ.get('FLASK_DEBUG', '1') != '0'
    app.run(debug=debug_mode, port=5000, use_reloader=use_reloader)