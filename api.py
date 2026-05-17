"""
api.py — FastAPI 后端
复用 qa.py 的核心逻辑，暴露 HTTP 接口供微信小程序调用

启动：uvicorn api:app --host 0.0.0.0 --port 8000
"""

import os
import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv

from qa import answer, get_retriever

load_dotenv()

# ── 日志配置 ──────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ── 全局状态 ──────────────────────────────────────────────────
_collection = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """服务启动时加载向量数据库（只加载一次）"""
    global _collection
    logger.info("正在加载向量数据库...")
    try:
        _collection = get_retriever()
        logger.info("✅ 向量数据库加载完成")
    except RuntimeError as e:
        logger.error(f"❌ 加载失败：{e}")
        logger.error("请先运行 python ingest.py 构建索引")
    yield
    logger.info("服务关闭")


# ── FastAPI 实例 ──────────────────────────────────────────────
app = FastAPI(
    title="达利欧 AI 投资顾问 API",
    version="1.0.0",
    lifespan=lifespan,
)

# 跨域（本地开发用；生产环境建议限制为小程序域名）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── 请求 / 响应模型 ───────────────────────────────────────────
class Message(BaseModel):
    role: str   # "user" 或 "assistant"
    content: str


class AskRequest(BaseModel):
    question: str
    history: Optional[list[Message]] = []


class SourceItem(BaseModel):
    book: str
    page: int
    score: float
    text: str


class AskResponse(BaseModel):
    reply: str
    sources: list[SourceItem]


# ── 接口 ──────────────────────────────────────────────────────
@app.get("/health")
async def health():
    """健康检查，微信小程序可用此接口确认服务在线"""
    return {
        "status": "ok",
        "db_loaded": _collection is not None,
    }


@app.post("/ask", response_model=AskResponse)
async def ask(req: AskRequest):
    """
    问答接口

    请求示例：
    {
        "question": "如何应对债务危机？",
        "history": [
            {"role": "user", "content": "达利欧是谁？"},
            {"role": "assistant", "content": "..."}
        ]
    }
    """
    if _collection is None:
        raise HTTPException(
            status_code=503,
            detail="知识库未加载，请联系管理员。请先运行 python ingest.py",
        )

    question = req.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="问题不能为空")
    if len(question) > 500:
        raise HTTPException(status_code=400, detail="问题过长，请控制在 500 字以内")

    history = [{"role": m.role, "content": m.content} for m in (req.history or [])]

    logger.info(f"收到问题：{question[:50]}...")

    try:
        reply, chunks = answer(
            question=question,
            history=history,
            collection=_collection,
        )
    except ValueError as e:
        raise HTTPException(status_code=500, detail=f"配置错误：{e}，请检查 .env 中的 MINIMAX_API_KEY")
    except Exception as e:
        logger.error(f"问答出错：{e}", exc_info=True)
        raise HTTPException(status_code=500, detail="服务内部错误，请稍后重试")

    sources = [
        SourceItem(
            book=c["book"],
            page=c["page"],
            score=c["score"],
            text=c["text"][:200],  # 只返回前 200 字，节省流量
        )
        for c in chunks[:4]
    ]

    logger.info(f"回答完成，参考 {len(sources)} 条来源")
    return AskResponse(reply=reply, sources=sources)


# ── 全局异常处理 ──────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"未捕获的异常：{exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "服务器内部错误"},
    )


# ── 本地直接运行 ──────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
