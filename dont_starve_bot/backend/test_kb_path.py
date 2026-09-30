"""
诊断知识库路径的脚本
"""
import os

# 获取脚本所在目录
script_dir = os.path.dirname(os.path.abspath(__file__))
print(f"脚本目录: {script_dir}")

# 获取项目根目录
base_dir = os.path.dirname(script_dir)
print(f"项目根目录: {base_dir}")

# 知识库路径
kb_dir = os.path.join(base_dir, "knowledge_base")
db_dir = os.path.join(script_dir, "chroma_db")

print(f"\n【知识库路径】")
print(f"知识库目录: {kb_dir}")
print(f"存在: {os.path.exists(kb_dir)}")

if os.path.exists(kb_dir):
    files = os.listdir(kb_dir)
    print(f"文件列表: {files}")
    for f in files:
        file_path = os.path.join(kb_dir, f)
        size = os.path.getsize(file_path)
        print(f"  - {f} ({size} bytes)")

print(f"\nChromaDB目录: {db_dir}")
print(f"存在: {os.path.exists(db_dir)}")

if os.path.exists(db_dir):
    files = os.listdir(db_dir)
    print(f"文件列表: {files}")
