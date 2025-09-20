from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
import asyncio
import re

from ..database import db
from ..services.youtube_parser import YouTubeParser
from ..config import settings

router = APIRouter()


class ParseRequest(BaseModel):
    url: str
    platform: str = "youtube"


class ParseResponse(BaseModel):
    job_id: str
    status: str
    message: str


@router.post("/parse", response_model=ParseResponse)
async def start_parsing(
        request: ParseRequest,
        background_tasks: BackgroundTasks
):
    """Запуск парсинга URL"""
    try:
        # Создаем новый job
        job = db.create_job(
            url=request.url,
            platform=request.platform
        )

        # Запускаем парсинг в фоне
        background_tasks.add_task(
            parse_task,
            job['id'],
            request.url,
            request.platform
        )

        return ParseResponse(
            job_id=job['id'],
            status="running",
            message=f"Парсинг {request.platform} запущен"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def parse_task(job_id: str, url: str, platform: str):
    """Фоновая задача парсинга"""
    try:
        if platform == "youtube":
            parser = YouTubeParser(settings.youtube_api_key)

            # Парсим метаданные видео и канала
            video_data = await parser.get_video_info(url)

            # Создаем или находим аккаунт
            account = db.get_or_create_account(
                platform="youtube",
                handle=video_data['channel_handle'],
                url=video_data['channel_url']
            )

            # Создаем источник (видео)
            source = db.get_or_create_source(
                job_id=job_id,
                account_id=account['id'],
                platform="youtube",
                ext_id=video_data['video_id'],
                title=video_data['title'],
                author=video_data['channel_title'],
                published_at=video_data['published_at'],
                raw_meta=video_data
            )

            # Парсим комментарии
            comments = await parser.parse_comments(video_data['video_id'])

            # Подготавливаем батч для вставки
            comments_batch = []
            for comment in comments:
                # Нормализуем текст
                text_norm = normalize_text(comment['text'])

                # Детектим язык (простая эвристика)
                lang = detect_language_simple(comment['text'])

                comments_batch.append({
                    'source_id': source['id'],
                    'ext_comment_id': comment['id'],
                    'author_name': comment['author'],
                    'text_raw': comment['text'],
                    'text_norm': text_norm,
                    'lang': lang,
                    'created_at': comment.get('published_at'),
                    'meta': {
                        'likes': comment.get('likes', 0)
                    }
                })

            # Вставляем батчами по 50
            for i in range(0, len(comments_batch), 50):
                batch = comments_batch[i:i + 50]
                db.insert_comments_batch(batch)

            # Обновляем статус job
            db.update_job_status(
                job_id=job_id,
                status='done',
                stats_total=len(comments),
                stats_processed=0  # ML еще не обработал
            )

    except Exception as e:
        print(f"Error in parse_task: {e}")
        db.update_job_status(
            job_id=job_id,
            status='error',
            error_message=str(e)
        )


def normalize_text(text: str) -> str:
    """Нормализация текста для анализа"""
    # Убираем ссылки
    text = re.sub(r'http[s]?://\S+', '', text)
    # Убираем эмейлы
    text = re.sub(r'\S+@\S+', '', text)
    # Приводим к нижнему регистру
    text = text.lower().strip()
    return text


def detect_language_simple(text: str) -> str:
    """Простая детекция языка по символам"""
    # Казахские буквы
    kk_chars = set('әіңғүұқөһ')
    # Проверяем наличие
    text_lower = text.lower()

    has_kk = any(c in text_lower for c in kk_chars)
    has_cyrillic = bool(re.search('[а-я]', text_lower))
    has_latin = bool(re.search('[a-z]', text_lower))

    if has_kk:
        return 'kk'
    elif has_cyrillic and has_latin:
        return 'mixed'
    elif has_cyrillic:
        return 'ru'
    else:
        return 'unk'


@router.get("/status/{job_id}")
async def get_job_status(job_id: str):
    """Получение статуса парсинга"""
    result = db.client.table("jobs").select("*").eq("id", job_id).execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="Job not found")

    job = result.data[0]

    # Добавляем статистику
    stats = db.get_dashboard_stats(job_id)
    job['stats'] = stats

    return job


@router.get("/queue-status")
async def get_queue_status():
    """Статус очереди ML"""
    queue = db.get_ml_queue(limit=10)
    return {
        "queue_size": len(queue),
        "oldest_item": queue[0]['created_at'] if queue else None,
        "sample": queue[:3]  # Первые 3 для примера
    }