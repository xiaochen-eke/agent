# 🚀 快速启动指南

## 📋 启动方式总览

我为你创建了三种启动脚本，选择最适合你的方式：

| 脚本 | 系统 | 使用方式 | 特点 |
|-----|------|--------|------|
| **START.bat** | Windows | 双击运行 | 最简单，无需配置 |
| **START.ps1** | Windows (PowerShell) | 右键运行 | 彩色输出，功能全 |
| **START.py** | 全平台 | `python START.py` | 跨平台，功能最全 |

---

## 🎯 方式一：Batch 脚本（最简单）

**适合：** Windows 用户，想要最快速启动

### 使用步骤：

1. **双击运行** `START.bat` 文件
2. 系统会自动：
   - ✅ 初始化知识库
   - ✅ 启动后端服务
   - ✅ 打开日志窗口

### 屏幕效果：
```
╔════════════════════════════════════════════════════════╗
║     🎮 饥荒游戏攻略AI助手 - 一键启动                   ║
╚════════════════════════════════════════════════════════╝

✅ 项目检测成功

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📚 第1步：初始化知识库...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ 创建知识库文件: game_basics.md
✅ 创建知识库文件: survival_guide.md
...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🚀 第2步：启动后端服务...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

 * Running on http://localhost:5000
```

---

## 🎯 方式二：PowerShell 脚本（功能全）

**适合：** Windows PowerShell 用户，需要高级功能

### 使用步骤：

1. **以管理员身份打开 PowerShell**
2. **运行脚本：**
   ```powershell
   cd C:\DLdata\git\dont_starve_bot
   .\START.ps1
   ```

### 高级选项：

```powershell
# 基础启动
.\START.ps1

# 跳过知识库初始化（已有时使用）
.\START.ps1 -SkipKB

# 启动前运行测试
.\START.ps1 -RunTests

# 组合使用
.\START.ps1 -RunTests -SkipKB
```

### 彩色输出示例：
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📚 第1步：初始化知识库...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ 创建知识库文件: game_basics.md
✅ 创建知识库文件: survival_guide.md
...

💡 提示：
  • 后端运行在 http://localhost:5000
  • 按 Ctrl+C 停止服务
  • 新开终端运行:
    - 测试 Agent: python Agent/search_agent.py
    - 运行测试: python test_integration.py
```

---

## 🎯 方式三：Python 脚本（跨平台）

**适合：** macOS、Linux 用户，或需要最大灵活性

### 使用步骤：

1. **打开终端**
2. **运行脚本：**
   ```bash
   cd /c/DLdata/git/dont_starve_bot  # 适配你的路径
   python START.py
   ```

### 命令行选项：

```bash
# 基础启动
python START.py

# 跳过知识库初始化
python START.py --skip-kb

# 启动前运行测试
python START.py --run-tests

# 组合使用
python START.py --run-tests --skip-kb

# 查看帮助
python START.py -h
```

### 输出示例：
```
════════════════════════════════════════════════════════
  🎮 饥荒游戏攻略AI助手 - 一键启动
════════════════════════════════════════════════════════

📍 项目目录: C:\DLdata\git\dont_starve_bot

检查项目结构:
  ✅ 后端目录              backend/
  ✅ Agent目录             Agent/
  ⚠️ 知识库目录            knowledge_base/ (将创建)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📍 第1步：初始化知识库
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ 创建知识库文件: game_basics.md
✅ 创建知识库文件: survival_guide.md
...

🌐 后端地址: http://localhost:5000
📚 知识库路径: C:\DLdata\git\dont_starve_bot\backend\knowledge_base
```

---

## ✅ 成功启动的标志

当看到以下信息时，说明启动成功：

```
 * Running on http://localhost:5000
 * Debug mode: on
