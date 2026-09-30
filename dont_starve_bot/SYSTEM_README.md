# 🎮 饥荒游戏攻略AI助手系统 - 完整指南

## 系统架构概览

```
┌─────────────────────────────────────────────────────┐
│         用户查询 (WebSocket / HTTP)                  │
└──────────────┬──────────────────────────────────────┘
               │
        ┌──────▼──────────────────────┐
        │   领域微调适配器              │
        │ (意图识别 + 提示词优化)        │
        └──────┬──────────────────────┘
               │
        ┌──────┴───────────────────────────────┐
        │                                      │
    ┌───▼────┐                        ┌──────▼────┐
    │ RAG    │                        │ 联网搜索   │
    │检索库  │                        │ (Web API) │
    └────────┘                        └───────────┘
        │                                   │
        └──────────────┬────────────────────┘
                       │
            ┌──────────▼──────────┐
            │  大模型 API        │
            │ (智谱 GLM-5)        │
            └────────┬────────────┘
                     │
            ┌────────▼──────────┐
            │  响应增强器        │
            │(格式化 + 交叉引用)  │
            └────────┬──────────┘
                     │
            ┌────────▼──────────┐
            │ 数据库持久化       │
            │ (SQLite)          │
            └───────────────────┘
```

## 🚀 快速开始

### 1. 初始化知识库

```bash
cd dont_starve_bot/backend
python init_knowledge_base.py
```

这会创建以下知识库文件：
- `game_basics.md` - 游戏基础知识
- `survival_guide.md` - 生存指南
- `advanced_tactics.md` - 高级战术
- `recipe_database.md` - 完整配方数据库
- `seasonal_guide.md` - 四季攻略

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 运行后端服务

```bash
python app.py
```

服务会启动在 `http://localhost:5000`

## 📚 核心功能模块

### 1. RAG（检索增强生成）

**工作流程：**
```
用户查询 → 向量化 → 搜索知识库 → 检索相关文档 → 融合入提示词 → 模型生成
```

**关键特性：**
- 使用 ChromaDB 向量数据库
- 支持 Cosine 相似度检索
- 自动加载 knowledge_base 目录下的所有文档

**示例：**
```python
# 自动检索与"冬季生存"相关的文档
retrieved_docs = bot.kb.retrieve("冬季怎么生存", k=3)
# 返回top-3相关文档及相似度分数
```

### 2. Agent（智能体）- 联网搜索功能

**位置：** `Agent/search_agent.py`

**可用工具：**
- `search_files` - 按文件名搜索
- `search_content` - 搜索文件内容
- `search_images` - 搜索图片库
- `list_image_labels` - 列出图片分类
- `read_file` - 读取文件内容
- **`web_search`** - **联网搜索** ⭐ 新增

**Web Search 使用示例：**

```bash
python search_agent.py
```

交互式使用：
```
你: 搜索最新的Unity游戏开发教程
[Tool] 🔍 web_search(搜索最新的Unity游戏开发教程)
Agent: 【网页搜索结果】
查询词: 搜索最新的Unity游戏开发教程

1. Unity 2024 LTS 官方教程 - learn.unity.com
   Unity官方发布的最新教程...
   
2. 高级Unity开发指南 - YouTube频道
   涵盖最新特性和最佳实践...
```

**Web Search 工作原理：**
```python
# 使用智谱的 web_search 工具
result = call_zhipu_api(
    messages,
    model="glm-4-flash",
    tools=[{"type": "web_search", "web_search": {"enable": True}}]
)
```

### 3. 领域微调（Domain Fine-tuning）

**位置：** `dont_starve_bot/backend/fine_tuning_adapter.py`

**核心功能：**

#### a) 意图识别
```python
adapter.intent_recognizer.recognize("冬季怎么生存")
# 返回: ['survival_strategy', 'seasonal_prep']
```

支持的意图类型：
- `survival_strategy` - 生存策略
- `food_recipe` - 食物配方
- `building_craft` - 建筑制作
- `seasonal_prep` - 季节准备
- `boss_fight` - Boss战斗
- `mechanic_explain` - 机制解释
- `equipment_guide` - 装备指南

#### b) 实体提取
```python
adapter.intent_recognizer.extract_entities("冬季怎么对付黑手党")
# 返回:
# {
#   "seasons": ["winter"],
#   "bosses": ["黑手党"],
#   "items": [],
#   ...
# }
```

#### c) 提示词优化
根据意图自动添加上下文：
- 生存策略 → 添加"分阶段策略"上下文
- Boss战斗 → 添加"风险评估"上下文
- 食物配方 → 添加"营养属性对比"上下文

#### d) 响应增强
```python
enhanced_response = adapter.enhance_response(
    model_response,
    metadata
)
```

增强包括：
- 数值验证（检查属性值是否在合理范围）
- 术语标准化（自动转义网络用语）
- 格式化输出（根据意图调整格式）
- 交叉引用（添加相关内容链接）

### 4. 完整的工作流示例

**场景：用户问"冬季怎么生存"**

