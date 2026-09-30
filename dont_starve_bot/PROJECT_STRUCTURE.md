# 📁 项目结构说明与故障排除

## 🏗️ 当前项目结构

```
C:\DLdata\git\
├── Agent/                         ← Agent 目录
│   ├── search_agent.py           ← 联网搜索 Agent
│   └── ... (其他文件)
│
├── dont_starve_bot/               ← 主项目目录
│   ├── START.py                  ← ⭐ 推荐启动脚本
│   ├── START.ps1                 ← PowerShell 启动脚本
│   ├── START.bat                 ← Batch 启动脚本
│   ├── CHECK_STRUCTURE.py        ← 结构诊断脚本 (新增)
│   ├── QUICKSTART.md             ← 快速开始指南
│   ├── QUICK_REFERENCE.md        ← 快速参考
│   ├── SYSTEM_README.md          ← 完整系统文档
│   ├── LAUNCH_SUMMARY.md         ← 启动脚本说明
│   │
│   ├── backend/                  ← 后端代码
│   │   ├── app.py               ← 主应用
│   │   ├── init_knowledge_base.py
│   │   ├── fine_tuning_adapter.py
│   │   ├── knowledge_base/      ← 知识库文件夹(自动创建)
│   │   │   ├── game_basics.md
│   │   │   ├── survival_guide.md
│   │   │   ├── advanced_tactics.md
│   │   │   ├── recipe_database.md
│   │   │   └── seasonal_guide.md
│   │   ├── chroma_db/           ← 向量数据库(自动创建)
│   │   ├── chat_history.db      ← 对话记录(自动创建)
│   │   └── ...
│   │
│   ├── test_integration.py       ← 集成测试脚本
│   ├── requirements.txt          ← Python 依赖
│   └── ...
│
└── ... (其他目录)
```

---

## ⚠️ 常见问题：Agent 目录未找到

### 问题描述
启动脚本提示：
```
❌ Agent目录              Agent/
❌ 项目结构检查失败
```

### 原因
Agent 目录在 `dont_starve_bot` 的**上级目录**中：
- ❌ 错误位置：`C:\DLdata\git\dont_starve_bot\Agent\`
- ✅ 正确位置：`C:\DLdata\git\Agent\`

### 解决方案（已修复）

**✅ 最新版本的启动脚本已自动处理此问题！**

修复包括：

#### 1️⃣ Python 脚本（START.py）
```python
# 自动检查两个位置
agent_dir = self.project_root.parent / 'Agent'  # 上级目录
if not agent_dir.exists():
    agent_dir = self.project_root / 'Agent'     # 本级目录
```

#### 2️⃣ PowerShell 脚本（START.ps1）
```powershell
# 自动检查两个位置
$agentPath = Join-Path (Split-Path -Parent $scriptPath) "Agent"
if (-not (Test-Path $agentPath)) {
    $agentPath = Join-Path $scriptPath "Agent"
}
```

---

## ✅ 诊断方法

### 方法 1：运行诊断脚本（推荐）

```bash
cd C:\DLdata\git\dont_starve_bot
python CHECK_STRUCTURE.py
```

输出示例：
```
════════════════════════════════════════════════════════
🔍 项目结构检查诊断
════════════════════════════════════════════════════════

📍 当前目录: C:\DLdata\git\dont_starve_bot
📍 项目根目录: C:\DLdata\git\dont_starve_bot

────────────────────────────────────────────────────────
检查项目结构
────────────────────────────────────────────────────────
✅ 后端目录            backend
✅ 知识库目录          knowledge_base
✅ 测试脚本            test_integration.py
✅ 启动脚本            START.py

────────────────────────────────────────────────────────
检查可选目录
────────────────────────────────────────────────────────
✅ Agent目录(上级)       ../Agent/

────────────────────────────────────────────────────────
检查 backend 子目录
────────────────────────────────────────────────────────
✅ app.py
✅ init_knowledge_base.py
✅ fine_tuning_adapter.py

────────────────────────────────────────────────────────
检查启动脚本
────────────────────────────────────────────────────────
✅ START.py
✅ START.ps1
✅ START.bat

════════════════════════════════════════════════════════
✅ 项目结构检查完成 - 所有必要文件都已找到！

🚀 现在可以启动系统:
   python START.py
