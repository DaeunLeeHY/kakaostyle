# 카카오스타일(지그재그) 그로스해킹 — YouTube 브랜드/소비자 인식 분석

패션 커머스 플랫폼(**지그재그·에이블리·29CM·무신사·W컨셉**)에 대한 YouTube
콘텐츠를 수집·분석해, 자사/경쟁사의 **브랜드 이미지와 소비자 인식**을
데이터로 파악하기 위한 파이프라인입니다.

## 조사 항목과 대응 방식

| # | 조사 항목 | 이 파이프라인의 대응 | 산출물 |
|---|-----------|----------------------|--------|
| 1 | 각 플랫폼을 주제로 한 **영상의 주제** | 제목·설명·태그를 규칙 기반으로 8개 토픽(하울/리뷰/코디/세일정보/비교 등)으로 멀티라벨 분류 | `topics_by_platform.csv`, `topics.png` |
| 2 | 플랫폼과 **함께 언급된 키워드** (가성비·고급미·하객룩 등) | 마케팅 키워드 사전 기반 동시출현 빈도 + 사전 외 신규 키워드 발굴 | `keywords_by_platform.csv`, `keywords.png` |
| 3 | 플랫폼별 **주 연령/성별 통계** | (자사)YouTube Analytics API 실측 + (경쟁사)콘텐츠 타깃 시그널 추정 | `demographics.csv` |

> **조사항목 3 관련 핵심 한계 (반드시 읽어주세요)**
> YouTube **Data** API로는 경쟁사 영상을 *본 시청자*의 연령·성별을 가져올 수
> 없습니다. 실제 시청자 인구통계는 YouTube **Analytics** API로만, 그것도
> **본인이 소유·인증한 채널**에 한해 제공됩니다.
> - **자사(지그재그 공식 채널)**: `src/demographics.py`의 `own_channel_demographics()`
>   로 실제 시청자 연령/성별 실측 가능 (OAuth 필요).
> - **경쟁사**: 실측 불가 → 본 도구는 콘텐츠 텍스트에 드러난 *타깃* 연령/성별
>   시그널을 **근사치**로 제공합니다. 정밀 인구통계가 필요하면 소셜리스닝
>   (썸트렌드/Nox 등)이나 설문 등 별도 소스를 병행하세요.

## 빠른 시작

```bash
# 1) 의존성 설치
pip install -r requirements.txt

# 2) API 키 설정
cp .env.example .env
#   .env 파일을 열어 YOUTUBE_API_KEY 입력
#   (Google Cloud Console → API/서비스 → YouTube Data API v3 사용 설정 → API 키 발급)

# 3) 실행
python run_analysis.py                      # 전체 플랫폼
python run_analysis.py --platforms 지그재그 무신사   # 일부만

# API 키 없이 구조/결과 형태만 확인 (가상 데이터)
python run_analysis.py --mock
```

산출물은 `output/` 폴더에 CSV / PNG / `REPORT.md`(요약) / `raw_records.json`으로 저장됩니다.

## 프로젝트 구조

```
kakaostyle/
├── config.py              # ★ 플랫폼·검색어·키워드 사전·토픽 규칙 (여기만 수정)
├── run_analysis.py        # 메인 실행 스크립트
├── src/
│   ├── youtube_client.py  # YouTube Data API v3 래퍼(검색/상세/댓글 + 재시도)
│   ├── collector.py       # 플랫폼별 수집·중복제거 오케스트레이션
│   ├── analyzer.py        # 토픽 분류 / 키워드 동시출현 / 신규 키워드 발굴
│   ├── demographics.py    # 인구통계(자사 실측 + 경쟁사 타깃 추정)
│   ├── reporter.py        # CSV / 차트 / 마크다운 리포트 출력
│   └── mock_data.py       # --mock 용 가상 데이터
├── requirements.txt
└── .env.example
```

## 커스터마이징

`config.py` 한 파일로 대부분 조정됩니다.

- **`PLATFORMS`** — 조사 대상과 검색어 변형(alias). 오타/영문/줄임말을 추가하면 커버리지가 넓어집니다.
- **`KEYWORD_LEXICON`** — 조사항목 2의 마케팅 키워드 사전. 가설 키워드를 카테고리로 추가하세요.
- **`TOPIC_RULES`** — 조사항목 1의 토픽 정의.
- **`COLLECTION`** — 수집량, 기간(`published_after_days`), 정렬 기준, 지역 코드.

## API 쿼터 유의사항

YouTube Data API 기본 일일 쿼터는 **10,000 유닛**입니다.
- `search.list` = **100 유닛/호출** (가장 비쌈)
- `videos.list` / `commentThreads.list` = 1 유닛/호출

플랫폼 5개 × alias 4개 ≈ 20회 검색 = 약 2,000 유닛. 여기에 영상 상세·댓글이
추가됩니다. 하루 쿼터로 충분하지만, 수집량을 크게 늘리면 초과할 수 있으니
`config.py`의 `max_videos_per_alias`·`max_comments_per_video`로 조절하세요.

## 분석 방법론 요약

1. **수집** — 플랫폼별 alias 검색 → `video_id` 기준 중복 제거 → 상세(통계/태그) + 상위 댓글 부착.
2. **토픽 분류(항목1)** — 제목·설명·태그 텍스트에 대한 규칙 기반 멀티라벨링. 한 영상이 '하울+리뷰+코디'처럼 여러 주제를 가질 수 있음.
3. **키워드 동시출현(항목2)** — 영상 단위 document frequency. "몇 개의 영상에서 그 키워드가 플랫폼과 함께 등장했나"를 셈. 댓글까지 포함해 소비자 언어를 반영.
4. **인구통계(항목3)** — 자사는 Analytics API 실측, 경쟁사는 콘텐츠 타깃 시그널 추정(한계 명시).
5. **리포트** — 플랫폼 간 비교가 쉽도록 매트릭스 CSV와 차트로 출력.

## 확장 아이디어

- **감성 분석**: 댓글 텍스트에 긍/부정 분류를 붙여 '가성비=긍정 / 배송=부정'처럼 인식의 방향까지 파악.
- **형태소 분석**: `konlpy` 등으로 명사 추출 정밀도를 높여 신규 키워드 발굴 품질 개선.
- **시계열**: `published_after_days`를 분기별로 돌려 인식 변화 추적.
