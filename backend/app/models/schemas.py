from pydantic import BaseModel, Field
from typing import Optional, List, Dict

# ---- Requests ----
class ParseRequest(BaseModel):
    url: str
    max_comments: int = 500

# ---- Responses ----
class JobStatus(BaseModel):
    job_id: str
    status: str
    stats_total: Optional[int] = None
    stats_processed: Optional[int] = None
    error: Optional[str] = None

class CommentRow(BaseModel):
    comment_id: str = Field(alias="id")
    ext_comment_id: str
    author_name: Optional[str] = None
    text_raw: str
    lang: Optional[str] = None
    status: str

class AnalyticsRow(BaseModel):
    platform: str
    handle: Optional[str]
    spam_cnt: int
    toxic_cnt: int
    total_cnt: int
    spam_pct: float
    toxic_pct: float
