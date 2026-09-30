# 饥荒（Don't Starve）游戏攻略助手 — 最终报告

## 一、项目概述

- 项目名称：饥荒游戏攻略助手（dont_starve_bot）
- 主要功能：基于 RAG（检索增强生成）为玩家提供场景化、生存策略与配方建议；支持多轮对话与会话持久化；可接入第三方 API（天气、游戏百科）以增强上下文。

## 二、系统架构

系统由前端（玩家界面）、Flask 后端、RAG 组件（EmbeddingService + KnowledgeBase）、向量数据库（ChromaDB）、会话数据库（SQLite）与第三方 API（天气、百科）构成：

```mermaid
flowchart LR
  Client[玩家 / 前端]
  Client -->|HTTP POST /api/chat| FlaskAPI[Flask 后端]
  FlaskAPI --> Bot[DontStarveChatBot]
  Bot --> KB[KnowledgeBase (ChromaDB)]
  Bot --> Embedding[EmbeddingService (OpenAI/BigModel)]
  Bot --> DB[ChatDatabase (SQLite)]
  Bot --> ThirdParty[ThirdPartyAPIs]
  Bot --> LLM[OpenAI/大模型 API]
```

## 三、关键模块说明与代码摘录

- 后端入口：dont_starve_bot/backend/app.py（核心职责：HTTP 接口、机器人初始化、健康检查）

### Flask 端点（摘录）

```python
@app.route('/api/chat', methods=['POST'])
def chat_endpoint():
    data = request.json
    user_input = data.get('message', '')
    session_id = data.get('session_id', 'default')
    if not user_input.strip():
        return jsonify({'error': '消息不能为空'}), 400
    result = bot.chat(user_input, session_id)
    return jsonify(result)
```

### RAG 与对话流程（摘录）

```python
class DontStarveChatBot:
    def __init__(self, api_key: str, kb_dir: str = None, db_dir: str = None):
        self.embedding_service = EmbeddingService(api_key)
        self.kb = KnowledgeBase(db_dir, self.embedding_service)
        self.db = ChatDatabase()
        self.third_party = ThirdPartyAPIs()
        self._load_knowledge_base()

    def chat(self, user_input: str, session_id: str) -> Dict:
        intent = self._detect_intent(user_input)
        retrieved_docs = self.kb.retrieve(user_input, k=3)
        rag_context, sources = self._format_rag_context(retrieved_docs)
        full_prompt = f"{rag_context}\n\n【用户问题】\n{user_input}"
        response = self.client.chat.completions.create(...)
        self.db.save_conversation(...)
        return {...}
```

## 四、运行与部署（快速指南）

1. 进入项目根目录：

```bash
cd <repo-root>
```

2. 创建虚拟环境并安装依赖：

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
pip install -r dont_starve_bot/requirements_report.txt
```

3. 启动服务：

```bash
python dont_starve_bot/backend/app.py
```

4. 测试示例：

```bash
curl -X POST http://127.0.0.1:5000/api/chat -H "Content-Type: application/json" \
  -d '{"session_id": "s1", "message": "如何做肉丸？"}'
```

## 五、已知限制与改进建议

- 知识库仅支持 `.md`/`.txt` 文档，建议添加批量导入与定时更新功能。
- 模型调用使用同步阻塞方式，建议改为异步并添加重试与熔断策略。
- 请将 `ZHIPU_API_KEY` 等密钥从代码中移出，使用环境变量或密钥管理服务。

## 六、附录 — 知识库节选：怪物信息

以下节选自知识库文件：dont_starve_bot/knowledge_base/怪物.md

```markdown
# 饥荒联机版 怪物信息
## 蜘蛛
- 血量：100
- 伤害：10
- 掉落：蜘蛛丝、蜘蛛腺体、怪物肉
- 打法：站撸2下，走位躲攻击，循环

## 蜘蛛战士
- 血量：200
- 伤害：20
- 掉落：蜘蛛丝、腺体、怪物肉
- 打法：保持距离，打2走1

## 青蛙
- 血量：100
- 伤害：10
- 特点：会偷物品
- 打法：快速击杀，避免围殴

## 猎犬
- 血量：150
- 伤害：20
- 特点：定期成群来袭
- 打法：穿甲站撸，或引到触手旁

## 火猎犬
- 血量：100
- 伤害：30
- 特点：死亡爆炸，点燃周围
- 打法：远离易燃物击杀

## 冰猎犬
- 血量：100
- 伤害：20
- 特点：死亡冰冻周围
- 打法：单独处理，避免被冻

## 巨鹿
- 季节：冬季
- 血量：2000
- 伤害：75
- 特点：破坏建筑极强
- 掉落：大肉×8，巨鹿眼球
- 打法：卡位绕树，穿木甲+火腿棒

## 龙蝇
- 季节：夏季
- 血量：2750
- 伤害：150
- 特点：会自燃，范围伤害
- 掉落：大肉×8，龙鳞
- 打法：石头墙卡位，多人配合

## 熊獾
- 季节：秋季
- 血量：1500
- 伤害：50
- 特点：偷吃食物，拍飞建筑
- 掉落：大肉×8，厚毛
- 打法：打4走1

## 鹿鹅
- 季节：春季
- 血量：1000
- 伤害：40
- 特点：群体攻击，会眩晕
- 掉落：大肉×6，羽毛×4
- 打法：先杀小的，再杀大的
```
