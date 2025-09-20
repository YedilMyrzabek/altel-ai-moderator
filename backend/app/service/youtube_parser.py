from googleapiclient.discovery import build
from typing import List, Dict, Optional
import re
from datetime import datetime


class YouTubeParser:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.youtube = build('youtube', 'v3', developerKey=api_key)

    async def get_video_info(self, url: str) -> Dict:
        """Получить информацию о видео и канале"""
        video_id = self.extract_video_id(url)
        if not video_id:
            raise ValueError("Invalid YouTube URL")

        # Получаем информацию о видео
        video_response = self.youtube.videos().list(
            part="snippet,statistics",
            id=video_id
        ).execute()

        if not video_response['items']:
            raise ValueError("Video not found")

        video = video_response['items'][0]
        snippet = video['snippet']

        # Получаем информацию о канале
        channel_id = snippet['channelId']
        channel_response = self.youtube.channels().list(
            part="snippet",
            id=channel_id
        ).execute()

        channel = channel_response['items'][0] if channel_response['items'] else {}

        return {
            'video_id': video_id,
            'title': snippet.get('title', ''),
            'description': snippet.get('description', ''),
            'published_at': snippet.get('publishedAt', ''),
            'channel_id': channel_id,
            'channel_title': snippet.get('channelTitle', ''),
            'channel_handle': self.extract_channel_handle(channel),
            'channel_url': f"https://www.youtube.com/channel/{channel_id}",
            'view_count': video.get('statistics', {}).get('viewCount', 0),
            'comment_count': video.get('statistics', {}).get('commentCount', 0)
        }

    async def parse_comments(self, video_id: str, max_results: int = 100) -> List[Dict]:
        """Парсинг комментариев с видео"""
        comments = []

        try:
            request = self.youtube.commentThreads().list(
                part="snippet",
                videoId=video_id,
                maxResults=100,
                textFormat="plainText"
            )

            # Получаем первую страницу
            response = request.execute()

            for item in response.get('items', []):
                comment = item['snippet']['topLevelComment']['snippet']
                comments.append({
                    'id': item['id'],
                    'author': comment['authorDisplayName'],
                    'author_channel_id': comment.get('authorChannelId', {}).get('value', ''),
                    'text': comment['textDisplay'],
                    'likes': comment.get('likeCount', 0),
                    'published_at': comment['publishedAt'],
                    'updated_at': comment.get('updatedAt', comment['publishedAt'])
                })

            # Пагинация (если есть следующая страница)
            while 'nextPageToken' in response and len(comments) < max_results:
                request = self.youtube.commentThreads().list(
                    part="snippet",
                    videoId=video_id,
                    pageToken=response['nextPageToken'],
                    maxResults=100,
                    textFormat="plainText"
                )
                response = request.execute()

                for item in response.get('items', []):
                    if len(comments) >= max_results:
                        break
                    comment = item['snippet']['topLevelComment']['snippet']
                    comments.append({
                        'id': item['id'],
                        'author': comment['authorDisplayName'],
                        'author_channel_id': comment.get('authorChannelId', {}).get('value', ''),
                        'text': comment['textDisplay'],
                        'likes': comment.get('likeCount', 0),
                        'published_at': comment['publishedAt'],
                        'updated_at': comment.get('updatedAt', comment['publishedAt'])
                    })

            return comments[:max_results]

        except Exception as e:
            print(f"Error parsing comments: {e}")
            raise

    def extract_video_id(self, url: str) -> Optional[str]:
        """Извлечение ID видео из URL"""
        patterns = [
            r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([^&\n?#]*)',
            r'youtube\.com\/embed\/([^&\n?#]*)',
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def extract_channel_handle(self, channel_data: Dict) -> str:
        """Извлечь handle канала"""
        if channel_data and 'snippet' in channel_data:
            # Попробуем customUrl или название канала
            custom_url = channel_data['snippet'].get('customUrl', '')
            if custom_url:
                return custom_url.replace('@', '')
            return channel_data['snippet'].get('title', 'unknown')
        return 'unknown'