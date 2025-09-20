# instagram_rate_limit_manager.py
"""
Утилита для управления rate limiting при работе с Instagram
"""

import time
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional


class RateLimitManager:
    """Менеджер для отслеживания и управления rate limits"""

    def __init__(self, cache_file: str = "instagram_rate_limit.json"):
        self.cache_file = Path(cache_file)
        self.load_state()

    def load_state(self):
        """Загружает состояние из файла"""
        if self.cache_file.exists():
            with open(self.cache_file, 'r') as f:
                self.state = json.load(f)
        else:
            self.state = {
                "last_request_time": None,
                "request_count": 0,
                "last_rate_limit_time": None,
                "rate_limit_count": 0,
                "blocked_until": None
            }

    def save_state(self):
        """Сохраняет состояние в файл"""
        with open(self.cache_file, 'w') as f:
            json.dump(self.state, f, indent=2, default=str)

    def can_make_request(self) -> tuple[bool, Optional[float]]:
        """
        Проверяет, можно ли делать запрос
        Returns: (можно_ли, время_ожидания_в_секундах)
        """
        now = datetime.now()

        # Проверяем блокировку
        if self.state["blocked_until"]:
            blocked_until = datetime.fromisoformat(self.state["blocked_until"])
            if now < blocked_until:
                wait_time = (blocked_until - now).total_seconds()
                return False, wait_time
            else:
                # Блокировка истекла
                self.state["blocked_until"] = None
                self.state["rate_limit_count"] = 0

        # Проверяем время с последнего запроса
        if self.state["last_request_time"]:
            last_time = datetime.fromisoformat(self.state["last_request_time"])
            elapsed = (now - last_time).total_seconds()

            # Минимум 3 секунды между запросами
            if elapsed < 3:
                return False, 3 - elapsed

            # Сброс счетчика если прошло больше часа
            if elapsed > 3600:
                self.state["request_count"] = 0

        # Ограничение на количество запросов в час
        if self.state["request_count"] >= 100:
            # Блокируем на час
            self.state["blocked_until"] = (now + timedelta(hours=1)).isoformat()
            self.save_state()
            return False, 3600

        return True, None

    def record_request(self):
        """Записывает успешный запрос"""
        self.state["last_request_time"] = datetime.now().isoformat()
        self.state["request_count"] += 1
        self.save_state()

    def record_rate_limit(self):
        """Записывает факт rate limiting"""
        now = datetime.now()
        self.state["last_rate_limit_time"] = now.isoformat()
        self.state["rate_limit_count"] += 1

        # Экспоненциальная задержка в зависимости от количества rate limits
        if self.state["rate_limit_count"] == 1:
            wait_minutes = 5
        elif self.state["rate_limit_count"] == 2:
            wait_minutes = 15
        elif self.state["rate_limit_count"] == 3:
            wait_minutes = 60
        else:
            wait_minutes = 240  # 4 часа

        self.state["blocked_until"] = (now + timedelta(minutes=wait_minutes)).isoformat()
        self.save_state()

        print(f"⚠️ Rate limited! Blocking for {wait_minutes} minutes")
        print(f"   This is rate limit #{self.state['rate_limit_count']} in this session")

    def reset(self):
        """Сброс всех ограничений (использовать осторожно)"""
        self.state = {
            "last_request_time": None,
            "request_count": 0,
            "last_rate_limit_time": None,
            "rate_limit_count": 0,
            "blocked_until": None
        }
        self.save_state()
        print("✅ Rate limit state reset")

    def status(self) -> Dict:
        """Возвращает текущий статус"""
        now = datetime.now()
        status = {
            "can_request": self.can_make_request()[0],
            "requests_made": self.state["request_count"],
            "requests_remaining": max(0, 100 - self.state["request_count"]),
            "rate_limit_count": self.state["rate_limit_count"]
        }

        if self.state["blocked_until"]:
            blocked_until = datetime.fromisoformat(self.state["blocked_until"])
            if now < blocked_until:
                status["blocked_for_seconds"] = (blocked_until - now).total_seconds()
                status["blocked_until"] = self.state["blocked_until"]

        return status


# Пример использования с Instagram parser
def safe_instagram_request(func, *args, **kwargs):
    """
    Обертка для безопасного выполнения Instagram запросов
    """
    manager = RateLimitManager()

    # Проверяем, можно ли делать запрос
    can_request, wait_time = manager.can_make_request()

    if not can_request:
        print(f"⏳ Rate limit active. Waiting {wait_time:.0f} seconds...")
        time.sleep(wait_time)

    try:
        # Делаем запрос
        result = func(*args, **kwargs)
        manager.record_request()
        return result

    except Exception as e:
        error_msg = str(e).lower()
        if "please wait" in error_msg or "429" in error_msg or "something went wrong" in error_msg:
            manager.record_rate_limit()
            raise
        else:
            raise


if __name__ == "__main__":
    import sys

    manager = RateLimitManager()

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "status":
            status = manager.status()
            print("\n📊 Instagram Rate Limit Status:")
            print(f"   Can make request: {'✅ Yes' if status['can_request'] else '❌ No'}")
            print(f"   Requests made: {status['requests_made']}")
            print(f"   Requests remaining: {status['requests_remaining']}")
            print(f"   Rate limit hits: {status['rate_limit_count']}")

            if 'blocked_for_seconds' in status:
                minutes = status['blocked_for_seconds'] / 60
                print(f"   Blocked for: {minutes:.1f} minutes")

        elif command == "reset":
            confirm = input("Are you sure you want to reset rate limit state? (y/n): ")
            if confirm.lower() == 'y':
                manager.reset()
            else:
                print("Reset cancelled")

        else:
            print(f"Unknown command: {command}")
            print("Usage: python instagram_rate_limit_manager.py [status|reset]")
    else:
        print("Instagram Rate Limit Manager")
        print("Usage: python instagram_rate_limit_manager.py [status|reset]")
        print("\nCurrent status:")
        status = manager.status()
        print(f"Can make request: {'Yes' if status['can_request'] else 'No'}")