# app/routers/parser.py

from fastapi import APIRouter, BackgroundTasks, HTTPException

from .service.instagram_parser import InstagramParser
from ..models.schemas import ParseRequest, JobStatus
from ..service.youtube_parser import YouTubeParser
from ..config import settings
from ..database import (
    upsert_account, create_job, upsert_source, insert_comments_batch, mark_job
)

router = APIRouter()


def _detect_platform_from_url(url: str) -> str:
    """Определяет платформу по URL"""
    if 'youtube.com' in url or 'youtu.be' in url:
        return 'youtube'
    elif 'instagram.com' in url or 'instagr.am' in url:
        return 'instagram'
    elif 'vk.com' in url or 'vk.ru' in url:
        return 'vk'
    elif 'facebook.com' in url or 'fb.com' in url:
        return 'facebook'
    else:
        return 'unknown'


@router.post("/start", response_model=JobStatus)
def start_parse(req: ParseRequest, background: BackgroundTasks):
    platform = _detect_platform_from_url(req.url)

    if platform == 'youtube':
        if not settings.youtube_api_key:
            raise HTTPException(500, "YOUTUBE_API_KEY is not set")
        job_id = create_job(source_type=platform, input_url=req.url)
        background.add_task(_run_youtube_ingest, job_id, req.url, req.max_comments)

    elif platform == 'instagram':
        job_id = create_job(source_type=platform, input_url=req.url)
        background.add_task(_run_instagram_ingest, job_id, req.url, req.max_comments)

    else:
        raise HTTPException(400, f"Platform '{platform}' is not supported yet")

    return JobStatus(job_id=job_id, status="running")


def _run_youtube_ingest(job_id: str, url: str, max_comments: int):
    """Существующий YouTube ингест"""
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


def _run_instagram_ingest(job_id: str, url: str, max_comments: int):
    """Instagram ингест для постов и профилей"""
    try:
        # Инициализируем парсер
        ig = InstagramParser(
            username=settings.instagram_username,
            password=None,  # Не передаем пароль если есть сессия
            session_file=settings.instagram_session_file
        )

        content_type = ig.detect_content_type(url)

        if content_type == 'post':
            # Парсим один пост
            _ingest_instagram_post(ig, job_id, url, max_comments)

        elif content_type == 'profile':
            # Парсим последние посты профиля
            _ingest_instagram_profile(ig, job_id, url, max_comments)

        else:
            raise ValueError(f"Cannot determine Instagram content type from URL: {url}")

    except Exception as e:
        mark_job(job_id, status="error", error=str(e))
        raise


def _ingest_instagram_post(ig: InstagramParser, job_id: str, url: str, max_comments: int):
    """Ингест одного Instagram поста"""

    try:
        # Получаем информацию о посте
        post_info = ig.get_post_info(url)

        # Создаём/находим account
        account_id = upsert_account(
            platform="instagram",
            handle=post_info["author_username"],
            url=post_info["author_url"],
            title=post_info["author_username"]
        )

        # Создаём source (пост)
        source_id = upsert_source(
            job_id=job_id,
            account_id=account_id,
            platform="instagram",
            ext_id=post_info["post_id"],
            title=post_info["caption"][:100] if post_info["caption"] else f"Post {post_info['post_id']}",
            author=post_info["author_username"],
            published_at=post_info["created_at"],
            raw_meta={
                "likes_count": post_info["likes_count"],
                "comments_count": post_info["comments_count"],
                "is_video": post_info["is_video"],
                "video_view_count": post_info.get("video_view_count"),
                "location": post_info.get("location"),
                "hashtags": post_info.get("hashtags", [])
            }
        )

        # Проверяем, требуется ли авторизация для комментариев
        if post_info.get("login_required_for_comments"):
            print(f"⚠️ Login required for comments. Post info saved, but comments not available.")
            mark_job(
                job_id=job_id,
                status="partial",
                stats_total=post_info["comments_count"],
                stats_processed=0,
                error="Instagram login required to fetch comments. Please add INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD to .env file."
            )
            return

        # Парсим комментарии
        comments = ig.parse_comments(post_info["post_id"], max_results=max_comments)

        if not comments:
            # Если комментариев нет или не удалось получить
            mark_job(
                job_id=job_id,
                status="done",
                stats_total=0,
                stats_processed=0
            )
            return

        # Преобразуем формат комментариев для совместимости с БД
        formatted_comments = []
        for c in comments:
            formatted_comments.append({
                "id": c["id"],
                "text": c["text"],
                "author": c["author"],
                "author_channel_id": c["author_id"],
                "published_at": c["created_at"],
                "likes": c.get("likes", 0),
                "updated_at": c["created_at"],
                "parent_comment_id": c.get("parent_comment_id")
            })

        inserted = insert_comments_batch(source_id, formatted_comments)

        # Обновляем статус job
        mark_job(
            job_id=job_id,
            status="done",
            stats_total=len(comments),
            stats_processed=inserted
        )
    except Exception as e:
        print(f"❌ Error in Instagram post ingestion: {str(e)}")
        raise


