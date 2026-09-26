from typing import Literal

from pydantic import BaseModel, Field

WritingAction = Literal["continue","expand","summarize"]

class AutocompleteRequest(BaseModel):
    context: str = Field(...,min_length=1,max_length=4000)


class WritingAssistRequest(BaseModel):
    context: str = Field(..., min_length=1, max_length=2000)
    action: WritingAction = "continue"