════════════════════════════════════════════════════════
```

### 方法 2：手动检查

```bash
# 检查关键目录
ls C:\DLdata\git\backend\              # 应该看到 app.py
ls C:\DLdata\git\Agent\                # 应该看到 search_agent.py
ls C:\DLdata\git\dont_starve_bot\      # 应该看到 START.py
```

### 方法 3：在 PowerShell 中检查

```powershell
cd C:\DLdata\git\dont_starve_bot
Test-Path backend                  # 应返回 True
Test-Path ..\Agent                 # 应返回 True
Test-Path START.py                 # 应返回 True
```

---

## 🚀 现在启动系统

### 方式 1：自动处理（推荐）

启动脚本已自动修复，直接运行：

```bash
python START.py
```

脚本会自动：
- ✅ 检查 backend 目录
- ✅ 查找 Agent 目录（上级或本级）
- ✅ 标记 Agent 为可选（不找到也能启动）

### 方式 2：如果仍有问题

1. **先诊断**：
   ```bash
   python CHECK_STRUCTURE.py
   ```

2. **检查输出**：查看哪些文件缺失

3. **手动启动**（如果诊断通过）：
   ```bash
   cd backend
   python init_knowledge_base.py
   python app.py
   ```

---

## 📋 启动脚本变更日志

### 新增功能

✅ **自动 Agent 目录检测**
- 检查上级目录的 Agent
- 检查本级目录的 Agent
- 找不到时标记为可选（不影响启动）

✅ **改进的结构检查**
- 分离必要目录和可选目录
- 详细的检查反馈
- 不会因为 Agent 缺失而失败

✅ **新增诊断脚本**
- `CHECK_STRUCTURE.py`：快速诊断项目结构
- 详细的文件检查报告
- 清晰的错误信息

---

## 🔧 如果需要调整路径

### 编辑 START.py

如果你想修改路径检查逻辑：

```python
# 修改路径检查
required_dirs = {
    'backend': ('后端目录', self.project_root / 'backend'),
    'custom_dir': ('自定义目录', self.project_root / 'custom_dir'),
}

optional_dirs = {
    'Agent': ('Agent目录', agent_dir),
}
```

### 编辑 START.ps1

如果你想修改 PowerShell 脚本的路径：

```powershell
# 修改路径检查
$agentPath = Join-Path (Split-Path -Parent $scriptPath) "Agent"
if (-not (Test-Path $agentPath)) {
    $agentPath = Join-Path $scriptPath "Agent"
}
```

---

## 📊 启动流程图

```
START.py
  │
  ├─→ 检查项目结构
  │   ├─ ✅ backend/
  │   ├─ ⚠️ Agent/ (可选)
  │   └─ ⚠️ knowledge_base/ (将创建)
  │
  ├─→ 初始化知识库
  │   └─ 生成 5 份文档
  │
  ├─→ 运行测试 (可选)
  │   └─ 7 项全面测试
  │
  └─→ 启动后端
      └─ http://localhost:5000
```

---

## 🎯 快速操作

| 操作 | 命令 |
|-----|------|
| 诊断项目 | `python CHECK_STRUCTURE.py` |
| 启动系统 | `python START.py` |
| 带测试启动 | `python START.py --run-tests` |
| 快速启动 | `python START.py --skip-kb` |
| 查看完整文档 | 打开 `SYSTEM_README.md` |

---

## ❓ 常见问题

### Q1: 为什么找不到 Agent 目录？
A: Agent 在上级目录中。新版启动脚本已自动处理，无需操心。

### Q2: Agent 目录对启动有影响吗？
A: 没有。后端启动不需要 Agent。Agent 用于 Web 搜索测试。

### Q3: 如何使用 Agent？
A: 在新开的终端中运行：
```bash
python ../Agent/search_agent.py
```
或
```bash
python ../../Agent/search_agent.py
```

### Q4: 项目结构有问题怎么办？
A: 运行诊断脚本：
```bash
python CHECK_STRUCTURE.py
```

---

## 📝 项目文件完整清单

必要文件：
- ✅ backend/app.py
- ✅ backend/init_knowledge_base.py
- ✅ backend/fine_tuning_adapter.py
- ✅ START.py / START.ps1 / START.bat
- ✅ test_integration.py

可选文件：
- ⚠️ Agent/search_agent.py

自动生成文件：
- 📝 backend/knowledge_base/ (首次启动)
- 📝 backend/chat_history.db (首次启动)
- 📝 startup.log (启动时)

---

## 🎓 后续步骤

1. **诊断项目**
   ```bash
   python CHECK_STRUCTURE.py
   ```

2. **启动系统**
   ```bash
   python START.py
   ```

3. **测试功能**
   ```bash
   # 新开终端
   curl http://localhost:5000/health
   ```

4. **查看文档**
   ```bash
   cat SYSTEM_README.md
   cat QUICKSTART.md
   ```

---

**✨ 系统现已完全自动处理路径问题，放心启动！** 🚀

版本：2.0（已修复 Agent 目录检测）  
更新时间：2026-06-13
