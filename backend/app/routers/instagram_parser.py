# app/service/instagram_parser.py

import instaloader
from datetime import datetime
from typing import List, Dict, Optional
import re
import time
from urllib.parse import urlparse


class InstagramParser:
    def __init__(self, username: Optional[str] = None, password: Optional[str] = None):
        """
        Инициализация Instagram парсера через Instaloader

        Args:
            username: Instagram логин (опционально для публичных профилей)
            password: Instagram пароль (опционально для публичных профилей)
        """
        self.L = instaloader.Instaloader(
            download_pictures=False,
            download_videos=False,
            download_video_thumbnails=False,
            compress_json=False,
            download_comments=True,
            save_metadata=False,
            quiet=True,
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )

        # Авторизация (если есть креды)
        if username and password:
            try:
                self.L.login(username, password)
                print(f"✅ Logged in as {username}")
            except Exception as e:
                print(f"⚠️ Login failed: {e}. Continuing without auth (limited access)")

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

    def get_post_info(self, url: str) -> Dict:
        """
        Получает информацию о посте Instagram

        Returns:
            Dict с информацией о посте
        """
        try:
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
                "hashtags": list(post.caption_hashtags) if post.caption_hashtags else []
            }

            return info

        except Exception as e:
            raise Exception(f"Failed to get post info: {str(e)}")

    def parse_comments(self, post_id: str, max_results: int = 500) -> List[Dict]:
        """
        Парсит комментарии к посту Instagram

        Args:
            post_id: Shortcode поста
            max_results: Максимальное количество комментариев

        Returns:
            List[Dict] с комментариями
        """
        comments = []

        try:
            post = instaloader.Post.from_shortcode(self.L.context, post_id)

            for idx, comment in enumerate(post.get_comments()):
                if idx >= max_results:
                    break

                # Базовая структура комментария
                comment_data = {
                    "id": str(comment.id),
                    "text": comment.text,
                    "author": comment.owner.username,
                    "author_id": str(comment.owner.userid),
                    "author_profile_pic": comment.owner.profile_pic_url if hasattr(comment.owner,
                                                                                   'profile_pic_url') else None,
                    "likes": comment.likes_count if hasattr(comment, 'likes_count') else 0,
                    "created_at": comment.created_at_utc.isoformat() if comment.created_at_utc else None,
                    "is_verified": comment.owner.is_verified if hasattr(comment.owner, 'is_verified') else False,
                    "parent_comment_id": None  # Instagram API не всегда даёт иерархию
                }

                # Обработка ответов на комментарии (если есть)
                if hasattr(comment, 'answers') and comment.answers:
                    for answer in comment.answers:
                        answer_data = {
                            "id": str(answer.id),
                            "text": answer.text,
                            "author": answer.owner.username,
                            "author_id": str(answer.owner.userid),
                            "author_profile_pic": answer.owner.profile_pic_url if hasattr(answer.owner,
                                                                                          'profile_pic_url') else None,
                            "likes": answer.likes_count if hasattr(answer, 'likes_count') else 0,
                            "created_at": answer.created_at_utc.isoformat() if answer.created_at_utc else None,
                            "is_verified": answer.owner.is_verified if hasattr(answer.owner, 'is_verified') else False,
                            "parent_comment_id": str(comment.id)
                        }
                        comments.append(answer_data)

                        if len(comments) >= max_results:
                            break

                comments.append(comment_data)

                # Rate limiting
                if idx % 50 == 0 and idx > 0:
                    time.sleep(2)  # Пауза каждые 50 комментариев

            print(f"✅ Parsed {len(comments)} comments from post {post_id}")
            return comments

        except Exception as e:
            print(f"❌ Error parsing comments: {str(e)}")
            raise

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
            for idx, post in enumerate(profile.get_posts()):
                if idx >= max_posts:
                    break

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
                try:
                    comments = self.parse_comments(post.shortcode, max_comments_per_post)
                    post_data["comments"] = comments
                except Exception as e:
                    print(f"Failed to parse comments for post {post.shortcode}: {e}")

                result["posts"].append(post_data)

                # Rate limiting между постами
                time.sleep(3)

            print(f"✅ Parsed {len(result['posts'])} posts from @{username}")
            return result

        except Exception as e:
            print(f"❌ Error parsing profile: {str(e)}")
            raise

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