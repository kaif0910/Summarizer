from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class SearchResultItem(BaseModel):
    session_id: str
    document: str
    metadata: Dict[str, Any]
    distance: Optional[float] = None


class SearchResponse(BaseModel):
    query: str
    count: int
    results: List[SearchResultItem]
