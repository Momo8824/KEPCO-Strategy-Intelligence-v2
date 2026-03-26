"""
pipeline.py — 파이프라인 오케스트레이터 (Full)
KEPCO E&C 전략 인텔리전스 시스템 v2.0

실행 순서:
  1. RssCollector      → 원천 기사 수집
  2. RssParser         → 키워드 필터 + 텍스트 정제
  3. AnalyzerAgent     → Gemini AI 분석 (요약·중요도·기회·위협·Action)
  4. NotionWriterAgent → Notion DB 저장
  5. NotifierAgent     → Slack + 카카오워크 알림 발송
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# 패키지 경로 설정
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from scv.rss_collector import RssCollector
from scv.rss_parser import RssParser
from agents.analyzer_agent import AnalyzerAgent
from agents.notion_writer_agent import NotionWriterAgent
from agents.notifier_agent import NotifierAgent

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(ROOT / "pipeline.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("pipeline")

OUTPUT_DIR = ROOT / "daily_output"


def save_output(articles: list, date_str: str):
    """일자별 JSON 아카이브 저장"""
    out_dir = OUTPUT_DIR / date_str
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "briefing.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump([a.to_dict() for a in articles], f, ensure_ascii=False, indent=2)
    logger.info(f"아카이브 저장: {out_path}")


def run():
    start = datetime.now(timezone.utc)
    date_str = start.strftime("%Y-%m-%d")
    logger.info(f"━━━ KEPCO E&C 전략 브리핑 파이프라인 시작 ({date_str}) ━━━")

    # Step 1: RSS 수집
    logger.info("[1/5] RSS 수집 중...")
    raw_articles = RssCollector().collect_all()
    logger.info(f"  수집 완료: {len(raw_articles)}건")

    # Step 2: 키워드 필터 + 정제
    logger.info("[2/5] 파싱 및 필터링 중...")
    filtered_articles = RssParser().process(raw_articles)
    logger.info(f"  필터링 후: {len(filtered_articles)}건")

    if not filtered_articles:
        logger.warning("필터링 후 기사가 없습니다. 파이프라인 종료.")
        return []

    # Step 3: AI 분석 (Gemini)
    logger.info("[3/5] AI 분석 중...")
    analyzed_articles = AnalyzerAgent().run(filtered_articles)
    logger.info(f"  AI 분석 완료: {len(analyzed_articles)}건")

    # 아카이브 우선 저장 (Notion 등에서 실패하더라도 JSON은 남도록)
    if analyzed_articles:
        save_output(analyzed_articles, date_str)

    # Step 4: Notion 저장
    logger.info("[4/5] Notion DB 저장 중...")
    try:
        saved_articles = NotionWriterAgent().run(analyzed_articles)
        logger.info(f"  Notion 저장: {len(saved_articles)}건")
    except EnvironmentError as e:
        logger.warning(f"  Notion DB 저장 스킵 ({e})")
        saved_articles = analyzed_articles

    # Step 5: 알림 발송
    logger.info("[5/5] 알림 발송 중...")
    try:
        notify_result = NotifierAgent().run(analyzed_articles)
        logger.info(f"  알림 결과: Slack={notify_result['slack']}, 카카오워크={notify_result['kakaowork']}")
    except EnvironmentError as e:
        logger.warning(f"  알림 발송 스킵 ({e})")


    elapsed = (datetime.now(timezone.utc) - start).total_seconds()
    logger.info(
        f"━━━ 파이프라인 완료 ({elapsed:.1f}초) "
        f"| 수집 {len(raw_articles)}건 → 필터 {len(filtered_articles)}건 "
        f"→ 분석 {len(analyzed_articles)}건 → Notion {len(saved_articles)}건 ━━━"
    )
    return analyzed_articles


if __name__ == "__main__":
    run()
