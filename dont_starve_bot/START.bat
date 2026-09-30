@echo off
REM 《饥荒游戏攻略助手》一键启动脚本 (Windows Batch)
REM 功能：初始化知识库 + 启动后端服务

echo.
echo ╔════════════════════════════════════════════════════════╗
echo ║     🎮 饥荒游戏攻略AI助手 - 一键启动                   ║
echo ╚════════════════════════════════════════════════════════╝
echo.

REM 获取脚本所在目录
set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

REM 检查后端目录
if not exist "backend" (
    echo ❌ 错误: 找不到 backend 目录
    echo 请确保在项目根目录运行此脚本
    pause
    exit /b 1
)

echo ✅ 项目检测成功
echo.

REM 第一步：初始化知识库
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo 📚 第1步：初始化知识库...
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo.

cd backend
python init_knowledge_base.py

if errorlevel 1 (
    echo.
    echo ⚠️ 知识库初始化出现警告或错误（非致命）
    echo 继续启动后端...
    echo.
)

echo.
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo 🚀 第2步：启动后端服务...
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo.
echo 💡 提示：
echo   - 后端运行在 http://localhost:5000
echo   - 按 Ctrl+C 停止服务
echo   - 新开终端运行 python ../Agent/search_agent.py 测试Agent
echo.

REM 启动后端
python app.py

REM 清理和提示
echo.
echo ═══════════════════════════════════════════════════════
echo ⏹️  后端服务已停止
echo ═══════════════════════════════════════════════════════
pause
