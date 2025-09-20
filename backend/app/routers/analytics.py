from fastapi import APIRouter, Query
from typing import Optional
from ..database import supabase

router = APIRouter()

@router.get("/job-status")
def job_status(job_id: str):
    res = supabase.table("jobs").select("*").eq("id", job_id).limit(1).execute()
    if not res.data:
        return {"job_id": job_id, "status": "not_found"}
    row = res.data[0]
    return {
        "job_id": row["id"],
        "status": row["status"],
        "stats_total": row.get("stats_total"),
        "stats_processed": row.get("stats_processed"),
        "error": row.get("error"),
    }

@router.get("/report")
def report(limit: int = 200):
    # Используем view v_comments_full (создан ранее SQL-скриптом)
    res = supabase.table("v_comments_full").select("*").order("commented_at", desc=True).limit(limit).execute()
    return {"rows": res.data}

@router.get("/aggregates")
def aggregates():
    # Карточки KPI
    res = supabase.table("v_dashboard_aggregates").select("*").execute()
    return {"rows": res.data}
