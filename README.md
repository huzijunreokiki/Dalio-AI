# 📈 达利欧 AI 投资顾问

基于 RAG 技术，将瑞·达利欧的著作作为知识库，通过 MiniMax AI 回答投资问题。

## 项目结构

```
dalio-ai/
├── books/          ← 把达利欧的 PDF 书籍放这里
├── chroma_db/      ← 向量数据库（自动生成）
├── ingest.py       ← 第一步：解析 PDF，构建索引
├── qa.py           ← 问答核心逻辑
├── app.py          ← Streamlit 网页界面
├── requirements.txt
└── .env            ← 你的 API 密钥（从 .env.example 复制）
```

## 快速开始

### 第一步：安装依赖

```bash
pip install -r requirements.txt
```

### 第二步：配置 API 密钥

```bash
cp .env.example .env
```

编辑 `.env`，填入你的 MiniMax 密钥：

```
MINIMAX_API_KEY=你的API Key
MINIMAX_GROUP_ID=你的Group ID
```

在 [MiniMax 平台](https://platform.minimaxi.com) 登录后可以在「API 密钥」中获取。

### 第三步：放入 PDF 书籍

将达利欧的书籍（PDF 格式）放入 `books/` 目录：

```
books/
├── 原则.pdf
├── 债务危机.pdf
├── 变化中的世界秩序.pdf
└── ...
```

### 第四步：构建知识库索引（只需运行一次）

```bash
python ingest.py
```

这一步会解析所有 PDF，生成向量索引，存入 `chroma_db/`。  
时间取决于书的数量，通常几分钟内完成。

### 第五步：启动应用

```bash
streamlit run app.py
```

浏览器会自动打开 `http://localhost:8501`，即可开始提问。

---

## 推荐问题示例

- 如何用达利欧的框架判断当前经济周期处于哪个阶段？
- 全天候投资组合是什么？怎么配置？
- 达利欧如何看待通货膨胀和黄金的关系？
- 在债务危机中，普通投资者应该如何保护资产？
- 美元霸权衰退对投资策略有什么影响？

---

## 技术说明

| 组件 | 技术选型 | 说明 |
|------|---------|------|
| PDF 解析 | PyMuPDF | 速度快，中文支持好 |
| 文本切分 | LangChain RecursiveTextSplitter | 保留语义完整性 |
| Embedding | sentence-transformers (本地) | 免费，支持中文 |
| 向量数据库 | ChromaDB (本地) | 零配置，持久化 |
| LLM | MiniMax abab6.5s-chat | Token Plan 性价比高 |
| 前端 | Streamlit | 快速搭建，无需前端经验 |

### Token 消耗估算

每次问答约消耗 1000-2000 tokens（检索上下文 + 回答），MiniMax Token Plan 下成本极低。

---

## 常见问题

**Q: 运行 ingest.py 时提示找不到模型文件？**  
A: 第一次运行会自动下载 sentence-transformers 模型（约 400MB），需要网络连接。

**Q: 如何添加新书？**  
A: 把新 PDF 放入 `books/` 目录，重新运行 `python ingest.py` 即可。

**Q: 回答质量不佳怎么办？**  
A: 尝试调整 `qa.py` 中的 `TOP_K`（增大检索数量）或 `CHUNK_SIZE`（调整切分粒度）。

---

⚠️ **免责声明**：本工具仅供学习和参考，不构成任何投资建议。投资有风险，入市需谨慎。
