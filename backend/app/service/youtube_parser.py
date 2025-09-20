from googleapiclient.discovery import build
from typing import List, Dict, Optional
import re

class YouTubeParser:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.youtube = build('youtube', 'v3', developerKey=api_key)

    def extract_video_id(self, url: str) -> Optional[str]:
        patterns = [
            r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([^&\n?#]*)',
            r'youtube\.com\/embed\/([^&\n?#]*)',
        ]
        for pattern in patterns:
            m = re.search(pattern, url)
            if m:
                return m.group(1)
        return None

    def extract_channel_handle(self, channel_item: Dict) -> str:
        if channel_item and 'snippet' in channel_item:
            custom_url = channel_item['snippet'].get('customUrl', '')
            if custom_url:
                return custom_url.replace('@', '')
            return channel_item['snippet'].get('title', 'unknown')
        return 'unknown'

    def get_video_info(self, url: str) -> Dict:
        vid = self.extract_video_id(url)
        if not vid:
            raise ValueError("Invalid YouTube URL")
        video_resp = self.youtube.videos().list(part="snippet,statistics", id=vid).execute()
        if not video_resp['items']:
            raise ValueError("Video not found")
        video = video_resp['items'][0]
        snippet = video['snippet']

        channel_id = snippet['channelId']
        channel_resp = self.youtube.channels().list(part="snippet", id=channel_id).execute()
        channel = channel_resp['items'][0] if channel_resp.get('items') else {}

        return {
            "video_id": vid,
            "title": snippet.get("title", ""),
            "description": snippet.get("description", ""),
            "published_at": snippet.get("publishedAt"),
            "channel_id": channel_id,
            "channel_title": snippet.get("channelTitle", ""),
            "channel_handle": self.extract_channel_handle(channel),
            "channel_url": f"https://www.youtube.com/channel/{channel_id}",
            "view_count": int(video.get("statistics", {}).get("viewCount", 0) or 0),
            "comment_count": int(video.get("statistics", {}).get("commentCount", 0) or 0)
        }

    def parse_comments(self, video_id: str, max_results: int = 1000) -> List[Dict]:
        comments: List[Dict] = []

        # 1) Собираем ветки топ-комментариев
        req = self.youtube.commentThreads().list(
            part="snippet",  # можно поставить "snippet,replies", но мы всё равно добираем все реплаи отдельно
            videoId=video_id,
            maxResults=100,
            textFormat="plainText"
        )
        resp = req.execute()

        def push_toplevel_items(r):
            for item in r.get('items', []):
                sn = item['snippet']['topLevelComment']['snippet']
                top_level_id = item['snippet']['topLevelComment']['id']  # ВАЖНО: это parentId для реплаев
                comments.append({
                    "id": top_level_id,
                    "parent_id": None,
                    "is_reply": False,
                    "author": sn.get('authorDisplayName', ''),
                    "author_channel_id": sn.get('authorChannelId', {}).get('value', ''),
                    "text": sn.get('textOriginal') or sn.get('textDisplay', ''),  # textOriginal стабильнее
                    "likes": sn.get('likeCount', 0),
                    "published_at": sn.get('publishedAt'),
                    "updated_at": sn.get('updatedAt', sn.get('publishedAt'))
                })

        push_toplevel_items(resp)

        # Пагинация по тредам
        while resp.get('nextPageToken') and len(comments) < max_results:
            resp = self.youtube.commentThreads().list(
                part="snippet",
                videoId=video_id,
                pageToken=resp['nextPageToken'],
                maxResults=100,
                textFormat="plainText"
            ).execute()
            push_toplevel_items(resp)
            if len(comments) >= max_results:
                break

        # 2) Для каждого топ-коммента вытаскиваем ВСЕ реплаи через comments().list(parentId=...)
        # (YouTube Data API возвращает все реплаи только этим способом)
        i = 0
        while i < len(comments) and len(comments) < max_results:
            c = comments[i]
            i += 1
            if c["is_reply"]:
                continue
            parent_id = c["id"]

            # Пагинируем ответы на данный топ-комментарий
            rep_resp = self.youtube.comments().list(
                part="snippet",
                parentId=parent_id,
                maxResults=100,
                textFormat="plainText"
            ).execute()

            def push_replies(rr):
                for itm in rr.get('items', []):
                    sn = itm['snippet']
                    comments.append({
                        "id": itm['id'],
                        "parent_id": parent_id,  # привязка к топ-комменту
                        "is_reply": True,
                        "author": sn.get('authorDisplayName', ''),
                        "author_channel_id": sn.get('authorChannelId', {}).get('value', ''),
                        "text": sn.get('textOriginal') or sn.get('textDisplay', ''),
                        "likes": sn.get('likeCount', 0),
                        "published_at": sn.get('publishedAt'),
                        "updated_at": sn.get('updatedAt', sn.get('publishedAt'))
                    })

            push_replies(rep_resp)
            while rep_resp.get('nextPageToken') and len(comments) < max_results:
                rep_resp = self.youtube.comments().list(
                    part="snippet",
                    parentId=parent_id,
                    pageToken=rep_resp['nextPageToken'],
                    maxResults=100,
                    textFormat="plainText"
                ).execute()
                push_replies(rep_resp)
                if len(comments) >= max_results:
                    break

        return comments[:max_results]

