# -*- coding: utf-8 -*-
"""
LangChain Agent（方式B）
========================
使用 LangChain 框架的 @tool 装饰器 + langgraph.create_react_agent
实现基于 tool_calls 的 Agent 决策机制

与方式A（原生 JSON Schema）的核心区别：
  方式A: 手动构建 JSON Schema → 手动管理对话历史 → 手动实现 ReAct 循环
  方式B: @tool 装饰器自动生成 Schema → langgraph 自动编排 ReAct → Agent 自动重试

两种方式功能等价，方式B代码量更少（~80行 vs ~200行），方式A控制粒度更细。
"""

import sys
import os
import base64
import json
import re
import urllib.request
import urllib.parse
from typing import List, Dict, Optional, Any
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config.settings import ZHIPU_BASE_URL, ZHIPU_API_KEY, TOP_K, KNOWLEDGE_BASE_DIR

# ---- LangChain / LangGraph ----
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

# ---- 复用 RAG 实验的检索器 ----
from src.retrieval.vector_retriever import VectorRetriever
from src.retrieval.hybrid_retriever import HybridRetriever
from src.retrieval.bm25_retriever import BM25Retriever
from src.chunker.document_chunker import DocumentChunker


# ============================================================================
# 全局延迟初始化检索器
# ============================================================================

_retrieval_cache: Dict[str, Any] = {}


def _get_hybrid_retriever() -> HybridRetriever:
    """延迟初始化知识库索引（仅首次调用时构建）"""
    if 'hybrid' not in _retrieval_cache:
        print("🔧 LangChain Agent 正在初始化知识库索引...")
        chunker = DocumentChunker()
        chunks = chunker.chunk_all(KNOWLEDGE_BASE_DIR)
        bm25 = BM25Retriever()
        bm25.build_index(chunks)
        vec = VectorRetriever(ZHIPU_API_KEY)
        vec.build_index(chunks)
        _retrieval_cache['hybrid'] = HybridRetriever(bm25, vec)
        print("✅ LangChain Agent 索引就绪\n")
    return _retrieval_cache['hybrid']


# ============================================================================
# 工具定义（LangChain @tool 装饰器 —— 方式B的核心）
# ============================================================================

@tool
def local_search(query: str) -> str:
    retriever = _get_hybrid_retriever()
    results = retriever.retrieve(query, k=TOP_K)

    if not results:
        return "[本地检索] 未找到相关知识。"

    parts = [f"本地知识库检索结果（共 {len(results)} 条）:\n"]
    for i, doc in enumerate(results):
        source = doc.get('metadata', {}).get('source', '未知来源')
        score = doc.get('fusion_score', doc.get('score', 0))
        content = doc.get('content', '')[:400]
        parts.append(f"【{i+1}】来源: {source} | 相关度: {score:.4f}")
        parts.append(f"{content}\n")
    return "\n".join(parts)


@tool
def web_search(query: str) -> str:
    # 方式 A: Bing 搜索
    try:
        url = f"https://www.bing.com/search?q={urllib.parse.quote(query)}&count=5"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept-Language": "zh-CN,zh;q=0.9",
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode('utf-8', errors='ignore')

        results = []
        blocks = re.findall(r'<li[^>]*class="b_algo"[^>]*>(.*?)</li>', html, re.DOTALL)
        for block in blocks[:5]:
            link_m = re.search(r'<a[^>]*href="(https?://[^"]+)"[^>]*>(.*?)</a>', block, re.DOTALL)
            if not link_m:
                continue
            title = re.sub(r'<[^>]+>', '', link_m.group(2)).strip()
            url_clean = link_m.group(1)
            snippet_m = re.search(r'<p[^>]*>(.*?)</p>', block, re.DOTALL)
            snippet = re.sub(r'<[^>]+>', '', snippet_m.group(1)).strip()[:200] if snippet_m else ""
            results.append(f"- {title}\n  URL: {url_clean}\n  摘要: {snippet}")

        if results:
            return "Bing搜索结果:\n" + "\n".join(results)
    except Exception as e:
        print(f"   ⚠️ Bing搜索失败: {e}")

    # 方式 B: DuckDuckGo
    try:
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
        results = []
        for m in re.finditer(r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>', html):
            results.append(f"- {re.sub(r'<[^>]+>', '', m.group(2)).strip()}\n  URL: {urllib.parse.unquote(m.group(1))}")
            if len(results) >= 5:
                break
        if results:
            return "DuckDuckGo搜索结果:\n" + "\n".join(results)
    except Exception as e:
        print(f"   ⚠️ DuckDuckGo搜索失败: {e}")

    # 方式 C: GLM 内置知识
    today_str = datetime.now().strftime('%Y年%m月%d日')
    return f"[GLM辅助回答，日期: {today_str}] 关于「{query}」：请基于训练知识回答，若需实时数据请说明无法获取。"


@tool
def vision_tool(image_url: str, question: str) -> str:
    import webbrowser as _wb
    try:
        _wb.open(image_url)
        print(f"   🖼 图片已在浏览器中打开")
    except Exception:
        pass
    try:
        req = urllib.request.Request(image_url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            img_data = resp.read()
        img_b64 = base64.b64encode(img_data).decode('utf-8')
        from openai import OpenAI
        client = OpenAI(api_key=ZHIPU_API_KEY, base_url=ZHIPU_BASE_URL, timeout=180)
        response = client.chat.completions.create(
            model="glm-4v-flash",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}},
                    {"type": "text", "text": question},
                ],
            }],
            max_tokens=1024,
        )
        return f"[视觉理解] 图片分析结果:\n{response.choices[0].message.content}"
    except Exception as e:
        return f"[视觉理解] 图片分析失败: {str(e)}"