```

或者访问 http://localhost:5000/health 返回：
```json
{"status": "ok"}
```

---

## 🧪 启动后的操作

### 1️⃣ 测试 API（任选一种）

**方式 A：使用 curl**
```bash
curl -X POST http://localhost:5000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "冬季怎么生存？", "session_id": "test"}'
```

**方式 B：使用 Python**
```python
import requests
response = requests.post(
    "http://localhost:5000/api/chat",
    json={"message": "冬季怎么生存？", "session_id": "test"}
)
print(response.json())
```

**方式 C：使用 Postman**
- 打开 Postman
- 选择 POST 方法
- URL: `http://localhost:5000/api/chat`
- 在 Body (raw JSON) 中输入：
```json
{
  "message": "冬季怎么生存？",
  "session_id": "test"
}
```

### 2️⃣ 测试 Agent 搜索

**新开一个终端，运行：**
```bash
cd dont_starve_bot
python Agent/search_agent.py
```

然后在交互式界面中输入：
```
你: 搜索最新的Python教程
[Tool] 🔍 web_search(搜索最新的Python教程)
Agent: 【网页搜索结果】...
```

### 3️⃣ 查看知识库状态

```bash
curl http://localhost:5000/api/knowledge-base-status
```

返回：
```json
{
  "doc_count": 5,
  "status": "✅ 就绪"
}
```

### 4️⃣ 获取对话历史

```bash
curl http://localhost:5000/api/history/test
```

---

## ❌ 故障排除

### 问题 1：找不到 Python

**解决：** 确保 Python 已安装并在系统路径中
```bash
python --version
```

### 问题 2：Permission Denied (PowerShell)

**解决：** 以管理员身份运行 PowerShell，或修改执行策略
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### 问题 3：端口 5000 已被占用

**解决：** 
- Windows: `netstat -ano | findstr :5000`
- Linux/Mac: `lsof -i :5000`

然后结束占用该端口的进程

### 问题 4：知识库初始化失败

**解决：** 手动初始化
```bash
cd backend
python init_knowledge_base.py
```

### 问题 5：API 调用返回 404

**解决：** 检查后端是否正常运行
```bash
curl http://localhost:5000/health
# 应返回 {"status": "ok"}
```

---

## 📊 启动配置对比

| 功能 | Batch | PowerShell | Python |
|-----|-------|-----------|--------|
| 双击启动 | ✅ | ❌ | ❌ |
| 跳过初始化 | ❌ | ✅ | ✅ |
| 自动测试 | ❌ | ✅ | ✅ |
| 彩色输出 | ❌ | ✅ | ✅ |
| 跨平台 | ❌ | ❌ | ✅ |
| 日志记录 | ❌ | ❌ | ✅ |
| 错误处理 | 基础 | 完整 | 完整 |

---

## 💡 最佳实践

### 首次启动：
```bash
python START.py --run-tests
```
这会运行完整测试，确保系统正常。

### 日常启动：
```bash
python START.py --skip-kb
```
跳过知识库初始化以加快启动。

### 故障排查：
```bash
python START.py --run-tests
```
运行测试以诊断问题。

---

## 📁 文件位置

```
dont_starve_bot/
├── START.bat           ← Windows Batch 脚本
├── START.ps1           ← PowerShell 脚本
├── START.py            ← Python 脚本（推荐）
├── backend/
│   ├── app.py          ← 主应用
│   ├── init_knowledge_base.py
│   ├── fine_tuning_adapter.py
│   └── knowledge_base/  ← 知识库文件夹
├── Agent/
│   └── search_agent.py  ← Agent 脚本
└── test_integration.py  ← 测试脚本
```

---

## 🎓 相关文档

- **完整系统文档**: [SYSTEM_README.md](SYSTEM_README.md)
- **完成总结**: [../COMPLETION_SUMMARY.md](../COMPLETION_SUMMARY.md)
- **系统架构**: 查看 SYSTEM_README.md 中的架构图

---

## 🆘 需要帮助？

1. **查看日志**: `startup.log` 文件（Python 脚本生成）
2. **运行测试**: `python test_integration.py`
3. **查看文档**: 阅读 `SYSTEM_README.md`
4. **检查配置**: 确保 `ZHIPU_API_KEY` 已设置

---

**提示：** 推荐使用 Python 脚本 (`START.py`)，因为功能最完整且跨平台！

✨ 现在就开始启动吧！🚀
