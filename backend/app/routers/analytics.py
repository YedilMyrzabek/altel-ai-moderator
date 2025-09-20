from fastapi import APIRouter, Query, HTTPException
from typing import Optional, Any
from ..database import supabase
from fastapi.responses import StreamingResponse
import io
import csv
import json
import datetime as dt
from xml.etree.ElementTree import Element, SubElement, tostring
from openpyxl import Workbook

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
    res = supabase.table("v_comments_full").select("*").order("commented_at", desc=True).limit(limit).execute()
    return {"rows": res.data}

@router.get("/aggregates")
def aggregates():
    res = supabase.table("v_dashboard_aggregates").select("*").execute()
    return {"rows": res.data}

# ---------------------------
# NEW: Export CSV / XLSX / XML
# ---------------------------
def _query_rows(
    platform: Optional[str],
    account: Optional[str],
    source_ext_id: Optional[str],
    date_from: Optional[str],
    date_to: Optional[str],
    limit: int,
):
    q = supabase.table("v_comments_full").select("*")
    if platform:
        q = q.eq("platform", platform)
    if account:
        q = q.eq("account_handle", account)
    if source_ext_id:
        q = q.eq("source_ext_id", source_ext_id)
    # date range по commented_at (ISO8601)
    if date_from:
        q = q.gte("commented_at", date_from)
    if date_to:
        q = q.lte("commented_at", date_to)

    # сортировка от новых к старым, лимит
    q = q.order("commented_at", desc=True).limit(limit)
    res = q.execute()
    return res.data or []

def _normalize_cell(v: Any) -> Any:
    # Приводим dict/list к JSON-строке, ISO для дат, остальное как есть
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, (dt.datetime, dt.date)):
        return v.isoformat()
    return v

@router.get("/export")
def export_report(
    format: str = Query("csv", pattern="^(csv|xlsx|xml)$", description="csv|xlsx|xml"),
    platform: Optional[str] = Query(None, description="youtube|instagram|vk|..."),
    account: Optional[str] = Query(None, description="account_handle, например ALTEL5G"),
    source_ext_id: Optional[str] = Query(None, description="videoId YouTube"),
    date_from: Optional[str] = Query(None, description="ISO 8601, напр. 2025-01-01T00:00:00Z"),
    date_to: Optional[str] = Query(None, description="ISO 8601"),
    limit: int = Query(1000, ge=1, le=50000),
):
    rows = _query_rows(platform, account, source_ext_id, date_from, date_to, limit)
    if not rows:
        # Вернём пустой файл нужного формата
        rows = []

    # Заголовки берём из ключей первой строки, иначе минимум фиксированный набор
    default_headers = [
        "platform","account_handle","account_url",
        "source_ext_id","source_title",
        "comment_id","author_name","comment_text","comment_lang","comment_status","commented_at",
        "is_spam","spam_score","is_toxic","tox_score",
        "type_label","type_conf","sentiment","sent_conf",
        "reply_lang","template_id","text_reply","kb_refs","quality_flags"
    ]
    headers = list(rows[0].keys()) if rows else default_headers

    if format == "csv":
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            row_norm = {k: _normalize_cell(r.get(k)) for k in headers}
            writer.writerow(row_norm)
        buf.seek(0)
        return StreamingResponse(
            buf,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="analytics_report.csv"'}
        )

    if format == "xlsx":
        wb = Workbook(write_only=True)
        ws = wb.create_sheet("report")
        ws.append(headers)
        for r in rows:
            ws.append([_normalize_cell(r.get(k)) for k in headers])
        out = io.BytesIO()
        wb.save(out)
        out.seek(0)
        return StreamingResponse(
            out,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": 'attachment; filename="analytics_report.xlsx"'}
        )

    # xml
    root = Element("comments")
    for r in rows:
        c = SubElement(root, "comment")
        for k in headers:
            v = _normalize_cell(r.get(k))
            # вложенные JSON как текст
            el = SubElement(c, k)
            el.text = "" if v is None else str(v)
    xml_bytes = tostring(root, encoding="utf-8")
    return StreamingResponse(
        io.BytesIO(xml_bytes),
        media_type="application/xml",
        headers={"Content-Disposition": 'attachment; filename="analytics_report.xml"'}
    )
