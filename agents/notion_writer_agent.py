"""
notion_writer_agent.py — Notion DB 저장 에이전트
KEPCO E&C 전략 인텔리전스 시스템 v2.0

분석 완료된 Article을 Notion Database에 1건 = 1 Page로 저장합니다.
- Rate Limit: 초당 최대 3 req (토큰 버킷)
- Retry: 429/502 에러 시 지수 백오프 (최대 5회)
- 중복 방지: URL 기준 기존 저장 여부 사전 확인
"""

import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import settings
from datetime import datetime, timezone
from threading import Lock

from notion_client import Client
from notion_client.errors import APIResponseError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from scv.rss_collector import Article

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Rate Limiter (토큰 버킷, 초당 3 req)
# ──────────────────────────────────────────────

class RateLimiter:
    """초당 최대 max_rps 요청만 허용하는 토큰 버킷"""

    def __init__(self, max_rps: int = 3):
        self.max_rps = max_rps
        self.min_interval = 1.0 / max_rps
        self._last_call = 0.0
        self._lock = Lock()

    def acquire(self):
        with self._lock:
            now = time.monotonic()
            wait = self.min_interval - (now - self._last_call)
            if wait > 0:
                time.sleep(wait)
            self._last_call = time.monotonic()


_rate_limiter = RateLimiter(max_rps=3)


# ──────────────────────────────────────────────
# Notion 클라이언트 래퍼
# ──────────────────────────────────────────────

class NotionWriter:
    """
    Notion API 래퍼. Rate Limit + Retry 자동 적용.

    Notion DB 스키마 (Blueprint 5.1 기준):
      Title, Source, URL, PublishedDate, Importance,
      Summary, Opportunity, Threat, ActionPoint, ProcessedAt
    """

    IMPORTANCE_COLORS = {
        "High": "red",
        "Medium": "yellow",
        "Low": "blue",
    }

    def __init__(self):
        if not settings.notion_enabled:
            raise EnvironmentError(
                "NOTION_API_KEY 또는 NOTION_DATABASE_ID가 설정되지 않았습니다. "
                ".env 파일을 확인하세요."
            )
        self.database_id = settings.notion_database_id
        self.client = Client(auth=settings.notion_api_key)

    # ── 중복 확인 ──────────────────────────────

    def get_existing_urls(self) -> set[str]:
        """DB에 이미 저장된 URL 집합 반환 (중복 방지용)"""
        existing: set[str] = set()
        cursor = None
        while True:
            _rate_limiter.acquire()
            params = {
                "database_id": self.database_id,
                "page_size": 100,
                "filter": {"property": "URL", "url": {"is_not_empty": True}},
            }
            if cursor:
                params["start_cursor"] = cursor

            result = self.client.databases.query(**params)
            for page in result.get("results", []):
                props = page.get("properties", {})
                url_prop = props.get("URL", {})
                url_val = url_prop.get("url", "")
                if url_val:
                    existing.add(url_val)

            if not result.get("has_more"):
                break
            cursor = result.get("next_cursor")

        logger.info(f"기존 URL {len(existing)}건 로드 완료")
        return existing

    # ── 페이지 생성 ────────────────────────────

    @retry(
        retry=retry_if_exception_type(APIResponseError),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(5),
    )
    def _create_page(self, properties: dict) -> str:
        """Notion DB에 단일 페이지 생성 (Retry 데코레이터 적용)"""
        _rate_limiter.acquire()
        result = self.client.pages.create(
            parent={"database_id": self.database_id},
            properties=properties,
        )
        return result["id"]

    def create_briefing_page(self, article: Article) -> str | None:
        """
        Article 1건을 Notion DB 1 Page로 저장합니다.
        Returns: 생성된 Notion Page ID, 실패 시 None
        """
        published_str = (
            article.published_at.strftime("%Y-%m-%d")
            if article.published_at
            else datetime.now(timezone.utc).strftime("%Y-%m-%d")
        )
        processed_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")

        properties = {
            "Title": {
                "title": [{"type": "text", "text": {"content": article.title[:2000]}}]
            },
            "Source": {
                "select": {"name": article.source_name[:100]}
            },
            "URL": {
                "url": article.url
            },
            "PublishedDate": {
                "date": {"start": published_str}
            },
            "Importance": {
                "select": {
                    "name": article.importance,
                    "color": self.IMPORTANCE_COLORS.get(article.importance, "default"),
                }
            },
            "Summary": {
                "rich_text": [{"type": "text", "text": {"content": article.summary[:2000]}}]
            },
            "Opportunity": {
                "rich_text": [{"type": "text", "text": {"content": article.opportunity[:2000]}}]
            },
            "Threat": {
                "rich_text": [{"type": "text", "text": {"content": article.threat[:2000]}}]
            },
            "ActionPoint": {
                "rich_text": [{"type": "text", "text": {"content": article.action_point[:2000]}}]
            },
            "ProcessedAt": {
                "date": {"start": processed_str}
            },
        }

        try:
            page_id = self._create_page(properties)
            logger.info(f"Notion 저장 완료: {article.title[:50]} (ID: {page_id})")
            return page_id
        except Exception as e:
            logger.error(f"Notion 저장 실패: {article.title[:50]} — {e}")
            return None


# ──────────────────────────────────────────────
# Notion Writer 에이전트
# ──────────────────────────────────────────────

class NotionWriterAgent:
    """
    분석 완료된 Article 목록을 Notion DB에 저장하는 에이전트.

    Usage:
        agent = NotionWriterAgent()
        saved = agent.run(analyzed_articles)
    """

    def __init__(self):
        self.writer = NotionWriter()

    def run(self, articles: list[Article]) -> list[Article]:
        """
        중복 확인 후 신규 기사만 Notion에 저장합니다.
        Returns: 저장 성공한 Article 리스트
        """
        if not articles:
            return []

        existing_urls = self.writer.get_existing_urls()
        saved: list[Article] = []

        for article in articles:
            if article.url in existing_urls:
                logger.info(f"중복 — 스킵: {article.title[:50]}")
                continue

            page_id = self.writer.create_briefing_page(article)
            if page_id:
                saved.append(article)

        logger.info(f"Notion 저장 완료: {len(saved)}/{len(articles)}건")
        return saved
