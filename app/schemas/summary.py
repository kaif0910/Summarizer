from typing import List, Optional
from pydantic import BaseModel, Field


class MeetingSummary(BaseModel):
    summary: str = Field(..., description="Overview summary of the meeting")
    key_points: List[str] = Field(..., description="Key takeaways and points discussed")
    action_items: List[str] = Field(..., description="Action items, assignments, and follow-ups")
    participants: Optional[List[str]] = Field(None, description="List of meeting participants if identified")
