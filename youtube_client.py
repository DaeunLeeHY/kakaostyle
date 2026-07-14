"""
YouTube Data API v3 얇은 래퍼(wrapper).

- API 키가 없거나 google-api-python-client 가 설치되지 않은 환경에서도
  import 는 실패하지 않도록 지연(lazy) 로딩합니다.
- 검색/영상상세/댓글 3가지 엔드포인트만 사용합니다. (쿼터 절약)

YouTube Data API 쿼터 비용(참고):
  - search.list        : 100 유닛/호출
  - videos.list        : 1 유닛/호출
  - commentThreads.list: 1 유닛/호출
  기본 일일 쿼터 10,000 유닛 → search 는 하루 약 100회.
"""
from __future__ import annotations

import time
from typing import Any


class YouTubeClient:
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("YOUTUBE_API_KEY 가 비어 있습니다. .env 파일을 확인하세요.")
        try:
            from googleapiclient.discovery import build
        except ImportError as e:
            raise ImportError(
                "google-api-python-client 가 필요합니다. "
                "`pip install -r requirements.txt` 를 실행하세요."
            ) from e
        self._yt = build("youtube", "v3", developerKey=api_key, cache_discovery=False)

    # -- 검색 -----------------------------------------------------------------
    def search_videos(
        self,
        query: str,
        *,
        max_results: int = 50,
        region_code: str = "KR",
        relevance_language: str = "ko",
        order: str = "relevance",
        published_after: str | None = None,
    ) -> list[dict[str, Any]]:
        """검색어로 영상을 찾아 videoId 목록과 기본 스니펫을 반환."""
        items: list[dict[str, Any]] = []
        page_token = None
        while len(items) < max_results:
            req = self._yt.search().list(
                q=query,
                part="snippet",
                type="video",
                maxResults=min(50, max_results - len(items)),
                regionCode=region_code,
                relevanceLanguage=relevance_language,
                order=order,
                publishedAfter=published_after,
                pageToken=page_token,
            )
            resp = _execute(req)
            for it in resp.get("items", []):
                items.append(
                    {
                        "video_id": it["id"]["videoId"],
                        "title": it["snippet"]["title"],
                        "description": it["snippet"]["description"],
                        "channel_id": it["snippet"]["channelId"],
                        "channel_title": it["snippet"]["channelTitle"],
                        "published_at": it["snippet"]["publishedAt"],
                    }
                )
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        return items

    # -- 영상 상세(통계/태그) -------------------------------------------------
    def get_video_details(self, video_ids: list[str]) -> dict[str, dict[str, Any]]:
        """videoId 목록의 통계/태그/카테고리를 조회. {video_id: {...}}"""
        out: dict[str, dict[str, Any]] = {}
        for chunk in _chunked(video_ids, 50):
            req = self._yt.videos().list(
                part="snippet,statistics,topicDetails",
                id=",".join(chunk),
            )
            resp = _execute(req)
            for it in resp.get("items", []):
                stats = it.get("statistics", {})
                out[it["id"]] = {
                    "tags": it["snippet"].get("tags", []),
                    "category_id": it["snippet"].get("categoryId"),
                    "view_count": int(stats.get("viewCount", 0)),
                    "like_count": int(stats.get("likeCount", 0)),
                    "comment_count": int(stats.get("commentCount", 0)),
                    "topic_categories": it.get("topicDetails", {}).get(
                        "topicCategories", []
                    ),
                }
        return out

    # -- 댓글 -----------------------------------------------------------------
    def get_comments(self, video_id: str, *, max_results: int = 50) -> list[str]:
        """영상의 상위 댓글 텍스트를 수집. 댓글이 막힌 영상은 빈 리스트."""
        comments: list[str] = []
        try:
            req = self._yt.commentThreads().list(
                part="snippet",
                videoId=video_id,
                maxResults=min(100, max_results),
                order="relevance",
                textFormat="plainText",
            )
            resp = _execute(req)
        except Exception:
            return comments  # 댓글 비활성화/삭제 영상
        for it in resp.get("items", []):
            top = it["snippet"]["topLevelComment"]["snippet"]
            comments.append(top.get("textDisplay", ""))
            if len(comments) >= max_results:
                break
        return comments


# ---------------------------------------------------------------------------
# 내부 유틸
# ---------------------------------------------------------------------------
def _execute(req, *, retries: int = 3):
    """일시적 오류(rate limit/5xx)에 대해 지수 백오프 재시도."""
    delay = 2
    for attempt in range(retries + 1):
        try:
            return req.execute()
        except Exception as e:
            msg = str(e)
            transient = any(c in msg for c in ("500", "503", "quota", "rateLimit"))
            if attempt < retries and transient:
                time.sleep(delay)
                delay *= 2
                continue
            raise


def _chunked(seq: list, n: int):
    for i in range(0, len(seq), n):
        yield seq[i : i + n]
