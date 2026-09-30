# 🚀 多服务联合启动指南

## 📋 概述

我为你创建了支持 **同时启动多个服务** 的启动脚本：

- 🎮 **游戏数据API** - 数据提供服务（端口 5001）
- 🤖 **后端应用** - 聊天和RAG服务（端口 5000）
- 💻 **前端应用** - Web界面（端口 3000）

---

## 🚀 快速启动

### 方式 1：启动所有服务（推荐）⭐

**Python 脚本**
```bash
cd C:\DLdata\git\dont_starve_bot
python START_ALL.py
```

**Batch 脚本（Windows）**
```
双击：START_ALL.bat
```

**PowerShell 脚本**
```powershell
.\START_ALL.ps1
```

### 方式 2：选择性启动

**仅启动后端 + API（不启动前端）**
```bash
python START_ALL.py --no-frontend
```

**仅启动后端应用**
```bash
python START_ALL.py --backend-only
```

**仅启动游戏数据API**
```bash
python START_ALL.py --api-only
```

**仅启动前端应用**
```bash
python START_ALL.py --frontend-only
```

---

## 📊 服务架构

```
用户浏览器 (localhost:3000)
    ↓
    前端应用 (React)
    ↓
API 网关 (localhost:5000)
    ├─→ 后端应用
    │   ├─→ RAG 模块
    │   ├─→ 意图识别
    │   └─→ 微调适配器
    │
    └─→ 游戏数据API (localhost:5001)
        ├─→ 游戏物品数据
        ├─→ 生物信息
        ├─→ 建筑数据
        └─→ 食物配方
```

---

## 🔌 服务端口与地址

| 服务 | 端口 | URL | 说明 |
|-----|------|-----|------|
| 游戏数据API | 5001 | `http://localhost:5001/api/...` | 游戏数据查询 |
| 后端应用 | 5000 | `http://localhost:5000/api/chat` | 聊天接口 |
| 后端健康检查 | 5000 | `http://localhost:5000/health` | 系统状态 |
| 前端应用 | 3000 | `http://localhost:3000` | Web界面 |

---

## 🧪 测试各个服务

### 1️⃣ 测试游戏数据API

```bash
# 查询物品信息
curl http://localhost:5001/api/items/木头

# 查询生物信息
curl http://localhost:5001/api/creatures/猎犬

# 查询建筑信息
curl http://localhost:5001/api/buildings/营火
```

### 2️⃣ 测试后端应用

```bash
# 健康检查
curl http://localhost:5000/health

# 聊天API
curl -X POST http://localhost:5000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"冬季怎么生存？","session_id":"test"}'

# 查询会话历史
curl http://localhost:5000/api/history/test

# 知识库状态
curl http://localhost:5000/api/knowledge-base-status
```

### 3️⃣ 测试前端应用

在浏览器中打开：
```
http://localhost:3000
```

应该看到前端界面

---

## 📂 项目文件结构

```
dont_starve_bot/
├── START_ALL.py          ⭐ 多服务启动脚本（Python）
├── START_ALL.bat         ⭐ 多服务启动脚本（Batch）
├── START_ALL.ps1         ⭐ 多服务启动脚本（PowerShell）
├── START.py              单个后端启动脚本
├── START.ps1             单个后端启动脚本
├── START.bat             单个后端启动脚本
│
├── backend/
│   ├── app.py           后端主应用
│   ├── init_knowledge_base.py
│   ├── fine_tuning_adapter.py
│   ├── knowledge_base/  知识库文件夹
│   └── ...
│
├── frontend/            React 前端应用
│   ├── package.json
│   ├── public/
│   ├── src/
│   └── ...
│
├── game_data_api.py     游戏数据API服务
├── game_data_api_client.py
├── test_game_data_api.py
└── ...
```

---

## 🔄 启动流程

### 完整启动（python START_ALL.py）

```
1️⃣ 检查项目结构
   ✅ backend/app.py
   ✅ game_data_api.py
   ✅ frontend/

2️⃣ 启动游戏数据API
   ▶️ http://localhost:5001
   ✅ 等待1秒

3️⃣ 启动后端应用
   ▶️ http://localhost:5000
   ✅ 等待1秒

4️⃣ 安装前端依赖（如需要）
   ▶️ npm install

5️⃣ 启动前端应用
   ▶️ http://localhost:3000
   ✅ 等待2秒

6️⃣ 显示服务状态
   📊 所有服务已启动
   🔗 访问地址
   🛑 停止方式
```

---

## 📝 命令参考

| 命令 | 说明 |
|-----|------|
| `python START_ALL.py` | 启动所有服务 |
| `python START_ALL.py --no-frontend` | 启动API+后端 |
| `python START_ALL.py --backend-only` | 仅启动后端 |
| `python START_ALL.py --api-only` | 仅启动API |
| `python START_ALL.py --frontend-only` | 仅启动前端 |

