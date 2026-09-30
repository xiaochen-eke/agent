#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
项目结构检查诊断工具
用于检查项目结构是否正确
"""

from pathlib import Path
import sys

# 修复 Windows 控制台 GBK 编码问题
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass


def check_structure():
    """检查项目结构"""

    print("\n" + "=" * 60)
    print("[*] 项目结构检查诊断")
    print("=" * 60)

    # 获取当前目录
    current_dir = Path(__file__).parent
    project_root = current_dir

    print(f"\n[*] 当前目录: {current_dir}")
    print(f"[*] 项目根目录: {project_root}")

    # 检查项目结构
    print("\n" + "-" * 60)
    print("检查项目结构")
    print("-" * 60)

    checks = {
        '后端目录': project_root / 'backend',
        '知识库目录': project_root / 'knowledge_base',
        '测试脚本': project_root / 'test_integration.py',
        '启动脚本': project_root / 'START.py',
    }

    all_ok = True
    for name, path in checks.items():
        exists = path.exists()
        status = "[OK]" if exists else "[FAIL]"
        rel_path = path.relative_to(project_root)
        print(f"{status} {name:15} {rel_path}")
        if not exists and name != '知识库目录':
            all_ok = False

    # 检查 Agent 目录
    print("\n" + "-" * 60)
    print("检查可选目录")
    print("-" * 60)

    # Agent 可能在上级目录
    agent_local = project_root / 'Agent'
    agent_parent = project_root.parent / 'Agent'

    if agent_local.exists():
        print(f"[OK] Agent目录(本地)       Agent/")
        agent_path = agent_local
    elif agent_parent.exists():
        print(f"[OK] Agent目录(上级)       ../Agent/")
        agent_path = agent_parent
    else:
        print(f"[!]  Agent目录             (未找到，可选)")
        agent_path = None

    # 检查 backend 子目录
    print("\n" + "-" * 60)
    print("检查 backend 子目录")
    print("-" * 60)

    backend_files = {
        'app.py': project_root / 'backend' / 'app.py',
        'init_knowledge_base.py': project_root / 'backend' / 'init_knowledge_base.py',
        'fine_tuning_adapter.py': project_root / 'backend' / 'fine_tuning_adapter.py',
    }

    for name, path in backend_files.items():
        exists = path.exists()
        status = "[OK]" if exists else "[FAIL]"
        print(f"{status} {name}")
        if not exists:
            all_ok = False

    # 检查启动脚本
    print("\n" + "-" * 60)
    print("检查启动脚本")
    print("-" * 60)

    launch_scripts = {
        'START.py': project_root / 'START.py',
        'START.ps1': project_root / 'START.ps1',
        'START.bat': project_root / 'START.bat',
    }

    for name, path in launch_scripts.items():
        exists = path.exists()
        status = "[OK]" if exists else "[!] "
        print(f"{status} {name}")

    # 总结
    print("\n" + "=" * 60)
    if all_ok:
        print("[OK] 项目结构检查完成 - 所有必要文件都已找到!")
        print("\n现在可以启动系统:")
        print("   python START.py")
    else:
        print("[FAIL] 项目结构检查失败 - 缺少必要文件")
        print("\n建议:")
        print("   1. 检查是否在正确的目录下")
        print("   2. 确保所有文件都已下载")
        print("   3. 重新克隆项目或检查文件完整性")
    print("=" * 60 + "\n")

    return all_ok


if __name__ == '__main__':
    success = check_structure()
    sys.exit(0 if success else 1)