# ============================================================================
# 工具列表（LangChain 自动从 @tool 生成 Schema）
# ============================================================================

TOOLS_LC = [local_search, web_search, vision_tool]


# ============================================================================
# LangGraph Agent 创建
# ============================================================================

def create_langgraph_agent(api_key: str = None):
    """
    创建基于 LangGraph 的 React Agent（LangChain 1.x 推荐方式）

    核心步骤（方式B）：
      1. @tool 装饰器 → 自动生成 tool.function JSON Schema
      2. ChatOpenAI 指向智谱 API → 模型自动接收 tool 定义
      3. create_react_agent → LangGraph 自动编排 Thought→Action→Observe→Answer
      4. agent.invoke() → 一行调用，内部自动完成 ReAct 循环

    与方式A对比：
      方式A: 需手动编写 _single_round() 循环、手工处理 tool_calls 解析、
             手工回传 tool result、手工管理对话历史
      方式B: 以上全部由 LangGraph 自动完成，只需定义 @tool 函数
    """
    key = api_key or ZHIPU_API_KEY

    # Step 1: 创建 LLM（OpenAI 兼容接口 → 指向智谱）
    llm = ChatOpenAI(
        model="glm-4-flash",
        api_key=key,
        base_url=ZHIPU_BASE_URL,
        temperature=0.7,
        max_tokens=2048,
        timeout=180,
        max_retries=3,
    )

    # Step 2: 构建 System Prompt（含日期红线）
    today_str = datetime.now().strftime('%Y年%m月%d日')
    system_prompt = (
        f"【日期】今天是{today_str}。你是具备工具调用能力的 AI Agent，自主选择工具获取信息。\n"
        "工具：local_search(知识库)、web_search(网络)、vision_tool(图片分析)。\n"
        "规则：每次只调1个工具→获取结果后立即综合回答→最多调用2次工具。\n"
        "日期红线：只能使用绝对日期，严禁编造「1天前」「上周」等相对时间。"
    )

    # Step 3: 创建 React Agent（LangGraph 一步到位）
    agent = create_react_agent(
        model=llm,
        tools=TOOLS_LC,
        prompt=system_prompt,
    )

    return agent


# ============================================================================
# 包装接口（保持与 AgentLoop 一致，方便对比）
# ============================================================================

class LangChainAgentWrapper:
    """
    LangChain Agent 包装器
    提供与方式A AgentLoop 相同的 .run() 接口
    """

    def __init__(self, api_key: str = None):
        self.agent = create_langgraph_agent(api_key)

    def run(self, user_query: str, image_url: str = None) -> Dict:
        today_tag = datetime.now().strftime('%Y年%m月%d日')
        if image_url:
            user_query = (
                f"【当前日期: {today_tag}】\n"
                f"用户问题: {user_query}\n"
                f"图片URL: {image_url}\n"
                f"请使用视觉理解工具分析这张图片，然后回答问题。"
            )
        else:
            user_query = f"【当前日期: {today_tag}】\n用户问题: {user_query}"

        messages = {"messages": [("user", user_query)]}
        try:
            result = self.agent.invoke(messages)
            # 提取最后一条 AI 消息
            last_msg = result["messages"][-1]
            answer = last_msg.content if hasattr(last_msg, 'content') else str(last_msg)
        except Exception as e:
            answer = f"[LangChain Agent] 执行失败: {str(e)}"

        return {
            "answer": answer,
            "tool_calls_made": [],
            "retry_count": 0,
            "total_rounds": 0,
            "log": [],
        }
