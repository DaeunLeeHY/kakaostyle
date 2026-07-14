#!/usr/bin/env python3
"""
카카오스타일(지그재그) YouTube 브랜드/소비자 인식 분석 - 메인 실행 스크립트

사용법:
  # 실제 수집 (YOUTUBE_API_KEY 필요)
  python run_analysis.py

  # 특정 플랫폼만
  python run_analysis.py --platforms 지그재그 무신사

  # API 키 없이 파이프라인 시연 (가상 데이터)
  python run_analysis.py --mock

결과물은 output/ 폴더에 CSV / PNG / 리포트(md) / raw(json) 로 저장됩니다.
"""
from __future__ import annotations

import argparse
import os
import sys

from config import OUTPUT_DIR, PLATFORMS
from src import analyzer, demographics, reporter


def _load_api_key() -> str:
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    return os.environ.get("YOUTUBE_API_KEY", "")


def main() -> int:
    parser = argparse.ArgumentParser(description="YouTube 플랫폼 브랜드 인식 분석")
    parser.add_argument(
        "--platforms", nargs="*", default=None,
        help="분석할 플랫폼 (기본: 전체). 예: --platforms 지그재그 무신사",
    )
    parser.add_argument(
        "--mock", action="store_true",
        help="API 키 없이 가상 데이터로 파이프라인 시연",
    )
    args = parser.parse_args()

    platforms = args.platforms or list(PLATFORMS.keys())
    unknown = [p for p in platforms if p not in PLATFORMS]
    if unknown:
        print(f"[오류] 알 수 없는 플랫폼: {unknown}", file=sys.stderr)
        print(f"       사용 가능: {list(PLATFORMS.keys())}", file=sys.stderr)
        return 1

    # 1) 데이터 수집 ---------------------------------------------------------
    if args.mock:
        print("▶ [MOCK] 가상 데이터로 파이프라인을 실행합니다.")
        from src.mock_data import build_mock_records
        records = [r for r in build_mock_records() if r["platform"] in platforms]
    else:
        api_key = _load_api_key()
        if not api_key:
            print("[오류] YOUTUBE_API_KEY 가 없습니다. .env 설정 또는 --mock 사용.",
                  file=sys.stderr)
            return 1
        from src.collector import collect_all
        from src.youtube_client import YouTubeClient
        print("▶ YouTube 데이터 수집 시작...")
        client = YouTubeClient(api_key)
        records = collect_all(client, platforms)

    if not records:
        print("[경고] 수집된 영상이 없습니다.", file=sys.stderr)
        return 1
    print(f"▶ 총 {len(records)}개 영상 분석 시작")

    # 2) 분석 ----------------------------------------------------------------
    analyzer.label_records_with_topics(records)
    topics = analyzer.classify_topics(records)                    # 조사항목 1
    keywords = analyzer.keyword_cooccurrence(records)             # 조사항목 2
    demo = demographics.proxy_audience_signal(records)            # 조사항목 3
    discovered = analyzer.discover_keywords(records)              # 부가

    # 3) 리포트 출력 ---------------------------------------------------------
    out = reporter.ensure_output_dir(OUTPUT_DIR)
    reporter.write_videos_csv(records, os.path.join(out, "videos.csv"))
    reporter.write_counter_matrix(
        topics, os.path.join(out, "topics_by_platform.csv"), row_label="토픽")
    reporter.write_counter_matrix(
        keywords, os.path.join(out, "keywords_by_platform.csv"), row_label="키워드")
    reporter.write_demographics_csv(demo, os.path.join(out, "demographics.csv"))
    reporter.dump_raw_json(records, os.path.join(out, "raw_records.json"))
    reporter.write_markdown_summary(
        topics=topics, keywords=keywords, demographics=demo,
        discovered=discovered, n_records=len(records),
        path=os.path.join(out, "REPORT.md"),
    )
    plotted_t = reporter.try_plot_topics(topics, os.path.join(out, "topics.png"))
    plotted_k = reporter.try_plot_keywords(keywords, os.path.join(out, "keywords.png"))

    print("\n▶ 완료. 결과물:")
    print(f"   - {out}/REPORT.md            (요약 리포트)")
    print(f"   - {out}/videos.csv           (영상별 원천 데이터)")
    print(f"   - {out}/topics_by_platform.csv")
    print(f"   - {out}/keywords_by_platform.csv")
    print(f"   - {out}/demographics.csv")
    print(f"   - {out}/raw_records.json")
    if plotted_t:
        print(f"   - {out}/topics.png")
    if plotted_k:
        print(f"   - {out}/keywords.png")
    if not (plotted_t and plotted_k):
        print("   (matplotlib 미설치 시 차트는 생략됩니다)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
