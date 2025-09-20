from fastapi import APIRouter, BackgroundTasks, HTTPException
from ..models.schemas import ParseRequest, JobStatus
from ..service.youtube_parser import YouTubeParser
from ..config import settings
from ..database import (
    upsert_account, create_job, upsert_source, insert_comments_batch, mark_job, supabase
)

router = APIRouter()

def _platform_from_url(url: str) -> str:
    return "youtube"

@router.post("/start", response_model=JobStatus)
def start_parse(req: ParseRequest, background: BackgroundTasks):
    if not settings.youtube_api_key:
        raise HTTPException(500, "YOUTUBE_API_KEY is not set")

    platform = _platform_from_url(req.url)
    if platform != "youtube":
        raise HTTPException(400, "Only YouTube supported for now")

    # Создаём job
    job_id = create_job(source_type=platform, input_url=req.url)

    # Ингест запустим в фоне
    background.add_task(_run_youtube_ingest, job_id, req.url, req.max_comments)
    return JobStatus(job_id=job_id, status="running")

def _run_youtube_ingest(job_id: str, url: str, max_comments: int):
    try:
        yt = YouTubeParser(api_key=settings.youtube_api_key)
        v = yt.get_video_info(url)
        # account
        account_id = upsert_account(
            platform="youtube",
            handle=v["channel_title"] or v["channel_handle"] or "unknown",
            url=v["channel_url"],
            title=v["channel_title"] or "YouTube Channel"
        )
        # source (video)
        source_id = upsert_source(
            job_id=job_id,
            account_id=account_id,
            platform="youtube",
            ext_id=v["video_id"],
            title=v["title"],
            author=v["channel_title"],
            published_at=v["published_at"],
            raw_meta={"view_count": v["view_count"], "comment_count": v["comment_count"]}
        )
        # comments
        comments = yt.parse_comments(v["video_id"], max_results=max_comments)
        inserted = insert_comments_batch(source_id, comments)
        # обновим job
        mark_job(job_id, status="done", stats_total=len(comments), stats_processed=inserted)
    except Exception as e:
        mark_job(job_id, status="error", error=str(e))
        raise
