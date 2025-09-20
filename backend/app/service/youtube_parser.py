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
        comments: list[dict] = []
        req = self.youtube.commentThreads().list(
            part="snippet",
            videoId=video_id,
            maxResults=100,
            textFormat="plainText"
        )
        resp = req.execute()
        def push_items(r):
            for item in r.get('items', []):
                sn = item['snippet']['topLevelComment']['snippet']
                comments.append({
                    "id": item['id'],
                    "author": sn.get('authorDisplayName', ''),
                    "author_channel_id": sn.get('authorChannelId', {}).get('value', ''),
                    "text": sn.get('textDisplay', ''),
                    "likes": sn.get('likeCount', 0),
                    "published_at": sn.get('publishedAt'),
                    "updated_at": sn.get('updatedAt', sn.get('publishedAt'))
                })
        push_items(resp)

        while resp.get('nextPageToken') and len(comments) < max_results:
            resp = self.youtube.commentThreads().list(
                part="snippet",
                videoId=video_id,
                pageToken=resp['nextPageToken'],
                maxResults=100,
                textFormat="plainText"
            ).execute()
            push_items(resp)
            if len(comments) >= max_results:
                break
        return comments[:max_results]
