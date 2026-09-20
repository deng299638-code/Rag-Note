from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from collections.abc import Sequence
from typing import Literal
Intent = Literal["chat","rag","note_search","note_stats","review_today","create_note","related_notes","remember","forget","working_memory",]

class QueryPlan(BaseModel):
    intent: Intent
    rewritten_query: str
    use_rag: bool
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reason: str = ""
