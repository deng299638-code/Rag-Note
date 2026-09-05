"""Milvus vector store adapter used by the existing RAG services."""

from __future__ import annotations

from typing import Any

from langchain_milvus import Milvus


def _quote(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _to_expr(condition: dict[str, Any]) -> str:
    parts: list[str] = []
    for key, value in condition.items():
        if key in ("$and", "$or"):
            children = [_to_expr(item) for item in value]
            if children:
                operator = " and " if key == "$and" else " or "
                parts.append("(" + operator.join(children) + ")")
        elif isinstance(value, dict) and "$in" in value:
            values = ", ".join(_quote(item) for item in value["$in"])
            parts.append(f"{key} in [{values}]")
        else:
            parts.append(f"{key} == {_quote(value)}")
    return " and ".join(parts)


class MilvusStore(Milvus):
    """Keep Chroma-like filters while using a Milvus collection underneath."""

    @staticmethod
    def _expression(filter_value: Any = None, where: Any = None) -> str | None:
        value = filter_value if filter_value is not None else where
        return None if value is None else _to_expr(value)

    def similarity_search(self, query: str, k: int = 4, **kwargs: Any):
        expression = kwargs.pop("expr", None) or self._expression(kwargs.pop("filter", None))
        return super().similarity_search(query, k=k, expr=expression, **kwargs)

    def similarity_search_with_score(self, query: str, k: int = 4, **kwargs: Any):
        expression = kwargs.pop("expr", None) or self._expression(kwargs.pop("filter", None))
        return super().similarity_search_with_score(query, k=k, expr=expression, **kwargs)

    def delete(self, ids=None, expr: str | None = None, **kwargs: Any):
        expression = expr or self._expression(kwargs.pop("filter", None), kwargs.pop("where", None))
        return super().delete(ids=ids, expr=expression, **kwargs)

    def get(self, include=None, where=None, filter=None, **kwargs: Any) -> dict[str, list]:
        """Return the row shape expected by the current document-management code."""
        if self.col is None:
            return {"ids": [], "documents": [], "metadatas": []}
        rows = self.client.query(
            collection_name=self.collection_name,
            filter=self._expression(filter, where) or "",
            output_fields=["*"],
            **kwargs,
        )
        vector_fields = set(self._as_list(self._vector_field))
        ids, documents, metadatas = [], [], []
        for row in rows:
            row = dict(row)
            ids.append(str(row.pop(self._primary_field)))
            documents.append(row.pop(self._text_field, ""))
            for field in vector_fields:
                row.pop(field, None)
            metadatas.append(row)
        return {"ids": ids, "documents": documents, "metadatas": metadatas}
