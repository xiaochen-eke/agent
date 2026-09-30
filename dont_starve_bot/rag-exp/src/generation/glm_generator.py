# -*- coding: utf-8 -*-
"""
GLM 生成器
==========
- 纯 GLM 回答（无知识库对比）
- GLM + RAG 上下文回答（知识增强）
"""

from typing import List, Dict

from openai import OpenAI

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

from config.settings import GLM_MODEL, GLM_PURE_MODEL, ZHIPU_BASE_URL


class GLMGenerator:
    def __init__(self, api_key: str):
        _timeout = httpx.Timeout(90.0, connect=10.0) if HAS_HTTPX else 90.0
        self.client = OpenAI(
            api_key=api_key,
            base_url=ZHIPU_BASE_URL,
            timeout=_timeout,
            max_retries=0,
        )

    def generate(self, prompt: str, model: str = GLM_MODEL,
                 temperature: float = 0.7, max_tokens: int = 2048) -> str:
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"❌ 模型调用失败: {str(e)}"

    def generate_pure(self, query: str) -> str:
        """纯 GLM 回答（无知识库）—— 用于对比实验"""
        prompt = f"请回答以下问题：\n\n{query}\n\n请给出详细的回答。"
        return self.generate(prompt, model=GLM_PURE_MODEL)

    def generate_with_context(self, query: str, context_docs: List[Dict]) -> str:
        """GLM + RAG 上下文回答 —— 知识增强生成"""
        ctx_parts = []
        for i, doc in enumerate(context_docs):
            source = doc.get('metadata', {}).get('source', doc.get('chunk_id', '未知'))
            ctx_parts.append(f"【参考文档 {i+1} · 来源: {source}】\n{doc['content']}")

        context_block = "\n\n---\n\n".join(ctx_parts)

        prompt = (
            f"你是一个《饥荒》游戏攻略专家。请严格基于以下参考知识回答问题。"
            f"如果参考知识不足以回答，请明确指出。\n\n"
            f"{context_block}\n\n"
            f"【用户问题】\n{query}\n\n"
            f"请给出详细、准确的回答，并注明信息来源。"
        )
        return self.generate(prompt, model=GLM_MODEL)
