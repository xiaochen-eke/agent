# 《饥荒游戏攻略助手》完整系统启动脚本 (PowerShell)
# 支持同时启动：API + 后端 + 前端 + Agent（可选）

param(
    [switch]$BackendOnly = $false,
    [switch]$ApiOnly = $false,
    [switch]$FrontendOnly = $false,
    [switch]$NoFrontend = $false,
    [switch]$WithAgent = $false,
    [string]$AgentType = "search_agent.py",
    [string]$AgentPersona = "buddy"
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
Write-Color "║    🎮 饥荒游戏攻略AI助手 - 完整系统启动               ║" "Cyan"
Write-Color "║    (API + 后端 + 前端 + Agent)                        ║" "Cyan"
Write-Color "╚════════════════════════════════════════════════════════╝" "Cyan"
Write-Host ""

# 获取脚本目录
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptPath

Write-Color "📍 项目目录: $scriptPath" "Green"
Write-Host ""

# 检查项目结构
Write-Host "检查项目文件:"
$checks = @{
    "后端应用: backend/app.py" = Test-Path "backend\app.py"
    "API服务: game_data_api.py" = Test-Path "game_data_api.py"
    "前端应用: frontend/" = Test-Path "frontend"
}

foreach ($check in $checks.GetEnumerator()) {
    if ($check.Value) {
        Write-Color "  ✅ $($check.Name)" "Green"
    } else {
        Write-Color "  ❌ $($check.Name)" "Red"
    }
}

# 检查 Agent
$agentParent = Join-Path (Split-Path -Parent $scriptPath) "Agent"
$agentLocal = Join-Path $scriptPath "Agent"
if (Test-Path $agentParent) {
    Write-Color "  ✅ Agent (上级目录)" "Green"
} elseif (Test-Path $agentLocal) {
    Write-Color "  ✅ Agent (本地目录)" "Green"
} else {
    Write-Color "  ⚠️  Agent (未找到，可选)" "Yellow"
}

Write-Host ""

# 显示启动计划
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor "Yellow"
Write-Color "📋 启动计划" "Yellow"
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor "Yellow"
Write-Host ""

if ($BackendOnly) {
    Write-Color "  • 后端应用          (localhost:5000)" "Green"
} elseif ($ApiOnly) {
    Write-Color "  • 游戏数据API       (localhost:5001)" "Green"
} elseif ($FrontendOnly) {
    Write-Color "  • 前端应用          (localhost:3000)" "Green"
} else {
    Write-Color "  • 游戏数据API       (localhost:5001)" "Green"
    Write-Color "  • 后端应用          (localhost:5000)" "Green"
    if (-not $NoFrontend) {
        Write-Color "  • 前端应用          (localhost:3000)" "Green"
    }
}

if ($WithAgent) {
    Write-Color "  • Agent ($AgentType)  (新终端窗口)" "Green"
}

Write-Host ""
Write-Color "💡 提示：按 Ctrl+C 停止所有服务" "Cyan"
Write-Host ""

# 构建启动参数
$pythonArgs = @("START_ALL.py")

if ($BackendOnly) { $pythonArgs += "--backend-only" }
if ($ApiOnly) { $pythonArgs += "--api-only" }
if ($FrontendOnly) { $pythonArgs += "--frontend-only" }
if ($NoFrontend) { $pythonArgs += "--no-frontend" }
if ($WithAgent) {
    $pythonArgs += "--with-agent"
    $pythonArgs += "--agent-type"
    $pythonArgs += $AgentType
    $pythonArgs += "--agent-persona"
    $pythonArgs += $AgentPersona
}

# 启动所有服务
Write-Color "🚀 启动所有服务..." "Green"
Write-Host ""

python @pythonArgs

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Color "❌ 启动失败 (Exit Code: $LASTEXITCODE)" "Red"
    Read-Host "按 Enter 退出"
    exit 1
}

Read-Host "按 Enter 退出"
