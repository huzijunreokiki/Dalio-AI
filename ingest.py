"""
ingest.py — PDF 解析 + 向量索引构建
用法：python ingest.py
将 books/ 目录下所有 PDF 解析并写入 ChromaDB
"""

import os
import sys
import hashlib
from pathlib import Path

import fitz  # PyMuPDF
import chromadb
from chromadb.utils import embedding_functions
from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter

load_dotenv()

BOOKS_DIR = Path(os.getenv("BOOKS_DIR", "./books"))
CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "./chroma_db")
COLLECTION_NAME = "dalio_books"

# 每个 chunk 的大小（字符数）和重叠量
CHUNK_SIZE = 800
CHUNK_OVERLAP = 150


def extract_text_from_pdf(pdf_path: Path) -> list[dict]:
    """从 PDF 逐页提取文本，返回带元数据的段落列表"""
    doc = fitz.open(str(pdf_path))
    pages = []
    for page_num, page in enumerate(doc, start=1):
        text = page.get_text("text").strip()
        if len(text) < 50:  # 跳过几乎空白的页
            continue
        pages.append({
            "text": text,
            "book": pdf_path.stem,
            "page": page_num,
        })
    doc.close()
    print(f"  [{pdf_path.name}] 提取了 {len(pages)} 页有效文本")
    return pages


def split_pages_to_chunks(pages: list[dict]) -> list[dict]:
    """将页面文本切分为更小的 chunk，保留元数据"""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", "。", "！", "？", ".", "!", "?", " ", ""],
    )
    chunks = []
    for page in pages:
        splits = splitter.split_text(page["text"])
        for i, split in enumerate(splits):
            chunks.append({
                "text": split,
                "book": page["book"],
                "page": page["page"],
                "chunk_index": i,
            })
    return chunks


def make_chunk_id(chunk: dict) -> str:
    """生成每个 chunk 的唯一 ID"""
    raw = f"{chunk['book']}|{chunk['page']}|{chunk['chunk_index']}|{chunk['text'][:50]}"
    return hashlib.md5(raw.encode()).hexdigest()


def build_index():
    """主函数：解析所有 PDF 并写入 ChromaDB"""
    if not BOOKS_DIR.exists():
        print(f"❌ 书籍目录不存在：{BOOKS_DIR}")
        print("请在项目目录下创建 books/ 文件夹，并放入达利欧的 PDF 书籍。")
        sys.exit(1)

    pdf_files = list(BOOKS_DIR.glob("*.pdf"))
    if not pdf_files:
        print(f"❌ 在 {BOOKS_DIR} 中未找到 PDF 文件")
        sys.exit(1)

    print(f"📚 找到 {len(pdf_files)} 本书：{[f.name for f in pdf_files]}")

    # 初始化 ChromaDB（使用本地 sentence-transformers 做 embedding，免费不消耗 token）
    print("\n🔧 初始化向量数据库...")
    embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="paraphrase-multilingual-MiniLM-L12-v2"  # 支持中文
    )
    client = chromadb.PersistentClient(path=CHROMA_DB_PATH)

    # 如果集合已存在则删除重建（重新索引）
    existing = [c.name for c in client.list_collections()]
    if COLLECTION_NAME in existing:
        print(f"⚠️  已存在集合 '{COLLECTION_NAME}'，将删除后重建...")
        client.delete_collection(COLLECTION_NAME)

    collection = client.create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_fn,
        metadata={"hnsw:space": "cosine"},
    )

    total_chunks = 0
    for pdf_path in pdf_files:
        print(f"\n📖 处理：{pdf_path.name}")
        pages = extract_text_from_pdf(pdf_path)
        chunks = split_pages_to_chunks(pages)
        print(f"  切分为 {len(chunks)} 个 chunk")

        # 批量写入，每批 100 条
        batch_size = 100
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i: i + batch_size]
            collection.add(
                ids=[make_chunk_id(c) for c in batch],
                documents=[c["text"] for c in batch],
                metadatas=[
                    {"book": c["book"], "page": c["page"], "chunk_index": c["chunk_index"]}
                    for c in batch
                ],
            )
        total_chunks += len(chunks)
        print(f"  ✅ 已写入 {len(chunks)} 个 chunk")

    print(f"\n🎉 索引构建完成！共处理 {len(pdf_files)} 本书，{total_chunks} 个 chunk")
    print(f"   向量数据库保存在：{CHROMA_DB_PATH}")


if __name__ == "__main__":
    build_index()
