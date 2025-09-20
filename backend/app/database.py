from supabase import create_client, Client
from .config import settings
from typing import Optional, List, Dict
from uuid import uuid4
from datetime import datetime


class Database:
    def __init__(self):
        self.client: Client = create_client(
            settings.supabase_url,
            settings.supabase_service_key
        )

    # ACCOUNTS операции
    def get_or_create_account(self, platform: str, handle: str, url: str) -> Dict:
        """Получить или создать аккаунт"""
        # Проверяем существующий
        result = self.client.table("accounts") \
            .select("*") \
            .eq("platform", platform) \
            .eq("handle", handle) \
            .execute()

        if result.data:
            return result.data[0]

        # Создаем новый
        account_data = {
            "id": str(uuid4()),
            "platform": platform,
            "handle": handle,
            "url": url
        }
        result = self.client.table("accounts").insert(account_data).execute()
        return result.data[0]

    # JOBS операции
    def create_job(self, url: str, platform: str) -> Dict:
        """Создать новое задание парсинга"""
        job_data = {
            "id": str(uuid4()),
            "source_type": platform,
            "input_url": url,
            "status": "running",
            "stats_total": 0,
            "stats_processed": 0
        }
        result = self.client.table("jobs").insert(job_data).execute()
        return result.data[0]

    def update_job_status(self, job_id: str, status: str, **kwargs):
        """Обновить статус задания"""
        update_data = {"status": status, **kwargs}
        self.client.table("jobs") \
            .update(update_data) \
            .eq("id", job_id) \
            .execute()

    # SOURCES операции
    def get_or_create_source(self, job_id: str, account_id: str,
                             platform: str, ext_id: str, **meta) -> Dict:
        """Получить или создать источник (видео/пост)"""
        # Проверяем существующий
        result = self.client.table("sources") \
            .select("*") \
            .eq("platform", platform) \
            .eq("ext_id", ext_id) \
            .execute()

        if result.data:
            return result.data[0]

        # Создаем новый
        source_data = {
            "id": str(uuid4()),
            "job_id": job_id,
            "account_id": account_id,
            "platform": platform,
            "ext_id": ext_id,
            **meta
        }
        result = self.client.table("sources").insert(source_data).execute()
        return result.data[0]

    # COMMENTS операции
    def insert_comments_batch(self, comments: List[Dict]):
        """Вставить батч комментариев"""
        # Добавляем status='queued' к каждому
        for comment in comments:
            comment['status'] = 'queued'
            comment['id'] = str(uuid4())

        result = self.client.table("comments").insert(comments).execute()
        return result.data

    def get_ml_queue(self, limit: int = 64) -> List[Dict]:
        """Получить очередь для ML обработки"""
        result = self.client.table("v_ml_queue") \
            .select("*") \
            .order("created_at") \
            .limit(limit) \
            .execute()
        return result.data

    def update_comment_status(self, comment_id: str, status: str):
        """Обновить статус комментария"""
        self.client.table("comments") \
            .update({"status": status}) \
            .eq("id", comment_id) \
            .execute()

    # PREDICTIONS операции
    def upsert_prediction(self, comment_id: str, prediction_data: Dict):
        """Вставить или обновить предсказание"""
        prediction_data['comment_id'] = comment_id
        prediction_data['created_at'] = datetime.utcnow().isoformat()

        self.client.table("predictions") \
            .upsert(prediction_data, on_conflict="comment_id") \
            .execute()

    # RESPONSES операции
    def upsert_response(self, comment_id: str, response_data: Dict):
        """Вставить или обновить ответ"""
        response_data['comment_id'] = comment_id
        response_data['created_at'] = datetime.utcnow().isoformat()

        self.client.table("responses") \
            .upsert(response_data, on_conflict="comment_id") \
            .execute()

    # Отчеты
    def get_comments_full(self, job_id: Optional[str] = None,
                          limit: int = 200) -> List[Dict]:
        """Получить полную информацию по комментариям"""
        query = self.client.table("v_comments_full").select("*")

        if job_id:
            # Нужно будет добавить job_id в view или джойнить через sources
            pass

        result = query.order("commented_at", desc=True).limit(limit).execute()
        return result.data

    def get_dashboard_stats(self, job_id: str) -> Dict:
        """Получить статистику для дашборда"""
        # Общая статистика
        comments = self.client.table("comments") \
            .select("*", count="exact") \
            .eq("source_id", job_id) \
            .execute()

        # Статистика по predictions
        toxic = self.client.table("predictions") \
            .select("*", count="exact") \
            .eq("is_toxic", True) \
            .execute()

        spam = self.client.table("predictions") \
            .select("*", count="exact") \
            .eq("is_spam", True) \
            .execute()

        return {
            "total_comments": len(comments.data) if comments.data else 0,
            "toxic_count": len(toxic.data) if toxic.data else 0,
            "spam_count": len(spam.data) if spam.data else 0,
            "processed": len([c for c in comments.data if c.get('status') == 'done'])
        }


# Singleton
db = Database()