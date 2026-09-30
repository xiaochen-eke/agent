# 饥荒（Don't Starve）游戏攻略助手 — 项目报告

## 一、项目概述

- 项目名称：饥荒游戏攻略助手（dont_starve_bot）
- 主要功能：基于 RAG（检索增强生成）为玩家提供场景化、生存策略与配方建议；支持多轮对话与会话持久化；可接入第三方 API（天气、游戏百科）以增强上下文。

## 二、系统架构（Mermaid 图）

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
  style KB fill:#f9f,stroke:#333,stroke-width:1px
  style DB fill:#ffe,stroke:#333,stroke-width:1px
```

（说明：若需导出为图片，请使用 Mermaid 渲染工具或在线渲染器将上述 Mermaid 源码生成 PNG/SVG。）

## 三、关键模块与代码摘录

- 后端入口：`dont_starve_bot/backend/app.py`（核心职责：HTTP 接口、机器人初始化、健康检查）

### 代码摘录：Flask 端点与机器人初始化

```python
app = Flask(__name__)
CORS(app)

# 初始化机器人
bot = DontStarveChatBot(api_key=ZHIPU_API_KEY)

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

### 代码摘录：RAG + 聊天逻辑（摘要）

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

（完整代码见 `dont_starve_bot/backend/app.py`）

## 四、运行与部署步骤

本节假设在 Windows 或类 Unix 环境，Python 3.8+ 已安装。

1. 克隆仓库并进入项目根目录：

```bash
git clone <repo-url>
cd <repo-root>
```

2. 创建虚拟环境并安装依赖：

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
pip install -r dont_starve_bot/requirements_report.txt
```

3. 配置环境变量（可选）：

- `ZHIPU_API_KEY`：大模型/Embedding 服务的 API Key（已在代码中示例写为常量，生产环境请用环境变量替换）。

4. 启动后端：

```bash
python dont_starve_bot/backend/app.py
```

5. 调用示例：

```bash
curl -X POST http://127.0.0.1:5000/api/chat -H "Content-Type: application/json" \
  -d '{"session_id": "s1", "message": "如何做肉丸？"}'
```

## 五、已知限制与改进建议

- 当前知识库加载仅支持 `.md`/`.txt` 文档，建议添加批量导入与定时更新功能。
- 模型调用使用同步阻塞方式，生产环境建议改为异步并添加重试和熔断策略。
- 建议将 `ZHIPU_API_KEY` 等密钥迁移至安全存储（如 Vault / 环境变量）并避免硬编码。

## 六、交付物

- 本报告（Markdown）: `dont_starve_bot/report.md`
- 将 Markdown 转为 Word 的脚本: `dont_starve_bot/scripts/convert_to_docx.py`
- 运行依赖文件: `dont_starve_bot/requirements_report.txt`

---
如果你希望我现在直接生成 `docx` 文件，我可以尝试在当前环境运行脚本来创建它（需安装 `python-docx`）。
