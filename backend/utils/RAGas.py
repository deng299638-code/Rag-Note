from __future__ import annotations

import argparse
import asyncio
import datetime
import importlib
import json
import os
import sys
import types
from pathlib import Path
from typing import Any

# Allow both `python -m utils.RAGas` and `python utils/RAGas.py`.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db.db_config import SessionLocal
from db.redis_client import close_redis, init_redis
from repository.chat import ChatRepository
from repository.note import NoteRepository
from schemas.agent_schemas import AgentQueryRequest
from services.AgentService import AgentService

DEFAULT_QUERY_FILE = ROOT / "utils" / "test_query.txt"
DEFAULT_REFERENCE_FILE = ROOT / "utils" / "test_answer.txt"
DEFAULT_OUTPUT = ROOT / "data" / "ragas_results.csv"


def _read_lines(path: Path) -> list[str]:
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_cases(path: Path | None) -> list[dict[str, Any]]:
    """Load JSON/JSONL golden data, or the repository's paired txt files."""
    if path is None:
        questions = _read_lines(DEFAULT_QUERY_FILE)
        references = _read_lines(DEFAULT_REFERENCE_FILE)
        if len(questions) != len(references):
            raise ValueError("test_query.txt 与 test_answer.txt 行数不一致")
        return [{"query": q, "reference": r} for q, r in zip(questions, references)]

    if path.suffix.lower() == ".jsonl":
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, list) else payload["cases"]


def _parse_sse(event: str) -> dict[str, Any] | None:
    if not event.startswith("data:"):
        return None
    try:
        return json.loads(event.removeprefix("data:").strip())
    except json.JSONDecodeError:
        return None


async def _run_agent(agent: AgentService, query: str, user_id: int) -> str:
    session_id, messages = await agent.prepare_stream(
        AgentQueryRequest(query=query), user_id
    )
    async for event in agent.stream_response(session_id, messages, user_id):
        payload = _parse_sse(event)
        if not payload:
            continue
        if payload.get("type") == "response":
            return str(payload.get("content", ""))
        if payload.get("type") == "error":
            raise RuntimeError(str(payload.get("content", "Agent 请求失败")))
    return ""


async def _retrieve_contexts(agent: AgentService, query: str, user_id: int) -> list[str]:
    """Return separate note/knowledge chunks for Ragas context metrics."""
    plan = await agent.query_router.route(query, [])
    if not plan.use_rag:
        return []

    retrieval_query = plan.rewritten_query or query
    results = await asyncio.gather(
        agent.note_rag_service.search_notes(retrieval_query, user_id),
        agent.knowledge_rag_service.search(retrieval_query, str(user_id)),
        return_exceptions=True,
    )

    contexts: list[str] = []
    for result in results:
        if isinstance(result, Exception):
            continue
        for item in result or []:
            content = str(item.get("document", "")).strip()
            if content and content not in contexts:
                contexts.append(content)
    return contexts


async def build_dataset(cases: list[dict[str, Any]], user_id: int):
    try:
        from datasets import Dataset
    except ModuleNotFoundError as exc:
        raise RuntimeError("请先安装 ragas、datasets 和项目依赖") from exc

    await init_redis()
    try:
        async with SessionLocal() as db:
            agent = AgentService(db, ChatRepository(db), NoteRepository(db))
            rows: list[dict[str, Any]] = []
            for case in cases:
                query = str(case.get("query", case.get("user_input", ""))).strip()
                if not query:
                    continue
                try:
                    response, contexts = await asyncio.gather(
                        _run_agent(agent, query, user_id),
                        _retrieve_contexts(agent, query, user_id),
                    )
                    error = ""
                except Exception as exc:  # Keep one failed case from stopping the run.
                    response, contexts = "", []
                    print(f"评测样本失败：{query} -> {exc}")

                rows.append({
                    "user_input": query,
                    "response": response,
                    "retrieved_contexts": contexts,
                    "reference": str(case.get("reference", case.get("answer", ""))),
                })
            return Dataset.from_list(rows)
    finally:
        await close_redis()


def _ragas_metrics(use_reasoning_model: bool = True) -> list[Any]:
    """Build Ragas metrics tuned for the evaluation LLM.

    - 评测模型为思考模型（阿里 qwen3 thinking 强制 n=1）时：
      AnswerRelevancy 默认 strictness=3 会请求 n=3 次生成，接口直接 400 报错，
      降到 1 并配合 bypass_n=True 兼容。
    - 评测模型为非思考模型（如 qwen-turbo，通过 RAGAS_EVAL_MODEL 指定）时：
      恢复原生 strictness=3 多采样，指标更可靠。
    """
    _install_ragas_compat()
    try:
        # Ragas 0.4.x class API
        from ragas.metrics import (
            AnswerRelevancy,
            ContextPrecision,
            ContextRecall,
            Faithfulness,
        )
        return [
            Faithfulness(),
            AnswerRelevancy(strictness=1 if use_reasoning_model else 3),
            ContextPrecision(),
            ContextRecall(),
        ]
    except ImportError:
        # Ragas 0.3.x fallback（模块级单例）
        from ragas.metrics import (
            answer_relevancy,
            context_precision,
            context_recall,
            faithfulness,
        )
        return [faithfulness, answer_relevancy, context_precision, context_recall]


