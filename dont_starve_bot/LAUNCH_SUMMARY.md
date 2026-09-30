# ✅ 一键启动脚本完成总结

## 🎉 已创建的启动脚本

我为你创建了 **3 种启动方式** + **2 份快速参考文档**，选择最适合你的：

### 📦 启动脚本清单

| 文件 | 类型 | 系统 | 使用方式 | 推荐度 |
|-----|-----|-----|--------|------|
| **START.py** | Python | 全平台 | `python START.py` | ⭐⭐⭐⭐⭐ |
| **START.ps1** | PowerShell | Windows | `.\START.ps1` | ⭐⭐⭐⭐ |
| **START.bat** | Batch | Windows | 双击运行 | ⭐⭐⭐ |
| QUICKSTART.md | 文档 | - | 详细指南 | - |
| QUICK_REFERENCE.md | 文档 | - | 快速参考 | - |

---

## 🚀 快速开始（选一种）

### 方式 A：最推荐 👍（Python 脚本）

```bash
cd C:\DLdata\git\dont_starve_bot
python START.py
```

**特点：**
- ✅ 跨平台（Windows/Mac/Linux）
- ✅ 功能最全
- ✅ 自动检查项目结构
- ✅ 完整的日志记录
- ✅ 支持高级选项

**高级选项：**
```bash
python START.py --skip-kb              # 跳过知识库初始化
python START.py --run-tests            # 启动前运行测试
python START.py --run-tests --skip-kb  # 两者都做
```

### 方式 B：最简单（Batch 脚本）

```
双击：START.bat
```

**特点：**
- ✅ 零配置
- ✅ 双击即可运行
- ✅ 适合首次使用者
- ❌ 功能较简单

### 方式 C：功能全（PowerShell 脚本）

```powershell
.\START.ps1
.\START.ps1 -RunTests
.\START.ps1 -SkipKB
```

**特点：**
- ✅ 彩色输出
- ✅ 功能完整
- ✅ 高级选项丰富
- ✅ Windows 原生

---

## ✨ 启动脚本的功能

### 自动执行的步骤

```
START.py / START.ps1 / START.bat
    │
    ├─→ 📍 检查项目结构
    │   ├─ ✅ backend/
    │   ├─ ✅ Agent/
    │   └─ ⚠️ knowledge_base/ (不存在时创建)
    │
    ├─→ 📚 初始化知识库 (可跳过)
    │   ├─ game_basics.md
    │   ├─ survival_guide.md
    │   ├─ advanced_tactics.md
    │   ├─ recipe_database.md
    │   └─ seasonal_guide.md
    │
    ├─→ 🧪 运行测试 (可选)
    │   ├─ 知识库初始化测试
    │   ├─ 意图识别测试
    │   ├─ 实体提取测试
    │   ├─ 提示词优化测试
    │   ├─ 响应格式化测试
    │   ├─ 完整流程测试
    │   └─ Web搜索测试
    │
    └─→ 🚀 启动后端服务
        └─ http://localhost:5000
```

---

## 📊 启动时间预期

| 步骤 | 耗时 | 说明 |
|-----|------|------|
| 项目检查 | <1s | 快速 |
| 知识库初始化 | 2-5s | 首次启动 |
| 知识库初始化（跳过） | <1s | 使用 --skip-kb |
| 集成测试 | 5-10s | 使用 --run-tests |
| 后端启动 | 2-3s | 加载模型和数据库 |
| **总计（首次）** | **~15s** | 完整初始化 |
| **总计（日常）** | **~5s** | 使用 --skip-kb |

---

## 🎯 使用场景

### 场景 1：首次启动
```bash
python START.py --run-tests
# 完整初始化 + 全部测试，确保系统正常
```

### 场景 2：日常启动
```bash
python START.py --skip-kb
# 快速启动，跳过知识库初始化
```

### 场景 3：故障排查
```bash
python START.py --run-tests
# 运行完整测试，诊断问题
```

### 场景 4：最快启动
```bash
START.bat
# 双击运行（仅 Windows）
```

---

## ✅ 成功启动的标志

看到以下信息说明一切正常：

```
════════════════════════════════════════════════════════
✅ 项目检测成功

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📚 第1步：初始化知识库...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ 创建知识库文件: game_basics.md
✅ 创建知识库文件: survival_guide.md
✅ 创建知识库文件: advanced_tactics.md
✅ 创建知识库文件: recipe_database.md
✅ 创建知识库文件: seasonal_guide.md
✅ 知识库加载完成，共 5 条记录

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🚀 第2步：启动后端服务...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 提示：
  • 后端运行在 http://localhost:5000
  • API 文档: http://localhost:5000/api/chat
  • 按 Ctrl+C 停止服务
  • 新开终端运行:
    - 测试 Agent: python Agent/search_agent.py
    - 运行测试: python test_integration.py

 * Running on http://localhost:5000
 * Debug mode: on
```

---

## 🔍 启动脚本的工作原理

### Python 脚本（START.py）详细流程

