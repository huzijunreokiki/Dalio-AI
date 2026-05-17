"""
qa.py — 问答核心模块
调用 ChromaDB 检索相关段落，再通过 MiniMax API 生成回答
"""

from __future__ import annotations

import os
import requests
import chromadb
from chromadb.utils import embedding_functions
from dotenv import load_dotenv
from typing import Optional, List, Tuple

load_dotenv()

MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY", "")
MINIMAX_MODEL = os.getenv("MINIMAX_MODEL", "abab6.5s-chat")
CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "./chroma_db")
COLLECTION_NAME = "dalio_books"

TOP_K = 6  # 每次检索返回最相关的 chunk 数量

SYSTEM_PROMPT = """你是一位专业的投资顾问助手，你的知识完全来自于瑞·达利欧（Ray Dalio）的著作，
包括《原则》《债务危机》《理解大型债务危机》《变化中的世界秩序》等书籍。

你的职责：
1. 严格基于达利欧书中的理论、原则和框架来回答问题
2. 结合用户的具体投资问题，给出符合达利欧思想的分析和建议
3. 在回答中引用具体的达利欧原则或理论，并注明来自哪本书
4. 保持客观理性，避免绝对化建议

重要提示：
- 你的回答仅供参考，不构成正式投资建议
- 如果问题超出达利欧书中的范畴，请如实说明
- 用中文回答，语言清晰专业

回答格式：
1. 先结合达利欧的相关理论框架分析问题
2. 给出具体的思考建议
3. 最后注明参考了哪本书的哪个核心原则
"""


def get_retriever():
    """初始化并返回 ChromaDB collection"""
    embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="paraphrase-multilingual-MiniLM-L12-v2"
    )
    client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    collections = [c.name for c in client.list_collections()]
    if COLLECTION_NAME not in collections:
        raise RuntimeError(
            f"向量数据库中未找到集合 '{COLLECTION_NAME}'。\n"
            "请先运行：python ingest.py"
        )
    collection = client.get_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_fn,
    )
    return collection


def retrieve_context(collection, question: str, top_k: int = TOP_K) -> List[dict]:
    """检索与问题最相关的 chunk"""
    results = collection.query(
        query_texts=[question],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )
    chunks = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        chunks.append({
            "text": doc,
            "book": meta.get("book", "未知"),
            "page": meta.get("page", 0),
            "score": round(1 - dist, 3),  # 转为相似度（越高越相关）
        })
    return chunks


def format_context(chunks: List[dict]) -> str:
    """将检索到的 chunk 格式化为 prompt 中的上下文"""
    parts = []
    for i, chunk in enumerate(chunks, 1):
        parts.append(
            f"【参考片段 {i}】来自《{chunk['book']}》第 {chunk['page']} 页\n{chunk['text']}"
        )
    return "\n\n---\n\n".join(parts)


def call_minimax(messages: List[dict]) -> str:
    """调用 MiniMax ChatCompletion API"""
    if not MINIMAX_API_KEY:
        raise ValueError(
            "未配置 MiniMax API Key。\n"
            "请复制 .env.example 为 .env 并填入你的密钥。"
        )

    url = "https://api.minimax.chat/v1/text/chatcompletion_v2"
    headers = {
        "Authorization": f"Bearer {MINIMAX_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MINIMAX_MODEL,
        "messages": messages,
        "temperature": 0.4,
        "max_tokens": 1500,
    }

    resp = requests.post(url, json=payload, headers=headers, timeout=60)
    resp.raise_for_status()
    data = resp.json()

    # 打印完整响应，方便调试
    import json
    print("MiniMax 响应：", json.dumps(data, ensure_ascii=False, indent=2))

    # 解析响应
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise RuntimeError(f"MiniMax 响应解析失败：{data}") from e


def answer(
    question: str,
    history: Optional[List[dict]] = None,
    collection=None,
) -> Tuple[str, List[dict]]:
    """
    主问答函数

    Args:
        question: 用户问题
        history: 对话历史 [{"role": "user"/"assistant", "content": "..."}]
        collection: ChromaDB collection（可复用，避免重复初始化）

    Returns:
        (回答文本, 参考来源列表)
    """
    if collection is None:
        collection = get_retriever()

    # 1. 检索相关段落
    chunks = retrieve_context(collection, question)

    # 2. 构建 messages
    context_text = format_context(chunks)
    user_message = (
        f"以下是达利欧书中与问题相关的参考内容：\n\n{context_text}\n\n"
        f"---\n\n用户问题：{question}\n\n"
        "请基于以上参考内容，结合达利欧的投资原则，给出专业、有深度的回答。"
    )

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    # 加入历史对话（最多保留最近 6 轮，节省 token）
    if history:
        messages.extend(history[-12:])

    messages.append({"role": "user", "content": user_message})

    # 3. 调用 MiniMax
    reply = call_minimax(messages)

    return reply, chunks


# ── 命令行测试入口 ──────────────────────────────────────────────
if __name__ == "__main__":
    print("🤖 达利欧 AI 投资顾问（命令行模式）")
    print("输入 'quit' 退出\n")

    try:
        col = get_retriever()
    except RuntimeError as e:
        print(f"❌ {e}")
        exit(1)

    chat_history = []
    while True:
        q = input("你：").strip()
        if q.lower() in ("quit", "exit", "q"):
            break
        if not q:
            continue

        try:
            ans, sources = answer(q, history=chat_history, collection=col)
            print(f"\n助手：{ans}")
            print("\n📚 参考来源：")
            for s in sources[:3]:
                print(f"  《{s['book']}》第 {s['page']} 页（相关度 {s['score']}）")
            print()

            # 更新历史
            chat_history.append({"role": "user", "content": q})
            chat_history.append({"role": "assistant", "content": ans})

        except Exception as e:
            print(f"❌ 出错：{e}\n")
