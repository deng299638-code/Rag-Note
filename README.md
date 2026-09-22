智能笔记助手（AI Note Assistant）
一个全栈智能笔记应用：在传统笔记管理之上，集成 RAG 检索增强生成 Agent、混合检索 + 重排、多模态文档解析 与 记忆系统，让 AI 基于你自己的笔记库和知识库回答问题。
后端：FastAPI（Python 3.12）
前端：React + TypeScript + Vite
向量检索：Milvus + 混合检索（BM25 + 向量）+ BGE Reranker 重排
文档解析：PyMuPDF + RapidOCR + VLM 多模态兜底
异步任务：ARQ（基于 Redis）
测评：RAGas