```python
Launcher 类
├── __init__()
│   └─ 初始化路径和配置
│
├── check_project_structure()
│   ├─ 检查 backend/ 目录
│   ├─ 检查 Agent/ 目录
│   └─ 检查 knowledge_base/ 目录
│
├── init_knowledge_base()
│   ├─ 检查 --skip-kb 标志
│   ├─ 运行 init_knowledge_base.py
│   └─ 生成 5 份知识库文档
│
├── run_tests()
│   └─ 运行 test_integration.py
│
├── start_backend()
│   ├─ 显示系统信息
│   ├─ 切换到 backend/ 目录
│   ├─ 运行 app.py
│   └─ 监听 Ctrl+C 信号
│
└── run()
    └─ 主流程：检查 → 初始化 → 测试 → 启动
```

---

## 📋 启动脚本的特性对比

| 特性 | START.py | START.ps1 | START.bat |
|-----|---------|---------|---------|
| 项目检查 | ✅ | ✅ | ✅ |
| 知识库初始化 | ✅ | ✅ | ✅ |
| 错误处理 | ✅✅✅ | ✅✅ | ✅ |
| 日志记录 | ✅ | ❌ | ❌ |
| 命令行选项 | ✅ | ✅ | ❌ |
| 自动测试 | ✅ | ✅ | ❌ |
| 彩色输出 | ✅ | ✅ | ❌ |
| 跨平台 | ✅ | ❌ | ❌ |
| 双击运行 | ❌ | ❌ | ✅ |

---

## 🎓 附加功能

### 日志记录（Python 脚本）

启动脚本会在项目根目录生成 `startup.log`：

```bash
cat dont_starve_bot/startup.log
```

内容示例：
```
=== 启动日志 [2026-06-13 14:30:45.123456] ===
[2026-06-13 14:30:45.123456] 运行命令: ['python', 'init_knowledge_base.py'] (在 C:\DLdata\git\dont_starve_bot\backend)
[2026-06-13 14:30:47.456789] 运行命令: ['python', 'app.py'] (在 C:\DLdata\git\dont_starve_bot\backend)
```

---

## 📚 相关文档

- **完整系统文档**: `SYSTEM_README.md`（1500+ 字）
- **快速启动指南**: `QUICKSTART.md`（详细步骤）
- **快速参考**: `QUICK_REFERENCE.md`（速查表）
- **完成总结**: `COMPLETION_SUMMARY.md`（系统架构图）

---

## 🛠️ 常见问题

### Q1：Python 版本要求？
**A:** Python 3.8+ （推荐 3.10+）

### Q2：可以同时运行多个启动脚本吗？
**A:** 不建议。每个启动脚本都会尝试在 5000 端口启动后端。

### Q3：如何修改启动端口？
**A:** 编辑 `backend/app.py` 的最后一行：
```python
app.run(debug=True, port=5001)  # 改为 5001
```

### Q4：启动很慢，怎么办？
**A:** 使用 `--skip-kb` 跳过知识库初始化：
```bash
python START.py --skip-kb
```

### Q5：如何后台运行？
**A:** 使用 `nohup` 或类似工具：
```bash
nohup python START.py > output.log 2>&1 &
```

---

## 🎁 额外便利

### 快捷方式建议（Windows）

右键创建快捷方式：

**选项 1：Batch 快捷方式**
- 目标: `C:\DLdata\git\dont_starve_bot\START.bat`
- 起始位置: `C:\DLdata\git\dont_starve_bot`

**选项 2：Python 快捷方式**
- 目标: `python C:\DLdata\git\dont_starve_bot\START.py`
- 起始位置: `C:\DLdata\git\dont_starve_bot`

---

## 📦 文件清单

```
dont_starve_bot/
├── START.py              ⭐ 推荐（Python 脚本）
├── START.ps1             ⭐ PowerShell 脚本
├── START.bat             ⭐ Batch 脚本
├── QUICKSTART.md         📖 详细指南
├── QUICK_REFERENCE.md    📖 快速参考
├── startup.log           📋 启动日志（自动生成）
├── backend/
│   ├── app.py
│   ├── init_knowledge_base.py
│   ├── fine_tuning_adapter.py
│   └── knowledge_base/    📚 知识库文件夹
├── Agent/
│   └── search_agent.py
└── test_integration.py
```

---

## 🎯 推荐工作流

```
1️⃣ 首次启动
   python START.py --run-tests
   ↓
   系统完整测试，确保一切正常

2️⃣ 日常启动
   python START.py --skip-kb
   ↓
   快速启动，5 秒内就绪

3️⃣ 测试功能
   新开终端1: curl http://localhost:5000/health
   新开终端2: python Agent/search_agent.py
   新开终端3: python test_integration.py

4️⃣ 停止服务
   原始终端中按 Ctrl+C
```

---

## ✨ 现在就开始！

**最简单的方式：**
```bash
python START.py
```

**或者（Windows）：**
```
双击 START.bat
```

然后在浏览器打开：`http://localhost:5000/health`

---

**🎮 一键启动已完成！享受 AI 饥荒攻略助手！** 🚀

版本：1.0.0  
更新时间：2026-06-13
