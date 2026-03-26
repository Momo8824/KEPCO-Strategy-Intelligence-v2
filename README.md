# KEPCO E&C 전략 인텔리전스 시스템 v2.0

> 글로벌 에너지·원전 뉴스를 자동 수집·AI 분석하여 경영진용 전략 브리핑을 매일 자동 발행하는 멀티에이전트 파이프라인입니다.

## 📁 프로젝트 구조

```
KEPCO_E&C_Strategy_Intelligence/
├── staff/                        # 에이전트 시스템 프롬프트
│   ├── 01_ceo_director.md        # CEO Agent — 최종 검토·승인
│   ├── 02_analyst1_strategy.md   # Analyst 1 — 전략 필터링
│   ├── 03_analyst2_industry.md   # Analyst 2 — 심층 분석(SWOT)
│   └── 04_briefing_editor.md     # Editor — 카드뉴스 편집
│
├── scv/                          # 수집·파싱 스크립트
│   ├── sources.yaml              # 25개 소스 URL + 키워드 필터
│   ├── rss_collector.py          # RSS 수집 (feedparser + httpx)
│   ├── rss_parser.py             # 키워드 필터 + 텍스트 정제
│   └── __init__.py
│
├── pipeline.py                   # 5단계 파이프라인 오케스트레이터
├── scheduler.py                  # APScheduler (매일 07:00 KST)
├── requirements.txt
├── .env.example                  # 환경변수 템플릿
└── daily_output/                 # 일별 JSON 아카이브 (자동 생성)
```

## 🚀 빠른 시작

```bash
# 1. 의존성 설치
pip install -r requirements.txt

# 2. 환경변수 설정
cp .env.example .env
# .env 파일에 API 키 입력

# 3. 파이프라인 1회 수동 실행
python pipeline.py

# 4. 스케줄러 데몬 실행 (매일 자동화)
python scheduler.py
```

## ⚙️ 환경변수 (.env)

| 변수 | 설명 |
|---|---|
| `GEMINI_API_KEY` | Google Gemini API 키 |
| `NOTION_API_KEY` | Notion Integration 토큰 |
| `NOTION_DATABASE_ID` | Notion DB ID |
| `SLACK_WEBHOOK_URL` | Slack Incoming Webhook URL |
| `KAKAOWORK_WEBHOOK_URL` | 카카오워크 Webhook URL |

## 📊 파이프라인 단계

| 단계 | 모듈 | 상태 |
|---|---|---|
| 1. RSS 수집 | `scv/rss_collector.py` | ✅ 구현 완료 |
| 2. 필터·정제 | `scv/rss_parser.py` | ✅ 구현 완료 |
| 3. AI 분석 | `agents/analyzer_agent.py` | 🔄 구현 예정 |
| 4. Notion 저장 | `agents/notion_writer_agent.py` | 🔄 구현 예정 |
| 5. 알림 발송 | `agents/notifier_agent.py` | 🔄 구현 예정 |

## 🔒 보안 주의사항

- `.env` 파일은 절대 Git 커밋 금지 (`.gitignore`에 포함됨)
- API 키는 GitHub Secrets 또는 기업 Secret Manager에만 저장
- 현재 설계는 **인터넷망 전용** — 업무망 연동 시 별도 VPN/게이트웨이 검토 필요
