"""
분석 결과를 CSV / 차트(PNG) / 마크다운 요약으로 출력.
"""
from __future__ import annotations

import csv
import json
import os
from collections import Counter
from typing import Any

from config import OUTPUT_DIR, PLATFORMS


def ensure_output_dir(path: str = OUTPUT_DIR) -> str:
    os.makedirs(path, exist_ok=True)
    return path


# ---------------------------------------------------------------------------
# 1) 원천 영상 레코드 CSV
# ---------------------------------------------------------------------------
def write_videos_csv(records: list[dict[str, Any]], path: str) -> None:
    fields = [
        "platform", "video_id", "title", "channel_title", "published_at",
        "view_count", "like_count", "comment_count", "topics", "matched_alias",
    ]
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for rec in records:
            row = dict(rec)
            row["topics"] = "|".join(rec.get("topics", []))
            w.writerow({k: row.get(k, "") for k in fields})


# ---------------------------------------------------------------------------
# 2) 집계 결과 CSV (토픽/키워드/인구통계)
# ---------------------------------------------------------------------------
def write_counter_matrix(
    data: dict[str, Counter], path: str, *, row_label: str = "항목"
) -> None:
    """{platform: Counter} → 행=항목, 열=플랫폼 매트릭스 CSV."""
    platforms = list(data.keys())
    all_keys: list[str] = []
    for c in data.values():
        for k in c:
            if k not in all_keys:
                all_keys.append(k)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow([row_label] + platforms)
        for key in all_keys:
            w.writerow([key] + [data[p].get(key, 0) for p in platforms])


def write_demographics_csv(demo: dict[str, Any], path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["플랫폼", "구분", "항목", "비율", "분석영상수", "시그널영상수"])
        for platform, d in demo.items():
            for age, ratio in d.get("age", {}).items():
                w.writerow([platform, "연령", age, ratio, d["n_videos"], d["n_signal_videos"]])
            for gender, ratio in d.get("gender", {}).items():
                w.writerow([platform, "성별", gender, ratio, d["n_videos"], d["n_signal_videos"]])


# ---------------------------------------------------------------------------
# 3) 차트 (matplotlib 있을 때만)
# ---------------------------------------------------------------------------
def try_plot_topics(topics: dict[str, Counter], path: str) -> bool:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return False
    _set_korean_font(plt)

    platforms = list(topics.keys())
    all_topics: list[str] = []
    for c in topics.values():
        for t in c:
            if t not in all_topics:
                all_topics.append(t)

    fig, ax = plt.subplots(figsize=(11, 6))
    bottom = [0] * len(platforms)
    for topic in all_topics:
        vals = [topics[p].get(topic, 0) for p in platforms]
        ax.bar(platforms, vals, bottom=bottom, label=topic)
        bottom = [b + v for b, v in zip(bottom, vals)]
    ax.set_title("플랫폼별 영상 주제(토픽) 분포")
    ax.set_ylabel("영상 수 (멀티라벨)")
    ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return True


def try_plot_keywords(keywords: dict[str, Counter], path: str) -> bool:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return False
    _set_korean_font(plt)

    platforms = list(keywords.keys())
    n = len(platforms)
    cols = 2
    rows = (n + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(13, 4 * rows))
    axes = axes.flatten() if hasattr(axes, "flatten") else [axes]
    for i, p in enumerate(platforms):
        top = keywords[p].most_common(8)
        color = PLATFORMS.get(p, {}).get("brand_color", "#888")
        labels = [k for k, _ in top][::-1]
        vals = [v for _, v in top][::-1]
        axes[i].barh(labels, vals, color=color)
        axes[i].set_title(f"{p} - 함께 언급된 키워드 TOP8")
    for j in range(n, len(axes)):
        axes[j].axis("off")
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return True


def _set_korean_font(plt) -> None:
    """설치된 한글 폰트를 찾아 지정 (없으면 경고만, 네모 깨짐 가능)."""
    import matplotlib.font_manager as fm
    candidates = ["NanumGothic", "Malgun Gothic", "AppleGothic", "Noto Sans CJK KR"]
    available = {f.name for f in fm.fontManager.ttflist}
    for c in candidates:
        if c in available:
            plt.rcParams["font.family"] = c
            break
    plt.rcParams["axes.unicode_minus"] = False


# ---------------------------------------------------------------------------
# 4) 마크다운 요약 리포트
# ---------------------------------------------------------------------------
def write_markdown_summary(
    *,
    topics: dict[str, Counter],
    keywords: dict[str, Counter],
    demographics: dict[str, Any],
    discovered: dict[str, list[tuple[str, int]]],
    n_records: int,
    path: str,
) -> None:
    lines: list[str] = []
    lines.append("# 카카오스타일(지그재그) YouTube 브랜드 인식 분석 리포트\n")
    lines.append(f"- 분석 영상 총계: **{n_records}건**")
    lines.append(f"- 대상 플랫폼: {', '.join(PLATFORMS.keys())}\n")

    lines.append("## 1. 플랫폼별 대표 영상 주제(토픽)\n")
    for p, c in topics.items():
        top = ", ".join(f"{t}({n})" for t, n in c.most_common(5))
        lines.append(f"- **{p}**: {top}")
    lines.append("")

    lines.append("## 2. 플랫폼별 함께 언급된 키워드 (동시출현 영상 수)\n")
    for p, c in keywords.items():
        top = ", ".join(f"{k}({n})" for k, n in c.most_common(6))
        lines.append(f"- **{p}**: {top}")
    lines.append("")

    lines.append("## 3. 플랫폼별 타깃 연령/성별 시그널 (추정)\n")
    lines.append("> ⚠️ 아래는 '콘텐츠 타깃'의 근사치입니다. 실제 시청자 인구통계가")
    lines.append("> 아니며(공개 API 미제공), 자사 채널은 YouTube Analytics API로 실측 가능합니다.\n")
    for p, d in demographics.items():
        age = ", ".join(f"{k} {v:.0%}" for k, v in d.get("age", {}).items()) or "시그널 없음"
        gender = ", ".join(f"{k} {v:.0%}" for k, v in d.get("gender", {}).items()) or "시그널 없음"
        lines.append(f"- **{p}** (시그널 영상 {d['n_signal_videos']}/{d['n_videos']})")
        lines.append(f"    - 연령: {age}")
        lines.append(f"    - 성별: {gender}")
    lines.append("")

    lines.append("## 4. 신규 키워드 발굴 (사전 외 상위 빈출어)\n")
    for p, kws in discovered.items():
        top = ", ".join(f"{k}({n})" for k, n in kws[:10])
        lines.append(f"- **{p}**: {top}")
    lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def dump_raw_json(records: list[dict[str, Any]], path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
