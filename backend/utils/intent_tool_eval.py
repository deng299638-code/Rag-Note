"""Evaluate query intent routing and Agent tool selection.

Example:
    python -m utils.intent_tool_eval --dataset utils/intent_tool_golden.jsonl

The tool evaluation intentionally uses the real AgentService. Use a dedicated
test user because create/remember/forget cases can change application data.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import uuid
from collections import Counter
from pathlib import Path
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_DATASET = ROOT / "utils" / "intent_tool_golden.jsonl"
DEFAULT_OUTPUT = ROOT / "data" / "intent_tool_eval.json"
VALID_INTENTS = {
    "chat",
    "rag",
    "note_search",
    "note_stats",
    "review_today",
    "create_note",
    "related_notes",
    "remember",
    "forget",
    "working_memory",
}


def load_cases(path: Path) -> list[dict[str, Any]]:
    """Load JSONL, a JSON list, or {"cases": [...]} data."""
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".jsonl":
        payload: Any = [json.loads(line) for line in text.splitlines() if line.strip()]
    else:
        payload = json.loads(text)
        if isinstance(payload, dict):
            payload = payload.get("cases", [])

    if not isinstance(payload, list):
        raise ValueError("测评集必须是 JSON 数组、JSONL，或包含 cases 数组的 JSON 对象")

    cases = []
    for index, case in enumerate(payload, start=1):
        if not isinstance(case, dict):
            raise ValueError(f"第 {index} 条样本不是对象")
        query = str(case.get("query", "")).strip()
        intent = str(case.get("expected_intent", "")).strip()
        if not query or intent not in VALID_INTENTS:
            raise ValueError(
                f"第 {index} 条样本需要有效的 query 和 expected_intent，"
                f"可选意图：{sorted(VALID_INTENTS)}"
            )
        expected_tools = case.get("expected_tools", [])
        if not isinstance(expected_tools, list) or not all(
            isinstance(item, str) and item.strip() for item in expected_tools
        ):
            raise ValueError(f"第 {index} 条样本的 expected_tools 必须是字符串数组")
        history = case.get("history", [])
        if not isinstance(history, list):
            raise ValueError(f"第 {index} 条样本的 history 必须是二维数组")
        expected_use_rag = case.get("expected_use_rag", intent == "rag")
        if not isinstance(expected_use_rag, bool):
            raise ValueError(f"第 {index} 条样本的 expected_use_rag 必须是布尔值")
        cases.append(
            {
                **case,
                "query": query,
                "expected_intent": intent,
                "expected_tools": expected_tools,
                "history": [tuple(item[:2]) for item in history if isinstance(item, list) and len(item) >= 2],
                "expected_use_rag": expected_use_rag,
            }
        )
    return cases


def parse_sse(event: str) -> dict[str, Any] | None:
    if not event.startswith("data:"):
        return None
    try:
        return json.loads(event.removeprefix("data:").strip())
    except json.JSONDecodeError:
        return None


async def evaluate_route(router: Any, case: dict[str, Any]) -> dict[str, Any]:
    try:
        plan = await router.route(case["query"], case["history"])
        return {
            "predicted_intent": plan.intent,
            "predicted_use_rag": bool(plan.use_rag),
            "confidence": float(plan.confidence),
            "reason": plan.reason,
            "rewritten_query": plan.rewritten_query,
            "route_degraded": "路由模型失败" in plan.reason,
            "error": "",
        }
    except Exception as exc:  # Keep one bad sample from stopping the report.
        return {
            "predicted_intent": "__error__",
            "predicted_use_rag": None,
            "confidence": 0.0,
            "reason": "",
            "rewritten_query": "",
            "route_degraded": False,
            "error": f"路由异常：{exc}",
        }


async def evaluate_tools(agent: Any, case: dict[str, Any], user_id: int) -> dict[str, Any]:
    """Run the real Agent and collect tool_start SSE events."""
    tools: list[str] = []
    error = ""
    # Keep the same 36-character format used by AgentService/database.
    session_id = str(uuid.uuid4())
    try:
        from schemas.agent_schemas import AgentQueryRequest

        session_id, messages = await agent.prepare_stream(
            AgentQueryRequest(query=case["query"], session_id=session_id), user_id
        )
        async for event in agent.stream_response(session_id, messages, user_id):
            payload = parse_sse(event)
            if not payload:
                continue
            if payload.get("type") == "thinking" and payload.get("stage") == "tool_start":
                content = str(payload.get("content", ""))
                tools.append(content.split("：", 1)[-1].strip())
            elif payload.get("type") == "error":
                error = str(payload.get("content", "Agent 请求失败"))
    except Exception as exc:
        error = f"Agent 异常：{exc}"
    return {"actual_tools": tools, "tool_error": error}


def _f1(precision: float, recall: float) -> float:
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def _tool_scores(expected: Sequence[str], actual: Sequence[str]) -> dict[str, Any]:
    expected_counts = Counter(expected)
    actual_counts = Counter(actual)
    matched = sum((expected_counts & actual_counts).values())
    if not expected and not actual:
        precision = recall = f1 = 1.0
    else:
        precision = matched / len(actual) if actual else 0.0
        recall = matched / len(expected) if expected else 0.0
        f1 = _f1(precision, recall)
    return {
        "exact_match": list(expected) == list(actual),
        "matched_count": matched,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def build_report(rows: list[dict[str, Any]], run_tools: bool) -> dict[str, Any]:
    total = len(rows)
    for row in rows:
        reasons = []
        if row.get("predicted_intent") != row["expected_intent"]:
            reasons.append(
                f"意图错误：期望 {row['expected_intent']}，实际 {row.get('predicted_intent')}"
            )
        if row.get("predicted_use_rag") != row.get("expected_use_rag"):
            reasons.append(
                f"use_rag 错误：期望 {row.get('expected_use_rag')}，实际 {row.get('predicted_use_rag')}"
            )
        if row.get("route_degraded"):
            reasons.append("路由模型异常并降级为 rag")
        if row.get("error"):
            reasons.append(row["error"])
        if run_tools and row.get("expected_tools", []) != row.get("actual_tools", []):
            reasons.append(
                f"工具调用错误：期望 {row.get('expected_tools', [])}，实际 {row.get('actual_tools', [])}"
            )
        if row.get("tool_error"):
            reasons.append(row["tool_error"])
        row["error_reasons"] = reasons

    expected_labels = [row["expected_intent"] for row in rows]
    predicted_labels = [row.get("predicted_intent", "__error__") for row in rows]
    labels = sorted(set(expected_labels) | set(predicted_labels))
    confusion = {
        expected: {predicted: 0 for predicted in labels}
        for expected in labels
    }
    for expected, predicted in zip(expected_labels, predicted_labels):
        confusion[expected][predicted] += 1

    f1_values = []
    for label in labels:
        tp = sum(1 for e, p in zip(expected_labels, predicted_labels) if e == label and p == label)
        fp = sum(1 for e, p in zip(expected_labels, predicted_labels) if e != label and p == label)
        fn = sum(1 for e, p in zip(expected_labels, predicted_labels) if e == label and p != label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1_values.append(_f1(precision, recall))

    route_ok = sum(e == p for e, p in zip(expected_labels, predicted_labels))
    use_rag_ok = sum(
        row.get("expected_use_rag") == row.get("predicted_use_rag")
        for row in rows
    )
    degraded = sum(bool(row.get("route_degraded")) for row in rows)
    summary: dict[str, Any] = {
        "total": total,
        "intent_accuracy": route_ok / total if total else 0.0,
        "intent_macro_f1": sum(f1_values) / len(f1_values) if f1_values else 0.0,
        "confusion_matrix": confusion,
        "route_degradation_rate": degraded / total if total else 0.0,
        "use_rag_accuracy": use_rag_ok / total if total else 0.0,
    }

    if run_tools:
        tool_rows = [_tool_scores(row["expected_tools"], row.get("actual_tools", [])) for row in rows]
        matched = sum(item["matched_count"] for item in tool_rows)
        expected_count = sum(len(row["expected_tools"]) for row in rows)
        actual_count = sum(len(row.get("actual_tools", [])) for row in rows)
        if expected_count == 0 and actual_count == 0:
            precision = recall = f1 = 1.0
        else:
            precision = matched / actual_count if actual_count else 0.0
            recall = matched / expected_count if expected_count else 0.0
            f1 = _f1(precision, recall)
        summary.update(
            {
                "tool_exact_match_rate": sum(item["exact_match"] for item in tool_rows) / total if total else 0.0,
                "tool_precision": precision,
                "tool_recall": recall,
                "tool_f1": f1,
            }
        )
        for row, score in zip(rows, tool_rows):
            row["tool_scores"] = score
    return {"summary": summary, "cases": rows}


async def run(args: argparse.Namespace) -> dict[str, Any]:
    cases = load_cases(args.dataset)
    if args.limit:
        cases = cases[: args.limit]

    # AgentService's database module loads .env as a side effect, but the
    # route-only path creates ChatOpenAI before importing that module.
    try:
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env")
    except ModuleNotFoundError:
        pass

    from langchain_openai import ChatOpenAI
    from rag.query import QueryRouter

    model = ChatOpenAI(
        model=os.getenv("OPENAI_MODEL_NAME", "qwen3.8-max"),
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL"),
        temperature=0,
    )
    router = QueryRouter(model)
    agent = None
    if not args.route_only:
        from db.db_config import SessionLocal
        from db.redis_client import close_redis, init_redis
        from repository.chat import ChatRepository
        from repository.note import NoteRepository
        from services.AgentService import AgentService

        await init_redis()
        try:
            async with SessionLocal() as db:
                agent = AgentService(db, ChatRepository(db), NoteRepository(db))
                rows = []
                for case in cases:
                    route = await evaluate_route(router, case)
                    tool_result = await evaluate_tools(agent, case, args.user_id)
                    rows.append({
                        "query": case["query"],
                        "expected_intent": case["expected_intent"],
                        "expected_use_rag": case["expected_use_rag"],
                        "expected_tools": case["expected_tools"],
                        **route,
                        **tool_result,
                    })
        finally:
            await close_redis()
    else:
        rows = []
        for case in cases:
            route = await evaluate_route(router, case)
            rows.append({
                "query": case["query"],
                "expected_intent": case["expected_intent"],
                "expected_use_rag": case["expected_use_rag"],
                "expected_tools": case["expected_tools"],
                **route,
            })

    report = build_report(rows, run_tools=not args.route_only)
    report["meta"] = {
        "dataset": str(args.dataset),
        "user_id": args.user_id,
        "route_only": args.route_only,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="测评意图路由和 Agent 工具调用准确率")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--user-id", type=int, default=int(os.getenv("INTENT_EVAL_USER_ID", "4")))
    parser.add_argument("--limit", type=int, default=0, help="只运行前 N 条样本")
    parser.add_argument("--route-only", action="store_true", help="只评测路由，不执行真实工具")
    args = parser.parse_args()
    report = asyncio.run(run(args))
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"结果已写入：{args.output}")


if __name__ == "__main__":
    main()