def _ingest_instagram_profile(ig: InstagramParser, job_id: str, url: str, max_comments: int):
    """Ингест последних постов Instagram профиля"""

    username = ig.extract_username_from_url(url)
    if not username:
        raise ValueError(f"Cannot extract username from URL: {url}")

    # Парсим профиль (10 последних постов, по 100 комментариев на пост)
    profile_data = ig.parse_profile_posts(
        username=username,
        max_posts=10,
        max_comments_per_post=min(max_comments // 10, 100)  # Распределяем лимит
    )

    # Создаём account для профиля
    account_id = upsert_account(
        platform="instagram",
        handle=profile_data["profile"]["username"],
        url=profile_data["profile"]["url"],
        title=profile_data["profile"]["full_name"] or profile_data["profile"]["username"]
    )

    total_comments = 0
    total_inserted = 0

    # Обрабатываем каждый пост
    for post_data in profile_data["posts"]:
        # Создаём source для каждого поста
        source_id = upsert_source(
            job_id=job_id,
            account_id=account_id,
            platform="instagram",
            ext_id=post_data["post_id"],
            title=post_data["caption"][:100] if post_data["caption"] else f"Post {post_data['post_id']}",
            author=profile_data["profile"]["username"],
            published_at=post_data["created_at"],
            raw_meta={
                "likes": post_data["likes"],
                "comments_count": post_data["comments_count"],
                "is_video": post_data["is_video"],
                "video_views": post_data.get("video_views")
            }
        )

        # Вставляем комментарии
        if post_data["comments"]:
            formatted_comments = []
            for c in post_data["comments"]:
                formatted_comments.append({
                    "id": c["id"],
                    "text": c["text"],
                    "author": c["author"],
                    "author_channel_id": c["author_id"],
                    "published_at": c.get("created_at"),
                    "likes": c.get("likes", 0),
                    "updated_at": c.get("created_at"),
                    "parent_comment_id": c.get("parent_comment_id")
                })

            inserted = insert_comments_batch(source_id, formatted_comments)
            total_comments += len(post_data["comments"])
            total_inserted += inserted

    # Обновляем статус job
    mark_job(
        job_id=job_id,
        status="done",
        stats_total=total_comments,
        stats_processed=total_inserted
    )

    print(f"✅ Instagram profile ingestion complete: {total_inserted}/{total_comments} comments")


@router.get("/platforms", summary="Get supported platforms")
def get_supported_platforms():
    """Возвращает список поддерживаемых платформ"""
    return {
        "supported": [
            {
                "platform": "youtube",
                "status": "active",
                "url_patterns": ["youtube.com/watch", "youtu.be/"],
                "features": ["video_comments", "channel_info"]
            },
            {
                "platform": "instagram",
                "status": "active",
                "url_patterns": ["instagram.com/p/", "instagram.com/reel/", "instagram.com/{username}"],
                "features": ["post_comments", "profile_posts", "stories_not_supported"]
            }
        ],
        "planned": ["vk", "facebook", "tiktok"]
    }