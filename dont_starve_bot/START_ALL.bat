@echo off
REM 《饥荒游戏攻略助手》完整系统启动脚本 (Windows Batch)
REM 支持同时启动：API + 后端 + 前端 + Agent（可选）

echo.
echo ╔════════════════════════════════════════════════════════╗
echo ║    🎮 饥荒游戏攻略AI助手 - 完整系统启动               ║
echo ║    (API + 后端 + 前端 + Agent)                        ║
echo ╚════════════════════════════════════════════════════════╝
echo.

REM 获取脚本所在目录
set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

echo ✅ 项目检测
echo   • 后端应用: backend/app.py
echo   • API服务: game_data_api.py
echo   • 前端应用: frontend/
echo   • Agent (可选): ../Agent/
echo.

echo 📋 启动方式:
echo   • 基础启动:  python START_ALL.py --no-frontend
echo   • 含前端:    python START_ALL.py
echo   • 含Agent:   python START_ALL.py --with-agent
echo   • 仅后端:    python START_ALL.py --backend-only
echo.

echo 💡 提示: 输入参数可传递给 Python 脚本
echo    例如: START_ALL --with-agent --agent-type search_agent.py
echo.

REM 把所有命令行参数传给 Python
python START_ALL.py %*

if errorlevel 1 (
    echo.
    echo ❌ 启动失败
    pause
    exit /b 1
)

pause
