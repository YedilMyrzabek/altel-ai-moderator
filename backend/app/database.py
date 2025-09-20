from supabase import create_client, Client
from .config import settings

def get_supabase() -> Client:
    if not settings.supabase_url or not settings.supabase_key:
        raise RuntimeError("Supabase creds missing. Check SUPABASE_URL and SUPABASE_SERVICE_KEY in .env")
    return create_client(settings.supabase_url, settings.supabase_key)

supabase = get_supabase()

def upsert_account(platform: str, handle: str, url: str, title: str | None = None) -> str:
    data = {"platform": platform, "handle": handle, "url": url, "title": title}
    res = supabase.table("accounts").upsert(data, on_conflict="platform,handle").execute()
    # supabase v2 возвращает список строк; берем id из первой
    return res.data[0]["id"]

def create_job(source_type: str, input_url: str) -> str:
    data = {"source_type": source_type, "input_url": input_url, "status": "running"}
    res = supabase.table("jobs").insert(data).execute()
    return res.data[0]["id"]

def upsert_source(job_id: str, account_id: str, platform: str, ext_id: str,
                  title: str, author: str, published_at: str | None, raw_meta: dict | None = None) -> str:
    data = {
        "job_id": job_id,
        "account_id": account_id,
        "platform": platform,
        "ext_id": ext_id,
        "title": title,
        "author": author,
        "published_at": published_at,
        "raw_meta": raw_meta or {}
    }
    res = supabase.table("sources").upsert(data, on_conflict="platform,ext_id").execute()
    return res.data[0]["id"]

def insert_comments_batch(source_id: str, comments: list[dict]) -> int:
    rows = []
    for c in comments:
        rows.append({
            "source_id": source_id,
            "ext_comment_id": c["id"],
            "author_name": c.get("author", ""),
            "author_channel_id": c.get("author_channel_id", ""),
            "text_raw": c.get("text", ""),
            "text_norm": (c.get("text") or "").lower(),
            "created_at": c.get("published_at"),
            "lang": None,
            "status": "queued",
            "meta": {"likes": c.get("likes", 0), "updated_at": c.get("updated_at")}
        })
    if not rows:
        return 0
    res = supabase.table("comments").upsert(rows, on_conflict="source_id,ext_comment_id").execute()
    # res.data может быть None, если представление не возвращено — но по умолчанию вернётся список
    return len(res.data or rows)

def mark_job(job_id: str, status: str, stats_total: int | None = None,
             stats_processed: int | None = None, error: str | None = None) -> None:
    payload = {"status": status}
    if stats_total is not None: payload["stats_total"] = stats_total
    if stats_processed is not None: payload["stats_processed"] = stats_processed
    if error is not None: payload["error"] = error
    supabase.table("jobs").update(payload).eq("id", job_id).execute()
