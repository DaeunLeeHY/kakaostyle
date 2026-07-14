"""
수집 데이터 분석.

조사항목 1) 영상 주제 분류        → classify_topics()
조사항목 2) 함께 언급된 키워드    → keyword_cooccurrence()
부가) 영상별 텍스트 결합 유틸
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Any

from config import KEYWORD_LEXICON, TOPIC_RULES


def _video_text(rec: dict[str, Any], *, include_comments: bool = False) -> str:
    """영상 1건의 분석 대상 텍스트(제목+설명+태그[+댓글])를 소문자로 결합."""
    parts = [rec.get("title", ""), rec.get("description", "")]
    parts.extend(rec.get("tags", []))
    if include_comments:
        parts.extend(rec.get("comments", []))
    return " ".join(parts).lower()


# ---------------------------------------------------------------------------
# 조사항목 1: 영상 주제(토픽) 분류
# ---------------------------------------------------------------------------
def classify_topics(records: list[dict[str, Any]]) -> dict[str, Counter]:
    """플랫폼별 토픽 출현 빈도를 반환. {platform: Counter({topic: n})}"""
    result: dict[str, Counter] = defaultdict(Counter)
    for rec in records:
        text = _video_text(rec)
        matched = []
        for topic, kws in TOPIC_RULES.items():
            if any(kw.lower() in text for kw in kws):
                matched.append(topic)
        if not matched:
            matched = ["기타/미분류"]
        for topic in matched:
            result[rec["platform"]][topic] += 1
    return dict(result)


def label_records_with_topics(records: list[dict[str, Any]]) -> None:
    """각 레코드에 topics 필드를 in-place 추가 (CSV 출력용)."""
    for rec in records:
        text = _video_text(rec)
        topics = [
            topic
            for topic, kws in TOPIC_RULES.items()
            if any(kw.lower() in text for kw in kws)
        ]
        rec["topics"] = topics or ["기타/미분류"]


# ---------------------------------------------------------------------------
# 조사항목 2: 플랫폼과 함께 언급된 키워드 (동시출현)
# ---------------------------------------------------------------------------
def keyword_cooccurrence(
    records: list[dict[str, Any]], *, include_comments: bool = True
) -> dict[str, Counter]:
    """
    플랫폼별로, 사전에 정의된 마케팅 키워드가 몇 개의 영상에서
    함께 언급됐는지 카운트. (영상 단위 document frequency)
    {platform: Counter({keyword_category: video_count})}
    """
    result: dict[str, Counter] = defaultdict(Counter)
    for rec in records:
        text = _video_text(rec, include_comments=include_comments)
        for category, synonyms in KEYWORD_LEXICON.items():
            if any(s.lower() in text for s in synonyms):
                result[rec["platform"]][category] += 1
    return dict(result)


# ---------------------------------------------------------------------------
# 부가: 자유 키워드(비사전) 빈도 - 신규 키워드 발굴용
# ---------------------------------------------------------------------------
_STOPWORDS = {
    "그리고", "하는", "합니다", "있는", "있어요", "너무", "정말", "진짜",
    "이거", "그냥", "저는", "제가", "근데", "해서", "에서", "하고", "the",
    "and", "for", "you", "this", "그래서", "이번", "오늘", "영상", "구독",
    "좋아요", "댓글", "채널", "영상을", "링크", "https",
}


def discover_keywords(
    records: list[dict[str, Any]], *, top_n: int = 20
) -> dict[str, list[tuple[str, int]]]:
    """플랫폼별 상위 명사성 토큰 빈도 (사전에 없는 신규 키워드 탐색용)."""
    result: dict[str, list[tuple[str, int]]] = {}
    grouped: dict[str, Counter] = defaultdict(Counter)
    token_re = re.compile(r"[가-힣a-zA-Z]{2,}")
    for rec in records:
        text = _video_text(rec, include_comments=True)
        for tok in token_re.findall(text):
            t = tok.lower()
            if t in _STOPWORDS or len(t) < 2:
                continue
            grouped[rec["platform"]][t] += 1
    for platform, counter in grouped.items():
        result[platform] = counter.most_common(top_n)
    return result
