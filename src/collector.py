"""
플랫폼별 YouTube 데이터 수집기.

각 플랫폼의 alias 검색어로 영상을 모으고, 중복 제거 후 상세정보와
댓글을 붙여 하나의 표준 레코드 리스트로 반환합니다.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from config import COLLECTION, PLATFORMS
from src.youtube_client import YouTubeClient


def _published_after_iso(days: int | None) -> str | None:
    if not days:
        return None
    dt = datetime.now(timezone.utc) - timedelta(days=days)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def collect_platform(client: YouTubeClient, platform: str) -> list[dict[str, Any]]:
    """단일 플랫폼에 대한 영상 레코드 수집."""
    cfg = PLATFORMS[platform]
    published_after = _published_after_iso(COLLECTION["published_after_days"])

    # 1) alias 별 검색 → video_id 기준 중복 제거
    by_id: dict[str, dict[str, Any]] = {}
    for alias in cfg["aliases"]:
        found = client.search_videos(
            alias,
            max_results=COLLECTION["max_videos_per_alias"],
            region_code=COLLECTION["region_code"],
            relevance_language=COLLECTION["relevance_language"],
            order=COLLECTION["order"],
            published_after=published_after,
        )
        for v in found:
            by_id.setdefault(v["video_id"], {**v, "matched_alias": alias})

    video_ids = list(by_id.keys())
    if not video_ids:
        return []

    # 2) 상세정보(통계/태그) 일괄 조회
    details = client.get_video_details(video_ids)

    # 3) 댓글 수집 (키워드 동시출현 분석용)
    records: list[dict[str, Any]] = []
    for vid, base in by_id.items():
        d = details.get(vid, {})
        comments = client.get_comments(
            vid, max_results=COLLECTION["max_comments_per_video"]
        )
        records.append(
            {
                "platform": platform,
                "video_id": vid,
                "title": base["title"],
                "description": base["description"],
                "channel_id": base["channel_id"],
                "channel_title": base["channel_title"],
                "published_at": base["published_at"],
                "matched_alias": base["matched_alias"],
                "tags": d.get("tags", []),
                "view_count": d.get("view_count", 0),
                "like_count": d.get("like_count", 0),
                "comment_count": d.get("comment_count", 0),
                "topic_categories": d.get("topic_categories", []),
                "comments": comments,
            }
        )
    return records


def collect_all(client: YouTubeClient, platforms: list[str] | None = None):
    """모든(또는 지정) 플랫폼에 대해 수집."""
    platforms = platforms or list(PLATFORMS.keys())
    all_records: list[dict[str, Any]] = []
    for p in platforms:
        recs = collect_platform(client, p)
        print(f"  · {p}: {len(recs)}개 영상 수집")
        all_records.extend(recs)
    return all_records
