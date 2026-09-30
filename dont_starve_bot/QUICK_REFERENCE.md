# 启动脚本使用快速参考

## � 项目检查（新增）

如果遇到路径问题，先运行诊断：
```bash
python CHECK_STRUCTURE.py
```

这会检查所有必要文件和目录。

---

## �🚀 三种启动方式

### 1️⃣ **最简单（Windows）**
```
双击：START.bat
```

### 2️⃣ **功能全（PowerShell）**
```powershell
.\START.ps1
.\START.ps1 -RunTests          # 带测试
.\START.ps1 -SkipKB            # 跳过知识库
.\START.ps1 -RunTests -SkipKB  # 两者都要
```

### 3️⃣ **最推荐（Python，跨平台）**
```bash
python START.py
python START.py --run-tests          # 带测试
python START.py --skip-kb            # 跳过知识库
python START.py --run-tests --skip-kb  # 两者都要
```

---

## ✅ 启动完成标志

看到这个说明成功：
```
 * Running on http://localhost:5000
```

## 🧪 启动后测试

**终端1（后端运行中）**
```
 * Running on http://localhost:5000
```

**新开终端2（测试 API）**
```bash
curl -X POST http://localhost:5000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"冬季怎么生存？","session_id":"test"}'
```

**新开终端3（测试 Agent）**
```bash
python Agent/search_agent.py
```

---

## 📂 重要路径

- **后端**: `backend/app.py`
- **知识库**: `backend/knowledge_base/`
- **Agent**: `Agent/search_agent.py`
- **测试**: `test_integration.py`
- **文档**: `SYSTEM_README.md` / `QUICKSTART.md`

---

## 🔑 快速命令

| 目的 | 命令 |
|-----|------|
| **启动系统** | `python START.py` |
| **运行测试** | `python test_integration.py` |
| **测试API** | `python Agent/search_agent.py` |
| **查看状态** | `curl http://localhost:5000/health` |
| **查看知识库** | `curl http://localhost:5000/api/knowledge-base-status` |

---

## 💾 文件清单

```
✅ START.bat          - Windows 一键启动
✅ START.ps1          - PowerShell 启动脚本
✅ START.py           - Python 启动脚本（推荐）
✅ QUICKSTART.md      - 本文件（快速参考）
✅ SYSTEM_README.md   - 完整系统文档
✅ test_integration.py - 集成测试
```

---

**🎮 现在就启动吧！**

```bash
python START.py
```

然后在浏览器访问 `http://localhost:5000/health`

✨ 一切就绪！
