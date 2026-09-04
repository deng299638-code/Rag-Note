from pydantic import BaseModel, Field


class AgentQueryRequest(BaseModel):
    query: str = Field(...,min_length=1,max_length=4000)
    session_id : str | None = None