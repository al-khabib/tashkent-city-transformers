from typing import Any, Dict, Optional
from pydantic import BaseModel


class ChatQuery(BaseModel):
    query: Optional[str] = None
    question: Optional[str] = None
    context_snapshot: Optional[Dict[str, Any]] = None
    context: Optional[Dict[str, Any]] = None


class PredictRequest(BaseModel):
    target_date: str
