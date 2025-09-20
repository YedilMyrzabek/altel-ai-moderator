# app/service/instagram_parser.py

import instaloader
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import re
import time
import random
from pathlib import Path
import os
import json


class InstagramParser:
    def __init__(self, username: Optional[str] = None, password: Optional[str] = None,
                 session_file: Optional[str] = None):
        """
        Инициализация Instagram парсера через Instaloader

        Args:
            username: Instagram логин
            password: Instagram пароль (не нужен если есть сессия)
            session_file: Путь к файлу сессии
        """
        # Настройки для обхода rate limiting
        self.L = instaloader.Instaloader(
            download_pictures=False,
            download_videos=False,
            download_video_thumbnails=False,
            compress_json=False,
            download_comments=True,
            save_metadata=False,
            quiet=True,
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            dirname_pattern='temp',
            filename_pattern='{date}',
            request_timeout=300,  # Увеличили таймаут
            fatal_status_codes=[429],  # 429 = Too Many Requests
            max_connection_attempts=3  # Меньше попыток переподключения
        )

        # Настройки rate limiting
        self.L.context._session.headers.update({
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept': '*/*',
            'Connection': 'keep-alive',
        })

        self.logged_in = False
        self.username = username
        self.last_request_time = None
        self.min_delay_between_requests = 3  # Минимальная задержка между запросами

        # Приоритет: 1) переданный session_file, 2) из ENV, 3) стандартный путь Instaloader
        if session_file and os.path.exists(session_file):
            self.session_file = session_file
        elif username:
            # Проверяем стандартный путь Instaloader
            default_session = Path.home() / f".config/instaloader/session-{username}"
            windows_session = Path.home() / f"AppData/Local/Instaloader/session-{username}"

            if windows_session.exists():
                self.session_file = str(windows_session)
            elif default_session.exists():
                self.session_file = str(default_session)
            else:
                self.session_file = f"./sessions/{username}"
        else:
            self.session_file = None

        # Попытка загрузить существующую сессию
        if self.username and self.session_file and os.path.exists(self.session_file):
            try:
                self.L.load_session_from_file(self.username, self.session_file)
                self.logged_in = True
                print(f"✅ Session loaded for {self.username}")

                # НЕ проверяем сессию сразу чтобы избежать rate limit
                # Проверка произойдет при первом реальном запросе

            except Exception as e:
                print(f"⚠️ Failed to load session: {e}")
                self.logged_in = False

        # Если сессия не загрузилась и есть пароль, пытаемся войти
        if not self.logged_in and username and password:
            self._login_with_retry(username, password)

    def _login_with_retry(self, username: str, password: str, max_retries: int = 3):
        """Вход с повторными попытками при ошибке"""
        for attempt in range(max_retries):
            try:
                wait_time = (attempt + 1) * 30  # 30, 60, 90 секунд
                if attempt > 0:
                    print(f"⏳ Waiting {wait_time} seconds before retry...")
                    time.sleep(wait_time)

                self.L.login(username, password)
                self.logged_in = True
                print(f"✅ Logged in as {username}")

                # Сохраняем сессию
                if self.session_file:
                    os.makedirs(os.path.dirname(self.session_file) or ".", exist_ok=True)
                    self.L.save_session_to_file(self.session_file)
                    print(f"✅ Session saved to {self.session_file}")
                break

            except instaloader.exceptions.ConnectionException as e:
                if "Please wait a few minutes" in str(e):
                    print(f"⚠️ Rate limited on login attempt {attempt + 1}/{max_retries}")
                    if attempt == max_retries - 1:
                        print(f"❌ Failed to login after {max_retries} attempts due to rate limiting")
                        self.logged_in = False
                else:
                    raise e
            except Exception as e:
                print(f"⚠️ Login failed: {e}")
                self.logged_in = False
                break

    def _wait_if_needed(self):
        """Ждёт перед следующим запросом чтобы избежать rate limiting"""
        if self.last_request_time:
            elapsed = (datetime.now() - self.last_request_time).total_seconds()
            if elapsed < self.min_delay_between_requests:
                wait_time = self.min_delay_between_requests - elapsed + random.uniform(0.5, 2.0)
                print(f"⏳ Waiting {wait_time:.1f}s to avoid rate limiting...")
                time.sleep(wait_time)

        self.last_request_time = datetime.now()

    def extract_post_id_from_url(self, url: str) -> str:
        """
        Извлекает shortcode поста из URL

        Examples:
            https://www.instagram.com/p/C1234567890/
            https://www.instagram.com/reel/C1234567890/
        """
        patterns = [
            r'/p/([A-Za-z0-9_-]+)',
            r'/reel/([A-Za-z0-9_-]+)',
            r'/tv/([A-Za-z0-9_-]+)'
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        raise ValueError(f"Could not extract post ID from URL: {url}")

    def extract_username_from_url(self, url: str) -> Optional[str]:
        """
        Извлекает username из URL профиля

        Example:
            https://www.instagram.com/altel_kazakhstan/
        """
        match = re.search(r'instagram\.com/([A-Za-z0-9_.]+)', url)
        if match:
            username = match.group(1)
            # Убираем слэш и служебные пути
            if username not in ['p', 'reel', 'tv', 'explore', 'accounts']:
                return username
        return None

    def get_post_info(self, url: str, retry_count: int = 3) -> Dict:
        """
        Получает информацию о посте Instagram с retry логикой

        Returns:
            Dict с информацией о посте
        """
        last_error = None

        for attempt in range(retry_count):
            try:
                if attempt > 0:
                    wait_time = (attempt + 1) * 60  # 60, 120, 180 секунд
                    print(f"⏳ Waiting {wait_time}s before retry {attempt + 1}/{retry_count}...")
                    time.sleep(wait_time)

                self._wait_if_needed()

                shortcode = self.extract_post_id_from_url(url)
                post = instaloader.Post.from_shortcode(self.L.context, shortcode)

                # Собираем базовую информацию
                info = {
                    "post_id": shortcode,
                    "url": f"https://www.instagram.com/p/{shortcode}/",
                    "author_username": post.owner_username,
                    "author_id": str(post.owner_id),
                    "author_url": f"https://www.instagram.com/{post.owner_username}/",
                    "caption": post.caption or "",
                    "likes_count": post.likes,
                    "comments_count": post.comments,
                    "created_at": post.date_utc.isoformat() if post.date_utc else None,
                    "is_video": post.is_video,
                    "video_view_count": post.video_view_count if post.is_video else None,
                    "location": post.location.name if post.location else None,
                    "hashtags": list(post.caption_hashtags) if post.caption_hashtags else [],
                    "login_required_for_comments": not self.logged_in
                }

                return info

            except instaloader.exceptions.ConnectionException as e:
                last_error = e
                if "Please wait a few minutes" in str(e) or "429" in str(e):
                    print(f"⚠️ Rate limited on attempt {attempt + 1}/{retry_count}")
                else:
                    raise e
            except Exception as e:
                last_error = e
                print(f"❌ Error on attempt {attempt + 1}: {e}")

        raise Exception(f"Failed to get post info after {retry_count} attempts: {last_error}")

    def parse_comments(self, post_id: str, max_results: int = 500) -> List[Dict]:
        """
        Парсит комментарии к посту Instagram с обработкой rate limiting

        Args:
            post_id: Shortcode поста
            max_results: Максимальное количество комментариев

        Returns:
            List[Dict] с комментариями
        """
        comments = []

        # Проверяем авторизацию
        if not self.logged_in:
            print(f"⚠️ Not logged in. Cannot fetch comments.")
            return []

        max_retries = 3
        for retry in range(max_retries):
            try:
                if retry > 0:
                    # Экспоненциальная задержка: 2 мин, 5 мин, 10 мин
                    wait_time = min(120 * (2 ** retry), 600)
                    print(f"⏳ Rate limited. Waiting {wait_time}s before retry {retry + 1}/{max_retries}...")
                    time.sleep(wait_time)

                self._wait_if_needed()

                post = instaloader.Post.from_shortcode(self.L.context, post_id)

                # Проверяем, доступны ли комментарии
                if post.comments == 0:
                    print(f"ℹ️ Post {post_id} has no comments")
                    return []

                print(f"📥 Fetching up to {max_results} comments from post {post_id}...")

                comment_count = 0
                for comment in post.get_comments():
                    if comment_count >= max_results:
                        break

                    try:
                        # Добавляем случайную задержку между комментариями
                        if comment_count > 0 and comment_count % 10 == 0:
                            delay = random.uniform(2, 5)
                            time.sleep(delay)

                        # Базовая структура комментария
                        comment_data = {
                            "id": str(comment.id),
                            "text": comment.text,
                            "author": comment.owner.username,
                            "author_id": str(comment.owner.userid),
                            "likes": getattr(comment, 'likes_count', 0),
                            "created_at": comment.created_at_utc.isoformat() if comment.created_at_utc else None,
                            "parent_comment_id": None
                        }

                        comments.append(comment_data)
                        comment_count += 1

                        # Progress update
                        if comment_count % 50 == 0:
                            print(f"  Progress: {comment_count}/{min(post.comments, max_results)} comments...")

                    except Exception as e:
                        print(f"⚠️ Error processing comment {comment_count}: {e}")
                        continue

                print(f"✅ Successfully parsed {len(comments)} comments from post {post_id}")
                return comments

            except instaloader.exceptions.ConnectionException as e:
                if "Please wait a few minutes" in str(e) or "something went wrong" in str(e):
                    print(f"⚠️ Rate limited while fetching comments (attempt {retry + 1}/{max_retries})")
                    if retry == max_retries - 1:
                        print(f"❌ Failed to fetch comments after {max_retries} attempts")
                        return comments  # Возвращаем то, что успели получить
                else:
                    raise e
            except instaloader.exceptions.LoginRequiredException:
                print(f"❌ Login required to access comments")
                return []
            except Exception as e:
                print(f"❌ Error parsing comments: {str(e)}")
                if retry == max_retries - 1:
                    return comments  # Возвращаем то, что успели получить

        return comments

    def detect_content_type(self, url: str) -> str:
        """
        Определяет тип контента по URL

        Returns:
            'post' | 'profile' | 'unknown'
        """
        if '/p/' in url or '/reel/' in url or '/tv/' in url:
            return 'post'
        elif self.extract_username_from_url(url):
            return 'profile'
        return 'unknown'

    def parse_profile_posts(self, username: str, max_posts: int = 10, max_comments_per_post: int = 100) -> Dict:
        """
        Парсит последние посты профиля и их комментарии

        Args:
            username: Instagram username
            max_posts: Максимальное количество постов для парсинга
            max_comments_per_post: Максимум комментариев на пост

        Returns:
            Dict с информацией о профиле и постах
        """
        result = {
            "profile": {},
            "posts": []
        }

        try:
            self._wait_if_needed()
            profile = instaloader.Profile.from_username(self.L.context, username)

            # Информация о профиле
            result["profile"] = {
                "username": profile.username,
                "user_id": str(profile.userid),
                "full_name": profile.full_name,
                "bio": profile.biography,
                "followers": profile.followers,
                "following": profile.followees,
                "posts_count": profile.mediacount,
                "is_verified": profile.is_verified,
                "is_business": profile.is_business_account,
                "profile_pic": profile.profile_pic_url,
                "url": f"https://www.instagram.com/{username}/"
            }

            # Парсим последние посты
            post_count = 0
            for post in profile.get_posts():
                if post_count >= max_posts:
                    break

                # Большая задержка между постами
                if post_count > 0:
                    time.sleep(random.uniform(5, 10))

                post_data = {
                    "post_id": post.shortcode,
                    "url": f"https://www.instagram.com/p/{post.shortcode}/",
                    "caption": post.caption or "",
                    "likes": post.likes,
                    "comments_count": post.comments,
                    "created_at": post.date_utc.isoformat() if post.date_utc else None,
                    "is_video": post.is_video,
                    "video_views": post.video_view_count if post.is_video else None,
                    "comments": []
                }

                # Парсим комментарии к посту
                if self.logged_in and max_comments_per_post > 0:
                    try:
                        comments = self.parse_comments(post.shortcode, max_comments_per_post)
                        post_data["comments"] = comments
                    except Exception as e:
                        print(f"Failed to parse comments for post {post.shortcode}: {e}")

                result["posts"].append(post_data)
                post_count += 1

            print(f"✅ Parsed {len(result['posts'])} posts from @{username}")
            return result

        except Exception as e:
            print(f"❌ Error parsing profile: {str(e)}")
            raise