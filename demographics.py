"""
조사항목 3: 플랫폼별 주 연령/성별 통계.

⚠️ 중요한 API 한계 (반드시 이해하고 사용할 것)
────────────────────────────────────────────────────────────
YouTube "Data" API v3 로는 특정 영상/채널을 "본 시청자"의 연령·성별을
가져올 수 없습니다. 시청자 인구통계(viewerPercentage by ageGroup/gender)는
YouTube "Analytics" API 로만 제공되며, 이는 **본인이 소유·인증한 채널**에
한해서만 조회됩니다. (OAuth 필요)

따라서 경쟁사(에이블리/29CM/무신사/W컨셉)의 "실제 시청자 인구통계"는
공개 API로 취득 불가능합니다.

이 모듈은 두 가지를 제공합니다.
  1) own_channel_demographics(): 자사(지그재그) 채널 실제 인구통계
     - YouTube Analytics API + OAuth. 소유 채널만 가능.
  2) proxy_audience_signal(): 경쟁사 포함, 콘텐츠 텍스트에 드러난
     '타깃 연령/성별 시그널'을 추정하는 대체 지표.
     - 실제 시청자 통계가 아니라 '콘텐츠가 겨냥한 타깃'의 근사치입니다.
     - 마케팅 인사이트용 참고치로만 사용하고, 정밀 인구통계가 필요하면
       설문/소셜리스닝(예: Nox, 썸트렌드) 등 별도 소스를 권장합니다.
────────────────────────────────────────────────────────────
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Any

# 콘텐츠 텍스트에서 연령 타깃 시그널을 잡는 규칙
_AGE_SIGNALS = {
    "10대": [r"10대", r"고등학생", r"중학생", r"청소년", r"교복"],
    "20대": [r"20대", r"대학생", r"이십대", r"캠퍼스", r"새내기"],
    "30대": [r"30대", r"직장인", r"삼십대", r"오피스룩"],
    "40대+": [r"40대", r"50대", r"중년", r"엄마룩"],
}

# 성별 타깃 시그널
_GENDER_SIGNALS = {
    "여성": [r"여성", r"여자", r"원피스", r"블라우스", r"하객룩", r"여친룩", r"우먼"],
    "남성": [r"남성", r"남자", r"맨즈", r"남친룩", r"멘즈", r"men"],
}


def _text(rec: dict[str, Any]) -> str:
    parts = [rec.get("title", ""), rec.get("description", "")]
    parts.extend(rec.get("tags", []))
    parts.extend(rec.get("comments", []))
    return " ".join(parts).lower()


def proxy_audience_signal(records: list[dict[str, Any]]):
    """
    플랫폼별 '콘텐츠 타깃 연령/성별 시그널' 추정.
    반환: {platform: {"age": {구간: 비율}, "gender": {성별: 비율},
                      "n_videos": int, "n_signal_videos": int}}
    ※ 실제 시청자 통계가 아님. 콘텐츠 타깃의 근사치.
    """
    age_counter: dict[str, Counter] = defaultdict(Counter)
    gender_counter: dict[str, Counter] = defaultdict(Counter)
    n_videos: Counter = Counter()
    n_signal: Counter = Counter()

    age_pats = {k: [re.compile(p) for p in v] for k, v in _AGE_SIGNALS.items()}
    gender_pats = {k: [re.compile(p) for p in v] for k, v in _GENDER_SIGNALS.items()}

    for rec in records:
        p = rec["platform"]
        n_videos[p] += 1
        text = _text(rec)
        had_signal = False
        for bucket, pats in age_pats.items():
            if any(pat.search(text) for pat in pats):
                age_counter[p][bucket] += 1
                had_signal = True
        for gender, pats in gender_pats.items():
            if any(pat.search(text) for pat in pats):
                gender_counter[p][gender] += 1
                had_signal = True
        if had_signal:
            n_signal[p] += 1

    result: dict[str, Any] = {}
    for p in n_videos:
        age_total = sum(age_counter[p].values()) or 1
        gender_total = sum(gender_counter[p].values()) or 1
        result[p] = {
            "age": {k: round(v / age_total, 3) for k, v in age_counter[p].items()},
            "gender": {
                k: round(v / gender_total, 3) for k, v in gender_counter[p].items()
            },
            "n_videos": n_videos[p],
            "n_signal_videos": n_signal[p],
        }
    return result


def own_channel_demographics(
    channel_id: str,
    start_date: str,
    end_date: str,
    client_secrets_path: str = "client_secrets.json",
):
    """
    자사(소유) 채널의 실제 시청자 연령/성별 인구통계.
    YouTube Analytics API + OAuth 필요. 소유하지 않은 채널은 조회 불가.

    사전 준비:
      1) Google Cloud Console에서 OAuth 클라이언트(데스크톱) 생성 →
         client_secrets.json 다운로드
      2) pip install google-auth-oauthlib
      3) 아래 함수 실행 시 브라우저 인증 1회

    반환: {"age": {구간: 시청비율%}, "gender": {성별: 시청비율%}}
    """
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError as e:
        raise ImportError(
            "OAuth 인증에는 google-auth-oauthlib 가 필요합니다: "
            "pip install google-auth-oauthlib"
        ) from e

    scopes = ["https://www.googleapis.com/auth/yt-analytics.readonly"]
    flow = InstalledAppFlow.from_client_secrets_file(client_secrets_path, scopes)
    creds = flow.run_local_server(port=0)
    analytics = build("youtubeAnalytics", "v2", credentials=creds)

    def _query(dimension: str):
        resp = (
            analytics.reports()
            .query(
                ids=f"channel=={channel_id}",
                startDate=start_date,
                endDate=end_date,
                metrics="viewerPercentage",
                dimensions=dimension,
                sort=dimension,
            )
            .execute()
        )
        return {row[0]: row[-1] for row in resp.get("rows", [])}

    return {
        "age": _query("ageGroup"),
        "gender": _query("gender"),
    }
