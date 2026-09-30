# -*- coding: utf-8 -*-
"""
文档分块器 —— Markdown 感知分块
=================================
策略：
  1. 按 ## 标题分割为"节"（保留标题与内容在一起）
  2. 若节过长，按自然段落（\\n\\n）进一步拆分
  3. 若段落仍过长，按句子分割
  4. 重叠：相邻 chunk 在头部保留上一个 chunk 的标题行作为上下文
- 元数据：记录来源文件、chunk 序号、所在章节标题
"""

import re
from pathlib import Path
from typing import List, Dict, Tuple

from config.settings import CHUNK_SIZE, CHUNK_OVERLAP


class DocumentChunker:
    MIN_CHUNK_CHARS = 30  # 最小 chunk 字符数，过小的合并到前一个

    def __init__(self, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP):
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.stats = {"total_chars": 0, "total_chunks": 0, "files": 0}

    def _split_sections(self, text: str) -> List[Tuple[str, str]]:
        """按 ## 标题分割为 (标题, 内容) 列表"""
        sections = []
        lines = text.split('\n')
        current_title = lines[0].strip() if lines else ""
        current_body = []

        for line in lines:
            stripped = line.strip()
            if re.match(r'^#{1,2}\s+', stripped) and not re.match(r'^#{3,}', stripped):
                if current_body:
                    body_text = '\n'.join(current_body).strip()
                    if body_text:
                        sections.append((current_title, body_text))
                current_title = stripped
                current_body = []
            else:
                current_body.append(line)

        if current_body:
            body_text = '\n'.join(current_body).strip()
            if body_text:
                sections.append((current_title, body_text))

        if not sections:
            sections = [("", text.strip())]

        return sections

    def _split_sentences(self, text: str) -> List[str]:
        """按句子分割（中文句号、问号、感叹号、换行）"""
        sentences = re.split(r'(?<=[。！？.!?\n])\s*', text)
        return [s.strip() for s in sentences if s.strip()]

    def _chunk_by_size(self, text: str) -> List[str]:
        """将长文本按 chunk_size 分割（尽量在句子边界处切分）"""
        chunks = []
        sentences = self._split_sentences(text)
        current = ""
        for sent in sentences:
            if len(current) + len(sent) <= self.chunk_size:
                current += sent
            else:
                if current.strip() and len(current.strip()) >= self.MIN_CHUNK_CHARS:
                    chunks.append(current.strip())
                elif current.strip():
                    current += sent
                    continue
                if len(sent) > self.chunk_size:
                    start = 0
                    while start < len(sent):
                        end = min(start + self.chunk_size, len(sent))
                        piece = sent[start:end].strip()
                        if piece:
                            chunks.append(piece)
                        start = end - self.overlap
                    current = ""
                else:
                    current = sent
        if current.strip() and len(current.strip()) >= self.MIN_CHUNK_CHARS:
            chunks.append(current.strip())
        elif current.strip() and chunks:
            chunks[-1] = chunks[-1] + "\n" + current.strip()
        return chunks

    def chunk_document(self, content: str, source_file: str) -> List[Dict]:
        """将单个文档分块"""
        sections = self._split_sections(content)
        all_chunks = []

        for title, body in sections:
            if not body.strip():
                continue

            if title and not body.startswith(title):
                chunk_text = title + "\n" + body
            else:
                chunk_text = body

            if len(chunk_text) <= self.chunk_size:
                all_chunks.append(chunk_text)
            else:
                paragraphs = [p.strip() for p in body.split('\n\n') if p.strip()]
                current_chunk = title + "\n" if title else ""

                for para in paragraphs:
                    para_with_title = title + "\n" + para if title else para
                    if len(current_chunk) + len(para) <= self.chunk_size:
                        current_chunk += "\n\n" + para if current_chunk != (title + "\n" if title else "") else para
                    else:
                        if current_chunk.strip() and len(current_chunk.strip()) >= self.MIN_CHUNK_CHARS:
                            all_chunks.append(current_chunk.strip())
                        if len(para_with_title) > self.chunk_size:
                            sub_chunks = self._chunk_by_size(para_with_title)
                            all_chunks.extend(sub_chunks)
                            current_chunk = title + "\n" if title else ""
                        else:
                            current_chunk = para_with_title

                if current_chunk.strip() and len(current_chunk.strip()) >= self.MIN_CHUNK_CHARS:
                    all_chunks.append(current_chunk.strip())
                elif current_chunk.strip() and all_chunks:
                    all_chunks[-1] = all_chunks[-1] + "\n" + current_chunk.strip()

        # 过小的 chunk 合并到前一个
        merged_chunks = []
        for chunk in all_chunks:
            if len(chunk) < self.MIN_CHUNK_CHARS and merged_chunks:
                merged_chunks[-1] = merged_chunks[-1] + "\n" + chunk
            else:
                merged_chunks.append(chunk)

        results = []
        base_id = source_file.replace('.', '_').replace(' ', '_')
        for i, chunk_text in enumerate(merged_chunks):
            section_title = ""
            for title, _ in sections:
                if title and title.lstrip('#').strip() in chunk_text:
                    section_title = title.lstrip('#').strip()
                    break

            results.append({
                'chunk_id': f"{base_id}_{i:03d}",
                'content': chunk_text,
                'metadata': {
                    'source': source_file,
                    'chunk_index': i,
                    'chunk_size': len(chunk_text),
                    'section': section_title,
                }
            })

        self.stats["total_chars"] += len(content)
        self.stats["total_chunks"] += len(results)
        self.stats["files"] += 1

        return results

    def chunk_all(self, kb_dir: str) -> List[Dict]:
        """遍历知识库目录，分块所有 .md 文件"""
        all_chunks = []
        kb_path = Path(kb_dir)
        if not kb_path.exists():
            print(f"⚠️ 知识库目录不存在: {kb_dir}")
            return all_chunks

        md_files = sorted(kb_path.glob("*.md"))
        print(f"📄 发现 {len(md_files)} 个知识库文件")
        print(f"⚙️  分块参数: chunk_size={self.chunk_size}, overlap={self.overlap}\n")

        for md_file in md_files:
            try:
                with open(md_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                if not content.strip():
                    continue
                chunks = self.chunk_document(content, md_file.name)
                all_chunks.extend(chunks)
                print(f"   ✅ {md_file.name}: {len(content)} 字符 → {len(chunks)} 个chunk")
            except Exception as e:
                print(f"   ❌ {md_file.name}: 读取失败 ({e})")

        print(f"\n📊 分块统计: {self.stats['files']} 文件 → {self.stats['total_chunks']} chunks | "
              f"平均 chunk={self.stats['total_chars']//max(self.stats['total_chunks'],1)} 字符")
        return all_chunks
