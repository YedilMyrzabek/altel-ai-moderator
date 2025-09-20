from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from ..database import supabase

router = APIRouter()

@router.get("", summary="List comments by filters")
def list_comments(
    source_ext_id: Optional[str] = Query(None, description="YouTube videoId"),
    status: Optional[str] = Query(None, description="queued|processing|done|error"),
    limit: int = 100
):
    q = supabase.table("comments").select("*").order("created_at", desc=True)
    if source_ext_id:
        # присоединяем через view для удобства - но быстрее напрямую
        # найдём source.id
        src = supabase.table("sources").select("id").eq("platform","youtube").eq("ext_id", source_ext_id).limit(1).execute()
        if not src.data:
            return {"items": []}
        source_id = src.data[0]["id"]
        q = q.eq("source_id", source_id)
    if status:
        q = q.eq("status", status)
    res = q.limit(limit).execute()
    return {"items": res.data}

@router.get("/{comment_id}", summary="Get one comment")
def get_comment(comment_id: str):
    res = supabase.table("comments").select("*").eq("id", comment_id).limit(1).execute()
    if not res.data:
        raise HTTPException(404, "Not found")
    return res.data[0]