```python
# 1. 用户输入
user_input = "冬季怎么生存？"
session_id = "user_123"

# 2. 调用聊天方法
result = bot.chat(user_input, session_id)

# 内部流程：
# a) 意图识别 → ['survival_strategy', 'seasonal_prep']
# b) 实体提取 → seasons=['winter']
# c) RAG检索 → 从knowledge_base检索冬季相关文档
# d) 提示词优化 → 加入"分阶段策略"上下文
# e) 模型生成 → 调用GLM-5大模型
# f) 响应增强 → 格式化为结构化的季节攻略
# g) 保存记录 → 存入SQLite数据库

# 3. 返回结果
{
    'response': '【生存策略指南】(winter季节)\n...',
    'sources': ['seasonal_guide.md'],
    'apis_used': ['game_mechanic_db'],
    'intent': ['survival_strategy', 'seasonal_prep']
}
```

## 🔌 API 端点

### 聊天接口

**POST** `/api/chat`

```json
{
  "message": "冬季怎么生存",
  "session_id": "user_123"
}
```

**响应：**
```json
{
  "response": "【生存策略指南】(winter季节)\n...",
  "sources": ["seasonal_guide.md"],
  "apis_used": ["game_mechanic_db"],
  "intent": ["survival_strategy"]
}
```

### 历史记录

**GET** `/api/history/<session_id>`

返回该会话的所有对话历史

### 知识库状态

**GET** `/api/knowledge-base-status`

```json
{
  "doc_count": 5,
  "status": "✅ 就绪"
}
```

### 健康检查

**GET** `/health`

```json
{
  "status": "ok"
}
```

## 📖 使用示例

### 示例1：查询生存策略

```bash
curl -X POST http://localhost:5000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "我是新手，春季怎么生存？",
    "session_id": "player_1"
  }'
```

**响应格式：**
```
【生存策略指南】(spring季节)

Days 1-5：初期建立
- 第一天：砍树、采草、挖石头
- 建立营火（中心基地）
- 制作基础工具
- 建立简易围墙

...

【快速检查清单】
□ 已确认当前季节及温度
□ 已准备必要的防护装备
...
```

### 示例2：查询食物配方

```bash
curl -X POST http://localhost:5000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "肉丸怎么制作？需要什么材料？",
    "session_id": "player_1"
  }'
```

**系统会自动：**
1. 识别意图为 `food_recipe`
2. 从知识库检索配方相关文档
3. 使用优化的提示词强调"完整配方信息"
4. 返回格式化的配方数据

### 示例3：联网搜索（Agent）

```bash
python Agent/search_agent.py

你: 搜索 GPT-5 最新进展
[Tool] 🔍 web_search(搜索 GPT-5 最新进展)
Agent: 【网页搜索结果】
...最新信息...
```

## 🛠️ 配置与自定义

### 修改系统提示词

在 `app.py` 中修改 `SYSTEM_PROMPT` 变量：

```python
SYSTEM_PROMPT = """你是一位资深的《饥荒》攻略专家...
"""
```

### 添加新的意图类型

在 `fine_tuning_adapter.py` 的 `DomainIntentRecognizer` 类中添加：

```python
self.intent_patterns = {
    # ... 现有意图
    "custom_intent": [
        r"自定义正则表达式1",
        r"自定义正则表达式2",
    ],
}
```

### 自定义知识库文档

编辑 `init_knowledge_base.py`，添加新的文档：

```python
NEW_DOCUMENT = """# 新文档标题

## 内容...
"""

knowledge_files = {
    # ... 现有文档
    "new_document.md": NEW_DOCUMENT,
}
```

## 📊 性能优化

### 1. 向量数据库缓存

ChromaDB 自动缓存向量，后续查询速度更快

### 2. 模型温度设置

当前配置：`temperature=0.7`
- 更低值（0.3）：更稳定、更一致的回答
- 更高值（0.9）：更创意、更多样的回答

### 3. 批量嵌入

`EmbeddingService` 支持批量嵌入，减少API调用次数

```python
embeddings = embedding_service.embed_documents(texts, batch_size=16)
```

## 🐛 故障排除

### 问题：知识库为空

**解决方案：**
```bash
python init_knowledge_base.py
```

### 问题：API调用超时

**解决方案：**
- 增加超时时间
- 检查网络连接
- 验证API密钥

### 问题：Web搜索不工作

**解决方案：**
1. 检查智谱API是否支持web_search工具
2. 升级到最新版的SDK
3. 检查网络连接

## 📝 日志与调试

启用调试模式：

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

查看对话记录：

```bash
sqlite3 dont_starve_bot/backend/chat_history.db
SELECT * FROM conversations ORDER BY id DESC LIMIT 10;
```

## 🔐 安全与隐私

- ✅ 本地数据存储（SQLite）
- ✅ 支持会话隔离
- ✅ API密钥环境变量管理
- ✅ 敏感信息不会记录

## 📈 扩展方向

1. **多语言支持** - 支持英文、日文等
2. **视觉输入** - 支持游戏截图识别
3. **实时数据** - 集成游戏社区API
4. **离线模式** - 本地部署轻量级模型
5. **个性化学习** - 根据用户风格调整回答

## 📞 支持与反馈

- 遇到问题？提交Issue
- 有改进建议？讨论中提出
- 想贡献代码？提交Pull Request

---

**最后更新：** 2026-06-13  
**版本：** 2.0.0 - 联网搜索 + 领域微调版本
