# 《饥荒游戏攻略助手》一键启动脚本 (PowerShell)
# 功能：初始化知识库 + 启动后端服务 + 可选启动Agent

param(
    [switch]$SkipKB = $false,
    [switch]$TestAgent = $false,
    [switch]$RunTests = $false
)

$ErrorActionPreference = "Continue"

# ==================== 颜色定义 ====================
function Write-Color {
    param([string]$text, [string]$color = "White")
    Write-Host $text -ForegroundColor $color
}

# ==================== 主程序 ====================

Write-Host ""
Write-Color "╔════════════════════════════════════════════════════════╗" "Cyan"
Write-Color "║     🎮 饥荒游戏攻略AI助手 - 一键启动                   ║" "Cyan"
Write-Color "╚════════════════════════════════════════════════════════╝" "Cyan"
Write-Host ""

$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptPath

Write-Color "📍 工作目录: $scriptPath" "Green"

# 检查后端目录
if (-not (Test-Path "backend")) {
    Write-Color "❌ 错误: 找不到 backend 目录" "Red"
    Write-Color "请确保在项目根目录运行此脚本" "Red"
    Read-Host "按 Enter 退出"
    exit 1
}

# 检查 Agent 目录（可能在上级目录）
$agentPath = Join-Path (Split-Path -Parent $scriptPath) "Agent"
if (-not (Test-Path $agentPath)) {
    $agentPath = Join-Path $scriptPath "Agent"
}

Write-Color "✅ 项目检测成功" "Green"
Write-Host ""

# 显示检查结果
Write-Host "检查项目结构:"
Write-Color "  ✅ 后端目录              backend/" "Green"
if (Test-Path $agentPath) {
    Write-Color "  ✅ Agent目录            Agent/" "Green"
} else {
    Write-Color "  ⚠️ Agent目录            (可选)" "Yellow"
}
Write-Color "  ⚠️ 知识库目录            knowledge_base/ (将创建)" "Yellow"
Write-Host ""
Write-Host ""

# ==================== 第1步：初始化知识库 ====================
if (-not $SkipKB) {
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor "Yellow"
    Write-Color "📚 第1步：初始化知识库..." "Yellow"
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor "Yellow"
    Write-Host ""
    
    Set-Location backend
    python init_knowledge_base.py
    
    if ($LASTEXITCODE -ne 0) {
        Write-Color "⚠️ 知识库初始化出现警告（非致命，继续启动）" "Yellow"
    }
    
    Set-Location ..
    Write-Host ""
}

# ==================== 第2步：运行测试 (可选) ====================
if ($RunTests) {
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor "Magenta"
    Write-Color "🧪 第2步：运行集成测试..." "Magenta"
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor "Magenta"
    Write-Host ""
    
    python test_integration.py
    
    if ($LASTEXITCODE -ne 0) {
        Write-Color "❌ 测试失败" "Red"
        Read-Host "按 Enter 退出"
        exit 1
    }
    
    Write-Host ""
}

# ==================== 第3步：启动后端 ====================
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor "Green"
Write-Color "🚀 第3步：启动后端服务..." "Green"
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor "Green"
Write-Host ""

Write-Color "💡 提示：" "Cyan"
Write-Host "  • 后端运行在 http://localhost:5000" -ForegroundColor "Cyan"
Write-Host "  • API 文档: http://localhost:5000/api/chat" -ForegroundColor "Cyan"
Write-Host "  • 按 Ctrl+C 停止服务" -ForegroundColor "Cyan"
Write-Host "  • 新开终端运行:" -ForegroundColor "Cyan"
Write-Host "    - 测试 Agent: python Agent/search_agent.py" -ForegroundColor "Magenta"
Write-Host "    - 运行测试: python test_integration.py" -ForegroundColor "Magenta"
Write-Host ""

# 启动后端
Set-Location backend
Write-Color "启动中..." "Green"
Write-Host ""
python app.py

# 清理
Write-Host ""
Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor "Red"
Write-Color "⏹️  后端服务已停止" "Red"
Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor "Red"
Read-Host "按 Enter 退出"
