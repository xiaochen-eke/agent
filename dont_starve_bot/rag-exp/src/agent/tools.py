# -*- coding: utf-8 -*-
"""
Agent 工具集
============
定义三个工具供 Agent 自主选择调用：
  1. local_search  — 本地知识库检索（向量数据库）
  2. web_search    — 通用网络搜索
  3. vision_tool   — 视觉理解（调用视觉大模型 API）

每个工具同时提供：
  - 函数实现（实际执行逻辑）
  - JSON Schema 描述（传递给模型的 tools 参数）
"""

import sys
import os
import json
import re
from typing import List, Dict, Optional, Callable
from datetime import datetime

from openai import OpenAI

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

# 确保能导入 rag-exp 的现有模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config.settings import (
    ZHIPU_BASE_URL, ZHIPU_API_KEY, TOP_K, KNOWLEDGE_BASE_DIR
)
from src.retrieval.vector_retriever import VectorRetriever
from src.retrieval.hybrid_retriever import HybridRetriever
from src.retrieval.bm25_retriever import BM25Retriever
from src.chunker.document_chunker import DocumentChunker


# ============================================================================
# 工具 JSON Schema 定义（OpenAI / Zhipu tool_calls 格式）
# ============================================================================

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "local_search",
            "description": (
                "搜索本地知识库（基于向量语义检索+关键词混合检索）。"
                "适用场景：当用户询问概念解释、知识性问题、游戏攻略、文档内容等需要专业知识库的问题时使用。"
                "例如：'什么是RAG？'、'冬季怎么保暖？'、'肉丸怎么做？'"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "要在本地知识库中检索的查询内容",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "通用网络搜索工具，用于获取实时信息或本地知识库中没有的内容。"
                "适用场景：当用户询问实时信息（天气、新闻、股价）、最新事件或通用网络信息时使用。"
                "例如：'今天天气如何？'、'最新AI新闻'、'2026年诺贝尔奖得主是谁？'"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "要在网上搜索的查询内容",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "vision_tool",
            "description": (
                "视觉理解工具，用于分析图片内容。使用视觉大模型来理解图片中的物体、场景、文字等信息。"
                "适用场景：当用户提供图片URL并询问图片相关内容时使用。"
                "例如：'这张图片里有什么动物？'、'请描述这张图片'、'图片中的文字是什么？'"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "image_url": {
                        "type": "string",
                        "description": "需要分析的图片的URL地址",
                    },
                    "question": {
                        "type": "string",
                        "description": "关于该图片的具体问题",
                    },
                },
                "required": ["image_url", "question"],
            },
        },
    },
]


# ============================================================================
# 工具函数实现
# ============================================================================