---

## 🎯 使用场景

### 场景 1：完整开发测试
```bash
python START_ALL.py
# 所有服务都运行，可进行端到端测试
```

### 场景 2：后端开发
```bash
python START_ALL.py --no-frontend
# 只运行API和后端，加快启动速度
```

### 场景 3：前端开发
```bash
python START_ALL.py --frontend-only
# 仅前端，连接到已运行的后端
```

### 场景 4：API测试
```bash
python START_ALL.py --api-only
# 单独测试游戏数据API
```

---

## 🛑 停止服务

### 方式 1：按 Ctrl+C
```
按 Ctrl+C 停止所有服务
```

### 方式 2：关闭终端窗口
```
关闭运行脚本的终端会停止所有进程
```

### 方式 3：手动杀死进程

**Windows**
```bash
# 查看进程
netstat -ano | findstr ":5000" 
netstat -ano | findstr ":5001"
netstat -ano | findstr ":3000"

# 结束进程（PID 为进程号）
taskkill /PID <PID> /F
```

**PowerShell**
```powershell
# 停止指定端口的进程
Get-Process | Where-Object {$_.MainWindowTitle -like "*5000*"} | Stop-Process
```

---

## ⚠️ 常见问题

### Q1: 某个服务启动失败怎么办？

**A:** 查看错误信息，常见原因：

1. **API启动失败** - 可能 `game_data_api.py` 有错误
   ```bash
   python game_data_api.py  # 单独测试
   ```

2. **后端启动失败** - 可能 API 密钥未配置
   ```bash
   # 检查 ZHIPU_API_KEY 是否设置
   echo %ZHIPU_API_KEY%  # Windows
   echo $env:ZHIPU_API_KEY  # PowerShell
   ```

3. **前端启动失败** - 可能缺少 Node.js 或依赖
   ```bash
   node --version  # 检查 Node.js
   npm install     # 重新安装依赖
   ```

### Q2: 端口被占用怎么办？

**A:** 修改启动脚本中的端口号

编辑 `game_data_api.py`：
```python
if __name__ == '__main__':
    app.run(debug=True, port=5002)  # 改为 5002
```

编辑 `backend/app.py`：
```python
if __name__ == '__main__':
    app.run(debug=True, port=5001)  # 改为 5001
```

### Q3: 前端加载慢怎么办？

**A:** 首次启动时 `npm install` 会很慢，后续会快很多

如果想跳过前端启动：
```bash
python START_ALL.py --no-frontend
```

### Q4: 如何在不关闭其他服务的情况下重启某个服务？

**A:** 在新终端中单独启动

```bash
# 终端1：运行主启动脚本（不包括前端）
python START_ALL.py --no-frontend

# 终端2：重启前端
cd frontend
npm start
```

---

## 💡 开发技巧

### 技巧 1：在不同终端中运行服务

```bash
# 终端1：启动API
python game_data_api.py

# 终端2：启动后端
cd backend
python app.py

# 终端3：启动前端
cd frontend
npm start

# 终端4：运行测试或其他命令
python test_integration.py
```

### 技巧 2：监控日志

```bash
# 创建日志文件
python START_ALL.py > startup.log 2>&1

# 实时查看日志
tail -f startup.log  # Mac/Linux
Get-Content startup.log -Tail 20 -Wait  # PowerShell
```

### 技巧 3：自动化重启

**创建 restart.ps1**
```powershell
# 停止所有服务
Get-Process python | Stop-Process
Get-Process node | Stop-Process

# 等待1秒
Start-Sleep -Seconds 1

# 重新启动
python START_ALL.py
```

---

## 📊 服务依赖关系

```
前端应用
  ↓
  调用 → 后端应用 (localhost:5000)
           ↓
           调用 → 游戏数据API (localhost:5001)
           调用 → 知识库检索
           调用 → 大模型API (远程)
```

---

## 🎓 更多资源

- **后端文档**: `SYSTEM_README.md`
- **快速参考**: `QUICK_REFERENCE.md`
- **项目结构**: `PROJECT_STRUCTURE.md`
- **单个启动**: `QUICKSTART.md`

---

## ✨ 总结

| 启动方式 | 命令 | 场景 |
|---------|------|------|
| **全部** | `python START_ALL.py` | 完整开发测试 |
| **无前端** | `python START_ALL.py --no-frontend` | 后端快速启动 |
| **仅后端** | `python START_ALL.py --backend-only` | 后端开发 |
| **仅API** | `python START_ALL.py --api-only` | API测试 |
| **仅前端** | `python START_ALL.py --frontend-only` | 前端开发 |

---

**🚀 现在就启动你的完整系统吧！**

```bash
python START_ALL.py
```

然后打开浏览器访问：`http://localhost:3000`

版本：1.0.0  
更新时间：2026-06-13
