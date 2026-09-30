#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
《饥荒游戏攻略AI助手》统一启动器
一个命令启动全部服务：游戏数据API + 后端(RAG/LoRA/Agent/多模态) + 前端

使用方式：
  python START_ALL.py                        # 启动全部（默认）
  python START_ALL.py --no-frontend          # 不启动前端
  python START_ALL.py --backend-only         # 仅后端
  python START_ALL.py --frontend-only        # 仅前端
  python START_ALL.py --agent-terminal       # 启动全部 + Agent 交互终端（新窗口）
"""

import os
import sys
import subprocess
import argparse
import shutil
import time
from pathlib import Path
import threading
import signal

# 修复 Windows 控制台 GBK 编码
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass


class UnifiedLauncher:
    """统一启动器 —— 所有服务在一个终端"""

    COLORS = {
        'header': '\033[95m', 'blue': '\033[94m', 'cyan': '\033[96m',
        'green': '\033[92m', 'yellow': '\033[93m', 'red': '\033[91m',
        'reset': '\033[0m', 'bold': '\033[1m',
    }

    def __init__(self, args):
        self.args = args
        self.project_root = Path(__file__).parent
        self.backend_dir = self.project_root / "backend"
        self.frontend_dir = self.project_root / "frontend"
        self.agent_dir = self.project_root.parent / 'Agent'
        if not self.agent_dir.exists():
            self.agent_dir = self.project_root / 'Agent'
        self.processes = []
        self.use_shell = sys.platform == 'win32'
        self.npm_path = shutil.which('npm') or 'npm'

    def cprint(self, text, color='reset', bold=False):
        prefix = (self.COLORS.get('bold', '') if bold else '') + self.COLORS.get(color, '')
        print(f"{prefix}{text}{self.COLORS['reset']}")

    def header(self, title):
        w = 70
        s = "═" * w
        print(); self.cprint(s, 'cyan'); self.cprint(f"  {title}", 'cyan', bold=True); self.cprint(s, 'cyan'); print()

    def check_project_structure(self):
        self.header(self.args.project_title)

        print(f"📍 项目目录: {self.project_root}")
        print(f"🐍 Python:    {sys.executable}")
        print()

        checks = {
            '后端应用 (app.py)': self.backend_dir / 'app.py',
            '游戏数据API': self.project_root / 'game_data_api.py',
            '前端应用': self.frontend_dir / 'package.json',
        }

        print("📁 项目文件检查:")
        all_ok = True
        for name, path in checks.items():
            ok = path.exists()
            icon = "✅" if ok else "❌"
            print(f"  {icon} {name}")
            if not ok and '前端' not in name:
                all_ok = False

        # 多模态模块
        mm_dir = self.backend_dir / 'multimodal'
        if mm_dir.exists():
            print(f"  ✅ 多模态模块 (图片/语音)")
        else:
            print(f"  ⚠️  多模态模块缺失")

        # Agent（内嵌在后端，检查源码）
        agent_py = self.agent_dir / 'search_agent.py' if self.agent_dir.exists() else None
        if agent_py and agent_py.exists():
            print(f"  ✅ Agent 联网搜索（内嵌于后端）")
        else:
            print(f"  ⚠️  Agent 脚本未找到（联网搜索不可用）")

        print()
        if not all_ok and not self.args.frontend_only:
            self.cprint("❌ 核心文件缺失，无法启动", 'red')
            return False
        self.cprint("✅ 项目结构检查完成", 'green')
        return True

    def show_plan(self):
        print()
        self.cprint("📋 启动计划:", 'cyan', bold=True)
        print()

        services = [
            ('🎮 游戏数据API',    5001, not self.args.backend_only and not self.args.frontend_only),
            ('🧠 后端应用',       5000, not self.args.api_only and not self.args.frontend_only),
            ('   ├ RAG 知识库',   None, True),
            ('   ├ LoRA 微调',    None, True),
            ('   ├ Agent 搜索',   None, True),
            ('   └ 多模态解析',  None, True),
            ('🌐 前端应用',       3000, not self.args.no_frontend and not self.args.api_only and not self.args.backend_only),
        ]
        if self.args.frontend_only:
            services = [('🌐 前端应用', 3000, True)]

        for name, port, active in services:
            if active:
                port_str = f"(:{port})" if port else ""
                self.cprint(f"  ▶  {name:22} {port_str}", 'green')
            else:
                self.cprint(f"  ✕  {name:22} (跳过)", 'yellow')

        print()
        self.cprint("💡 Ctrl+C 停止所有服务", 'yellow')
        print()

    # ========== 服务启动 ==========

    def start_api(self):
        if self.args.backend_only or self.args.frontend_only:
            return None
        self.cprint("─" * 70, 'yellow')
        self.cprint("🚀 [1/3] 启动游戏数据API (localhost:5001)", 'yellow', bold=True)
        try:
            p = subprocess.Popen(
                [sys.executable, 'game_data_api.py'],
                cwd=self.project_root,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            p._name = '游戏数据API'
            self.processes.append(p)
            self.cprint("   ✅ 已启动", 'green')
            time.sleep(1)
            return p
        except Exception as e:
            self.cprint(f"   ❌ 失败: {e}", 'red')
            return None

    def start_backend(self):
        if self.args.api_only or self.args.frontend_only:
            return None
        step = 1 if self.args.api_only else 2
        total = self._total_steps()
        self.cprint("─" * 70, 'yellow')
        self.cprint(f"🚀 [{step}/{total}] 启动后端应用 (localhost:5000)", 'yellow', bold=True)
        print("   (LoRA 加载约10秒, BLIP/Whisper 按需加载...)")
        try:
            env = os.environ.copy()
            env['FLASK_NO_RELOAD'] = '1'  # 避免 reloader 导致 LoRA 加载两遍
            p = subprocess.Popen(
                [sys.executable, 'app.py'],
                cwd=self.backend_dir,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                env=env
            )
            p._name = '后端应用'
            self.processes.append(p)

            # 轮询健康检查
            for i in range(45):
                try:
                    import urllib.request
                    urllib.request.urlopen("http://127.0.0.1:5000/health", timeout=2)
                    self.cprint("   ✅ 后端已就绪", 'green')
                    # 检查多模态状态
                    try:
                        import json
                        resp = urllib.request.urlopen("http://127.0.0.1:5000/api/multimodal/status", timeout=2)
                        mm = json.loads(resp.read())
                        img_ok = 'BLIP' in mm.get('image_parser', '') and '就绪' in mm.get('image_parser', '')
                        audio_ok = 'Whisper' in mm.get('speech_to_text', '') and '就绪' in mm.get('speech_to_text', '')
                        img_s = '✅' if img_ok else '⚠️'
                        audio_s = '✅' if audio_ok else '⚠️'
                        self.cprint(f"   {img_s} 多模态·图片: {mm.get('image_parser','?')}", 'green' if img_ok else 'yellow')
                        self.cprint(f"   {audio_s} 多模态·语音: {mm.get('speech_to_text','?')}", 'green' if audio_ok else 'yellow')
                    except Exception:
                        pass
                    break
                except Exception:
                    if i == 5:
                        print("   (仍在加载中...)")
                    time.sleep(1)
            else:
                self.cprint("   ⚠️ 后端启动较慢，稍后访问 http://localhost:5000/health", 'yellow')
            return p
        except Exception as e:
            self.cprint(f"   ❌ 失败: {e}", 'red')
            return None

    def start_frontend(self):
        if self.args.no_frontend or self.args.api_only or self.args.backend_only:
            return None
        if not shutil.which('node'):
            self.cprint("⚠️ 未找到 Node.js，跳过前端", 'yellow')
            return None

        # 检查依赖
        if not (self.frontend_dir / 'node_modules').exists():
            self.cprint("📦 安装前端依赖...", 'cyan')
            try:
                subprocess.run(
                    f'"{self.npm_path}" install' if self.use_shell else [self.npm_path, 'install'],
                    cwd=str(self.frontend_dir), capture_output=True,
                    timeout=300, shell=self.use_shell
                )
                self.cprint("   ✅ 依赖安装完成", 'green')
            except Exception as e:
                self.cprint(f"   ⚠️ 安装失败: {e}", 'yellow')

        step = 2 if self.args.frontend_only else 3
        total = self._total_steps()
        self.cprint("─" * 70, 'yellow')
        self.cprint(f"🚀 [{step}/{total}] 启动前端应用 (localhost:3000)", 'yellow', bold=True)
        try:
            cmd = f'"{self.npm_path}" start' if self.use_shell else [self.npm_path, 'start']
            p = subprocess.Popen(
                cmd, cwd=str(self.frontend_dir),
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, shell=self.use_shell
            )
            p._name = '前端应用'
            self.processes.append(p)
            time.sleep(2)
            self.cprint("   ✅ 已启动", 'green')
            return p
        except Exception as e:
            self.cprint(f"   ⚠️ 失败: {e}", 'yellow')
            self.cprint(f"   💡 手动启动: cd frontend && npm start", 'yellow')
            return None

    def start_agent_terminal(self):
        """在新终端中启动 Agent 交互式会话（可选）"""
        if not self.args.agent_terminal:
            return None

        agent_path = self.agent_dir / 'agent_web.py' if self.agent_dir.exists() else None
        if not agent_path or not agent_path.exists():
            self.cprint("⚠️ Agent 脚本未找到", 'yellow')
            return None

        self.cprint("─" * 70, 'yellow')
        self.cprint(f"🔧 启动 Agent 交互终端 (新窗口)", 'yellow', bold=True)
        try:
            if self.use_shell:
                cmd = (
                    f'start "Agent-交互终端" '
                    f'cmd /k "cd /d {self.agent_dir} && '
                    f'{sys.executable} agent_web.py --persona {self.args.agent_persona}"'
                )
                subprocess.Popen(cmd, shell=True)
                self.cprint("   ✅ Agent 在新窗口中启动", 'green')
            else:
                subprocess.Popen([
                    'gnome-terminal', '--', 'bash', '-c',
                    f'cd {self.agent_dir} && python agent_web.py --persona {self.args.agent_persona}; exec bash'
                ])
            return True
        except Exception as e:
            self.cprint(f"   ⚠️ 失败: {e}", 'yellow')
            return None

    def _total_steps(self):
        n = 0
        if not self.args.backend_only and not self.args.frontend_only:
            n += 1  # API
        if not self.args.api_only and not self.args.frontend_only:
            n += 1  # Backend
        if not self.args.no_frontend and not self.args.api_only and not self.args.backend_only:
            n += 1  # Frontend
        if self.args.frontend_only:
            n = 1
        if self.args.api_only:
            n = 1
        if self.args.backend_only:
            n = 1
        return n

    # ========== 监控 & 停止 ==========

    def monitor(self):
        print()
        self.cprint("═" * 70, 'green')
        self.cprint("✅ 全部就绪！", 'green', bold=True)
        self.cprint("═" * 70, 'green')
        print()
        print("📍 访问地址:")
        print("   • 前端页面:    http://localhost:3000")
        print("   • 后端接口:    http://localhost:5000/api/chat")
        print("   • 多模态接口:  http://localhost:5000/api/multimodal/chat")
        print("   • Agent 搜索:  http://localhost:5000/api/agent/search")
        print("   • 游戏数据API: http://localhost:5001/api/...")
        print("   • 健康检查:    http://localhost:5000/health")
        print()
        self.cprint("🛑 按 Ctrl+C 停止所有服务", 'yellow')
        print()

    def wait(self):
        def handler(sig, frame):
            print()
            self.cprint("⏹ 正在停止所有服务...", 'red')
            self.stop_all()
            sys.exit(0)
        signal.signal(signal.SIGINT, handler)
        try:
            while self.processes:
                time.sleep(2)
                alive = []
                for p in self.processes:
                    code = p.poll()
                    if code is not None:
                        name = getattr(p, '_name', '?')
                        self.cprint(f"⚠️ {name} 已停止 (exit={code})", 'yellow')
                    else:
                        alive.append(p)
                self.processes = alive
                if not self.processes:
                    self.cprint("ℹ️ 所有服务已退出", 'yellow')
                    break
        except KeyboardInterrupt:
            pass

    def stop_all(self):
        for p in self.processes:
            if p.poll() is None:
                try:
                    p.terminate()
                    p.wait(timeout=5)
                except Exception:
                    p.kill()
        self.cprint("✅ 所有服务已停止", 'green')
        print()

    def run(self):
        if not self.check_project_structure():
            return 1

        self.show_plan()

        # 按依赖顺序启动: API → Backend → Frontend → Agent(可选)
        self.start_api()
        self.start_backend()
        self.start_frontend()
        self.start_agent_terminal()

        self.monitor()
        self.wait()
        return 0


def main():
    parser = argparse.ArgumentParser(
        description='🎮 饥荒游戏攻略AI助手 - 统一启动器',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python START_ALL.py                 # 启动全部（API + 后端 + 前端）
  python START_ALL.py --no-frontend   # 不启动前端
  python START_ALL.py --agent-terminal # 全部 + Agent 交互终端新窗口
"""
    )
    parser.add_argument('--project-title', default='🎮 饥荒游戏攻略AI助手 — 统一启动',
                        help='启动标题')
    parser.add_argument('--backend-only', action='store_true', help='仅后端')
    parser.add_argument('--api-only', action='store_true', help='仅API')
    parser.add_argument('--frontend-only', action='store_true', help='仅前端')
    parser.add_argument('--no-frontend', action='store_true', help='不启动前端')
    parser.add_argument('--with-agent', action='store_true',  # 旧参数，兼容
                        help='同 --agent-terminal，在新窗口打开 Agent 交互终端')
    parser.add_argument('--agent-terminal', action='store_true',
                        help='额外打开 Agent 交互终端（新窗口）')
    parser.add_argument('--agent-persona', default='search',
                        choices=['search', 'buddy', 'teacher', 'strict'],
                        help='Agent 人设 (默认: search)')
    args = parser.parse_args()

    # 兼容旧参数
    if args.with_agent:
        args.agent_terminal = True
    return UnifiedLauncher(args).run()


if __name__ == '__main__':
    sys.exit(main())
