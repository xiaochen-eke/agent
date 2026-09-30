#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
《饥荒游戏攻略助手》一键启动脚本
支持：Windows、macOS、Linux
功能：初始化知识库 + 启动后端 + 可选测试和Agent
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path
from datetime import datetime

# 修复 Windows 控制台 GBK 编码问题
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass


class Launcher:
    """启动器类"""
    
    COLORS = {
        'header': '\033[95m',
        'blue': '\033[94m',
        'cyan': '\033[96m',
        'green': '\033[92m',
        'yellow': '\033[93m',
        'red': '\033[91m',
        'reset': '\033[0m',
        'bold': '\033[1m',
    }
    
    def __init__(self, args):
        self.args = args
        self.project_root = Path(__file__).parent
        self.backend_dir = self.project_root / "backend"
        self.log_file = self.project_root / "startup.log"
    
    def print_header(self, title, color='cyan'):
        """打印标题"""
        width = 60
        border = "═" * width
        print()
        self.print_color(border, color)
        self.print_color(f"  {title}", color, bold=True)
        self.print_color(border, color)
        print()
    
    def print_color(self, text, color='reset', bold=False):
        """彩色打印"""
        prefix = self.COLORS.get(color, '')
        if bold:
            prefix = self.COLORS['bold'] + prefix
        reset = self.COLORS['reset']
        print(f"{prefix}{text}{reset}")
    
    def print_step(self, step_num, title, color='green'):
        """打印步骤"""
        print(f"\n{'━' * 60}")
        self.print_color(f"📍 第{step_num}步：{title}", color)
        print(f"{'━' * 60}\n")
    
    def log(self, message):
        """记录日志"""
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(f"[{datetime.now()}] {message}\n")
    
    def run_command(self, cmd, cwd=None, description=""):
        """运行命令"""
        if not cwd:
            cwd = self.project_root
        
        try:
            self.log(f"运行命令: {' '.join(cmd)} (在 {cwd})")
            result = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=False,
                text=True
            )
            return result.returncode == 0
        except Exception as e:
            self.print_color(f"❌ 命令执行失败: {e}", 'red')
            self.log(f"错误: {e}")
            return False
    
    def check_project_structure(self):
        """检查项目结构"""
        self.print_header("🎮 饥荒游戏攻略AI助手 - 一键启动", 'cyan')
        
        self.print_color(f"📍 项目目录: {self.project_root}", 'green')
        
        # 检查必要目录
        required_dirs = {
            'backend': ('后端目录', self.project_root / 'backend'),
            'knowledge_base': ('知识库目录 (会自动创建)', self.project_root / 'knowledge_base'),
        }
        
        # Agent 可能在上级目录
        agent_dir = self.project_root.parent / 'Agent'
        if not agent_dir.exists():
            agent_dir = self.project_root / 'Agent'
        
        optional_dirs = {
            'Agent': ('Agent目录', agent_dir),
        }
        
        print("\n检查项目结构:")
        
        # 检查必要目录
        for dir_name, (description, dir_path) in required_dirs.items():
            if dir_path.exists():
                self.print_color(f"  ✅ {description:25} ✓", 'green')
            else:
                if dir_name == 'knowledge_base':
                    self.print_color(f"  ⚠️ {description:25} (将创建)", 'yellow')
                else:
                    self.print_color(f"  ❌ {description:25} (缺失)", 'red')
                    return False
        
        # 检查可选目录
        for dir_name, (description, dir_path) in optional_dirs.items():
            if dir_path.exists():
                self.print_color(f"  ✅ {description:25} ✓", 'green')
            else:
                self.print_color(f"  ⚠️ {description:25} (可选，不影响启动)", 'yellow')
        
        return True
    
    def init_knowledge_base(self):
        """初始化知识库"""
        if self.args.skip_kb:
            self.print_step(1, "初始化知识库", 'yellow')
            self.print_color("⏭️  跳过知识库初始化 (使用 --skip-kb 参数)", 'yellow')
            return True
        
        self.print_step(1, "初始化知识库", 'yellow')
        
        cmd = [sys.executable, 'init_knowledge_base.py']
        success = self.run_command(cmd, cwd=self.backend_dir, description="初始化知识库")
        
        if not success:
            self.print_color("⚠️  知识库初始化出现警告（继续启动）", 'yellow')
        
        return True
    
    def run_tests(self):
        """运行集成测试"""
        self.print_step(2, "运行集成测试", 'magenta')
        
        cmd = [sys.executable, 'test_integration.py']
        success = self.run_command(cmd, cwd=self.project_root, description="运行测试")
        
        if not success:
            self.print_color("❌ 测试失败！", 'red')
            return False
        
        return True
    
    def start_backend(self):
        """启动后端"""
        self.print_step(3, "启动后端服务", 'green')
        
        # 打印提示信息
        self.print_color("💡 系统信息", 'cyan')
        print(f"""
  🌐 后端地址: http://localhost:5000
  📚 知识库路径: {self.backend_dir}/knowledge_base
  💾 数据库: {self.backend_dir}/chat_history.db
  
  🔧 可用操作:
    • 聊天接口: POST /api/chat
    • 历史记录: GET /api/history/<session_id>
    • 状态检查: GET /api/knowledge-base-status
    • 健康检查: GET /health
  
  🛑 停止方式:
    • 按 Ctrl+C 停止后端服务
  
  🚀 其他终端操作:
    • 测试 Agent: python Agent/search_agent.py
    • 运行完整测试: python test_integration.py
    • 查看文档: 阅读 SYSTEM_README.md
        """)
        
        print("=" * 60)
        self.print_color("🚀 后端启动中...", 'green')
        print("=" * 60)
        print()
        
        # 启动后端
        cmd = [sys.executable, 'app.py']
        os.chdir(self.backend_dir)
        
        try:
            subprocess.run(cmd)
        except KeyboardInterrupt:
            print()
            self.print_color("⏹️  收到中止信号", 'red')
        except Exception as e:
            self.print_color(f"❌ 启动失败: {e}", 'red')
            self.log(f"启动错误: {e}")
    
    def show_completion(self):
        """显示完成信息"""
        print()
        print("=" * 60)
        self.print_color("✅ 启动完成！", 'green')
        print("=" * 60)
        print()
        self.print_color("📖 下一步建议:", 'cyan')
        print("""
  1. 在浏览器中打开：http://localhost:5000/health
  2. 使用 curl 或 API 工具测试：
     POST http://localhost:5000/api/chat
     {
       "message": "冬季怎么生存？",
       "session_id": "test"
     }
  3. 新开终端测试 Agent:
     python Agent/search_agent.py
  4. 查看完整文档：
     cat SYSTEM_README.md
        """)
    
    def run(self):
        """主运行流程"""
        # 清空日志文件
        with open(self.log_file, 'w', encoding='utf-8') as f:
            f.write(f"=== 启动日志 [{datetime.now()}] ===\n")
        
        # 检查项目结构
        if not self.check_project_structure():
            self.print_color("❌ 项目结构检查失败", 'red')
            return 1
        
        # 初始化知识库
        if not self.init_knowledge_base():
            self.print_color("❌ 知识库初始化失败", 'red')
            return 1
        
        # 运行测试（可选）
        if self.args.run_tests:
            if not self.run_tests():
                return 1
        
        # 启动后端
        self.start_backend()
        
        # 显示完成信息
        self.show_completion()
        
        return 0


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='🎮 饥荒游戏攻略AI助手 - 一键启动脚本',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例使用:
  python START.py                    # 正常启动
  python START.py --skip-kb          # 跳过知识库初始化
  python START.py --run-tests        # 启动前运行测试
  python START.py --run-tests --skip-kb  # 运行测试但跳过知识库初始化
        """
    )
    
    parser.add_argument(
        '--skip-kb',
        action='store_true',
        help='跳过知识库初始化'
    )
    
    parser.add_argument(
        '--run-tests',
        action='store_true',
        help='启动前运行集成测试'
    )
    
    args = parser.parse_args()
    
    launcher = Launcher(args)
    return launcher.run()


if __name__ == '__main__':
    sys.exit(main())