class ToolImplementations:
    """三个工具的具体实现"""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or ZHIPU_API_KEY
        _timeout = httpx.Timeout(180.0, connect=30.0) if HAS_HTTPX else 180.0
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=ZHIPU_BASE_URL,
            timeout=_timeout,
            max_retries=3,
        )

        # ---- 延迟初始化检索器（首次使用时构建索引） ----
        self._vector_retriever: Optional[VectorRetriever] = None
        self._hybrid_retriever: Optional[HybridRetriever] = None
        self._index_ready = False

        # ---- 调用日志 ----
        self.call_log: List[Dict] = []

    def _ensure_index(self):
        """确保本地知识库索引已构建"""
        if self._index_ready:
            return

        print("🔧 正在初始化本地知识库索引...")
        chunker = DocumentChunker()
        chunks = chunker.chunk_all(KNOWLEDGE_BASE_DIR)

        if not chunks:
            print("⚠️ 知识库为空，本地检索将不可用")
            self._index_ready = True
            return

        bm25 = BM25Retriever()
        bm25.build_index(chunks)

        self._vector_retriever = VectorRetriever(self.api_key)
        self._vector_retriever.build_index(chunks)

        self._hybrid_retriever = HybridRetriever(bm25, self._vector_retriever)
        self._index_ready = True
        print("✅ 本地知识库索引就绪\n")

    # ---- 工具 1: 本地知识库检索 ----
    def local_search(self, query: str) -> str:
        """
        本地知识库检索：基于向量语义 + BM25 关键词混合检索
        返回格式化的检索结果文本
        """
        self._ensure_index()
        self._log("local_search", {"query": query})

        if self._hybrid_retriever is None:
            return "[本地检索] 知识库索引未就绪，无法执行检索。"

        try:
            results = self._hybrid_retriever.retrieve(query, k=TOP_K)

            if not results:
                return "[本地检索] 未找到相关知识。知识库中暂无与查询匹配的内容。"

            # 格式化检索结果
            parts = [f"本地知识库检索结果（共 {len(results)} 条相关文档）:\n"]
            for i, doc in enumerate(results):
                source = doc.get('metadata', {}).get('source', '未知来源')
                section = doc.get('metadata', {}).get('section', '')
                fusion_score = doc.get('fusion_score', doc.get('score', 0))
                content = doc.get('content', '')[:500]  # 截断过长内容

                parts.append(f"【文档 {i+1}】来源: {source}" +
                           (f" | 章节: {section}" if section else "") +
                           f" | 相关度: {fusion_score:.4f}")
                parts.append(f"{content}\n")

            self._log_result("local_search", f"找到 {len(results)} 条结果")
            return "\n".join(parts)

        except Exception as e:
            self._log_result("local_search", f"错误: {str(e)}")
            return f"[本地检索] 检索过程出错: {str(e)}"

    # ---- 工具 2: 通用网络搜索 ----
    def web_search(self, query: str) -> str:
        """
        通用网络搜索
        尝试多种方式获取搜索结果，优先使用 requests + DuckDuckGo
        """
        self._log("web_search", {"query": query})

        # 方式 A: 尝试 Bing 搜索（国内可访问）
        try:
            result = self._bing_search(query)
            if result and "未找到" not in result:
                self._log_result("web_search", "Bing搜索成功")
                return result
        except Exception as e:
            print(f"   ⚠️ Bing搜索失败: {e}")

        # 方式 B: 尝试 DuckDuckGo 搜索
        try:
            result = self._duckduckgo_search(query)
            if result and "未找到" not in result:
                self._log_result("web_search", "DuckDuckGo搜索成功")
                return result
        except Exception as e:
            print(f"   ⚠️ DuckDuckGo搜索失败: {e}")

        # 方式 C: 使用 GLM 模型凭借自身知识回答（注入当前日期）
        try:
            result = self._glm_web_search(query)
            if result and "未找到" not in result:
                self._log_result("web_search", "GLM内置搜索成功")
                return result
        except Exception as e:
            print(f"   ⚠️ GLM内置搜索失败: {e}")

        # 方式 D: 回退
        today_str = datetime.now().strftime('%Y年%m月%d日 %H:%M')
        fallback = (
            f"[网络搜索] 关于「{query}」的搜索结果：\n"
            f"⚠️ 当前网络搜索服务不可用。今天是{today_str}。\n"
            f"建议：请检查网络连接。"
        )
        self._log_result("web_search", "回退: 全部搜索方式不可用")
        return fallback

    def _bing_search(self, query: str, max_results: int = 5) -> str:
        """使用 Bing 搜索（国内可访问）"""
        import urllib.parse
        import urllib.request

        url = f"https://www.bing.com/search?q={urllib.parse.quote(query)}&count={max_results}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }

        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            html = response.read().decode('utf-8', errors='ignore')

        # 解析 Bing 搜索结果
        results = []
        # Bing 结果在 <li class="b_algo"> 中
        block_pattern = re.compile(
            r'<li[^>]*class="b_algo"[^>]*>(.*?)</li>',
            re.DOTALL
        )
        link_pattern = re.compile(
            r'<a[^>]*href="(https?://[^"]+)"[^>]*>(.*?)</a>',
            re.DOTALL
        )
        snippet_pattern = re.compile(
            r'(?:<p[^>]*class="b_lineclamp\d*"[^>]*>(.*?)</p>|<div[^>]*class="b_caption"[^>]*>.*?<p[^>]*>(.*?)</p>)',
            re.DOTALL
        )

        blocks = block_pattern.findall(html)
        for i, block in enumerate(blocks[:max_results]):
            link_match = link_pattern.search(block)
            if not link_match:
                continue
            url_clean = link_match.group(1)
            title_clean = re.sub(r'<[^>]+>', '', link_match.group(2)).strip()
            # 找摘要
            snippet_match = snippet_pattern.search(block)
            snippet = ""
            if snippet_match:
                snippet = re.sub(r'<[^>]+>', '', snippet_match.group(0)).strip()[:300]

            results.append({
                "title": title_clean,
                "url": url_clean,
                "snippet": snippet,
            })

        if not results:
            return f"[Bing搜索] 关于「{query}」未找到相关结果。"

        parts = [f"Bing搜索结果（共 {len(results)} 条）:\n"]
        for i, r in enumerate(results):
            parts.append(f"{i+1}. **{r['title']}**")
            parts.append(f"   URL: {r['url']}")
            if r['snippet']:
                parts.append(f"   摘要: {r['snippet'][:300]}")
            parts.append("")

        return "\n".join(parts)

    def _duckduckgo_search(self, query: str, max_results: int = 5) -> str:
        """使用 requests 进行 DuckDuckGo 搜索"""
        import urllib.parse
        import urllib.request

        # DuckDuckGo HTML 搜索（无需 API key）
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            html = response.read().decode('utf-8', errors='ignore')

        # 简单解析搜索结果
        results = []
        # 匹配结果链接和摘要
        link_pattern = re.compile(
            r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
            re.DOTALL | re.IGNORECASE
        )
        snippet_pattern = re.compile(
            r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>',
            re.DOTALL | re.IGNORECASE
        )

        links = link_pattern.findall(html)
        snippets = snippet_pattern.findall(html)

        for i, (url_match, title) in enumerate(links[:max_results]):
            title_clean = re.sub(r'<[^>]+>', '', title).strip()
            url_clean = urllib.parse.unquote(url_match) if url_match else ""
            snippet = re.sub(r'<[^>]+>', '', snippets[i]).strip() if i < len(snippets) else ""

            results.append({
                "title": title_clean,
                "url": url_clean,
                "snippet": snippet,
            })

        if not results:
            return f"[网络搜索] 关于「{query}」未找到相关结果。"

        parts = [f"网络搜索结果（共 {len(results)} 条）:\n"]
        for i, r in enumerate(results):
            parts.append(f"{i+1}. **{r['title']}**")
            parts.append(f"   链接: {r['url']}")
            if r['snippet']:
                parts.append(f"   摘要: {r['snippet'][:300]}")
            parts.append("")

        return "\n".join(parts)

    def _glm_web_search(self, query: str) -> str:
        """回退方案：使用 GLM 模型凭借自身知识回答问题，注入当前日期"""
        today_str = datetime.now().strftime('%Y年%m月%d日 %H:%M')
        prompt = (
            f"注意：今天是 {today_str}。你是我的网络搜索助手。\n\n"
            f"请帮我回答以下搜索问题。如果问题需要实时数据（如天气、股价）"
            f"而你的知识截止较早，请如实说明你无法获取实时数据。\n"
            f"如果是知识性问题，请根据你的训练数据给出答案，并在答案中标注日期信息。\n\n"
            f"搜索问题: {query}\n\n"
            f"请给出简洁准确、带日期的回答。"
        )
        try:
            response = self.client.chat.completions.create(
                model="glm-4-flash",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=1024,
            )
            answer = response.choices[0].message.content
            return f"[GLM辅助回答] 关于「{query}」:\n{answer}"
        except Exception as e:
            return f"[网络搜索] 搜索失败: {str(e)}"

    # ---- 工具 3: 视觉理解 ----
    def vision_tool(self, image_url: str, question: str) -> str:
        """
        视觉理解工具
        调用 GLM-4V (智谱视觉模型) 分析图片
        下载图片 → 终端内联显示 → base64 发给视觉模型
        """
        self._log("vision_tool", {"image_url": image_url, "question": question})

        # 下载图片
        image_content = None
        ext = ".jpg"
        try:
            import urllib.request
            req = urllib.request.Request(image_url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            with urllib.request.urlopen(req, timeout=15) as resp:
                image_content = resp.read()
            import mimetypes
            content_type = resp.headers.get('Content-Type', '')
            ext = mimetypes.guess_extension(content_type) or '.jpg'
        except Exception as e:
            print(f"   ⚠️ 无法下载图片 ({e})，尝试直接使用URL...")

        # ---- 用浏览器打开图片 ----
        if image_content or True:
            try:
                import webbrowser
                webbrowser.open(image_url)
                print(f"   🖼 图片已在浏览器中打开")
            except Exception as e:
                print(f"   ⚠️ 打开图片失败: {e}")

        # ---- 发给视觉模型分析 ----
        if image_content:
            try:
                import base64
                img_base64 = base64.b64encode(image_content).decode('utf-8')
                if ext in ('.png',):
                    mime_type = "image/png"
                elif ext in ('.gif',):
                    mime_type = "image/gif"
                elif ext in ('.webp',):
                    mime_type = "image/webp"
                else:
                    mime_type = "image/jpeg"

                data_uri = f"data:{mime_type};base64,{img_base64}"

                response = self.client.chat.completions.create(
                    model="glm-4v-flash",
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": data_uri}},
                            {"type": "text", "text": question},
                        ],
                    }],
                    max_tokens=1024,
                    temperature=0.7,
                )
                answer = response.choices[0].message.content
                self._log_result("vision_tool", f"视觉分析完成(base64, {len(answer)} 字符)")
                return f"[视觉理解] 图片分析结果:\n{answer}"
            except Exception as e:
                print(f"   ⚠️ base64方式失败: {e}")

        # 方式 B: 直接使用 URL
        try:
            response = self.client.chat.completions.create(
                model="glm-4v-flash",
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": image_url}},
                        {"type": "text", "text": question},
                    ],
                }],
                max_tokens=1024,
                temperature=0.7,
            )
            answer = response.choices[0].message.content
            self._log_result("vision_tool", f"视觉分析完成(URL, {len(answer)} 字符)")
            return f"[视觉理解] 图片分析结果:\n{answer}"
        except Exception as e:
            self._log_result("vision_tool", f"错误: {str(e)}")
            return f"[视觉理解] 图片分析失败: {str(e)}"

    # ---- 日志记录 ----
    def _log(self, tool_name: str, params: Dict):
        """记录工具调用"""
        entry = {
            "tool": tool_name,
            "params": params,
            "timestamp": datetime.now().isoformat(),
            "result_summary": "",
        }
        self.call_log.append(entry)

    def _log_result(self, tool_name: str, summary: str):
        """记录工具调用结果"""
        if self.call_log and self.call_log[-1]["tool"] == tool_name:
            self.call_log[-1]["result_summary"] = summary

    def get_log(self) -> List[Dict]:
        """获取调用日志"""
        return self.call_log


# ============================================================================
# 工具名称 → 实现函数的映射
# ============================================================================

def create_tool_map(tools_impl: ToolImplementations) -> Dict[str, Callable]:
    """创建工具名 → 可调用函数的映射"""
    return {
        "local_search": tools_impl.local_search,
        "web_search": tools_impl.web_search,
        "vision_tool": tools_impl.vision_tool,
    }