def _install_ragas_compat() -> None:
    """Bridge Ragas 0.4.3's optional Vertex import with langchain-community 0.4.x."""
    module_name = "langchain_community.chat_models.vertexai"
    if module_name in sys.modules:
        return
    try:
        importlib.import_module(module_name)
        return
    except ModuleNotFoundError:
        pass

    try:
        from langchain_community.llms.vertexai import VertexAI
        chat_vertex_ai = VertexAI
    except Exception:
        class chat_vertex_ai:  # Ragas only needs the optional type at import time.
            pass

    shim = types.ModuleType(module_name)
    shim.ChatVertexAI = chat_vertex_ai
    sys.modules[module_name] = shim


def evaluate_dataset(dataset, output: Path):
    try:
        _install_ragas_compat()
        from langchain_openai import ChatOpenAI
        from ragas import evaluate
        from ragas.llms import LangchainLLMWrapper
        from ragas.run_config import RunConfig
    except ModuleNotFoundError as exc:
        raise RuntimeError("请先安装 ragas、datasets、langchain-openai") from exc

    # 评测专用模型：
    # - 未设置 RAGAS_EVAL_MODEL → 与业务模型一致（qwen3 思考模型），走兼容模式
    # - 设置 RAGAS_EVAL_MODEL（如 qwen-turbo，非思考）→ 恢复 RAGAS 原生 n=3 多采样
    model = os.getenv("RAGAS_EVAL_MODEL", os.getenv("OPENAI_MODEL_NAME", ""))
    use_reasoning_model = os.getenv("RAGAS_EVAL_MODEL") is None

    llm = ChatOpenAI(
        model=model,
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL"),
        temperature=0,
        timeout=int(os.getenv("RAGAS_LLM_TIMEOUT", "180")),
        max_retries=int(os.getenv("RAGAS_LLM_MAX_RETRIES", "2")),
    )

    # 思考模型兼容：默认 Ragas 对 OpenAI 系模型直接传 n>1（如 AnswerRelevancy 的 n=3），
    # 阿里 qwen3 开启 thinking 时强制 n=1，会报 400 且导致 faithfulness=nan。
    # bypass_n=True 改为「重复 prompt」方式请求（每个请求 n=1）兼容思考模型；
    # 非思考评测模型则恢复原生 n 参数（多采样更可靠）。
    eval_llm = LangchainLLMWrapper(llm, bypass_n=use_reasoning_model)

    # 关键修复 2：降低并发 + 加大超时。
    # Ragas 默认 max_workers=16，思考模型推理慢，高并发极易 TimeoutError。
    run_config = RunConfig(
        max_workers=int(os.getenv("RAGAS_MAX_WORKERS", "4")),
        timeout=int(os.getenv("RAGAS_TIMEOUT", "300")),
        max_retries=int(os.getenv("RAGAS_MAX_RETRIES", "3")),
        max_wait=60,
    )

    try:
        from core.embedding_factory import create_embedding_model
        eval_embeddings = create_embedding_model()
        try:
            from ragas.embeddings import LangchainEmbeddingsWrapper
            eval_embeddings = LangchainEmbeddingsWrapper(eval_embeddings)
        except ImportError:
            pass
    except Exception:
        eval_embeddings = None

    kwargs = {
        "metrics": _ragas_metrics(use_reasoning_model),
        "llm": eval_llm,
        "run_config": run_config,
    }
    if eval_embeddings is not None:
        kwargs["embeddings"] = eval_embeddings

    result = evaluate(dataset, **kwargs)
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        result.to_pandas().to_csv(output, index=False, encoding="utf-8-sig")
    except PermissionError:
        # 目标文件被占用（如 Excel 打开中）时，自动换带时间戳的文件名，不覆盖原文件
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output = output.with_name(f"{output.stem}_{timestamp}{output.suffix}")
        result.to_pandas().to_csv(output, index=False, encoding="utf-8-sig")
        print(f"原输出文件被占用，结果已写入: {output}")
    return result


async def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the local Agent/RAG service with Ragas")
    parser.add_argument("--dataset", type=Path, help="JSON/JSONL golden set; default: utils/test_query.txt + test_answer.txt")
    parser.add_argument("--user-id", type=int, default=int(os.getenv("RAGAS_USER_ID", "4")))
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    dataset = await build_dataset(load_cases(args.dataset), args.user_id)
    result = evaluate_dataset(dataset, args.output)
    print(result)
    print(f"结果已写入: {args.output}")


if __name__ == "__main__":
    asyncio.run(main())
