"""
rss_collector.py — RSS 수집 에이전트
KEPCO E&C 전략 인텔리전스 시스템 v2.0

sources.yaml에 정의된 소스 목록에서 RSS/Atom 피드를 수집합니다.
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import feedparser
import httpx
import yaml

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# 데이터 클래스
# ──────────────────────────────────────────────

@dataclass
class Article:
    """수집된 기사 단위 데이터 클래스"""
    title: str
    url: str
    source_name: str
    category: str
    language: str
    published_at: Optional[datetime] = None
    summary: str = ""
    importance: str = "Low"  # High / Medium / Low (AI 분석 후 채워짐)
    opportunity: str = ""
    threat: str = ""
    action_point: str = ""
    collected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "url": self.url,
            "source_name": self.source_name,
            "category": self.category,
            "language": self.language,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "summary": self.summary,
            "importance": self.importance,
            "opportunity": self.opportunity,
            "threat": self.threat,
            "action_point": self.action_point,
            "collected_at": self.collected_at.isoformat(),
        }


# ──────────────────────────────────────────────
# RSS 수집기
# ──────────────────────────────────────────────

class RssCollector:
    """
    sources.yaml을 읽어 RSS 피드를 수집하는 메인 클래스.

    Usage:
        collector = RssCollector()
        articles = collector.collect_all()
    """

    SOURCES_YAML = Path(__file__).parent / "sources.yaml"

    def __init__(self, sources_path: Optional[Path] = None):
        self.sources_path = sources_path or self.SOURCES_YAML
        self.config = self._load_config()
        self.collection_cfg = self.config.get("collection", {})
        self.max_age_hours: int = self.collection_cfg.get("max_age_hours", 24)
        self.max_per_source: int = self.collection_cfg.get("max_articles_per_source", 20)
        self.timeout: int = self.collection_cfg.get("request_timeout_seconds", 10)
        self.retry_count: int = self.collection_cfg.get("retry_count", 3)
        self.user_agent: str = self.collection_cfg.get(
            "user_agent", "KEPCO-StrategyBot/2.0"
        )

    def _load_config(self) -> dict:
        with open(self.sources_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def _fetch_feed(self, url: str) -> Optional[feedparser.FeedParserDict]:
        """단일 RSS URL 피드 파싱 (재시도 포함)"""
        headers = {"User-Agent": self.user_agent}
        for attempt in range(1, self.retry_count + 1):
            try:
                response = httpx.get(url, headers=headers, timeout=self.timeout, follow_redirects=True)
                response.raise_for_status()
                feed = feedparser.parse(response.text)
                return feed
            except Exception as e:
                logger.warning(f"[시도 {attempt}/{self.retry_count}] 피드 수집 실패: {url} — {e}")
                if attempt < self.retry_count:
                    time.sleep(2 ** attempt)  # 지수 백오프
        return None

    def _parse_published(self, entry) -> Optional[datetime]:
        """RSS 엔트리의 발행일 파싱"""
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        if hasattr(entry, "updated_parsed") and entry.updated_parsed:
            return datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
        return None

    def _is_recent(self, published_at: Optional[datetime]) -> bool:
        """max_age_hours 이내의 기사인지 확인"""
        if published_at is None:
            return True  # 날짜 불명 → 일단 포함
        now = datetime.now(timezone.utc)
        age_hours = (now - published_at).total_seconds() / 3600
        return age_hours <= self.max_age_hours

    def collect_from_source(self, source: dict) -> list[Article]:
        """단일 소스에서 기사 수집"""
        if not source.get("enabled", True):
            return []

        name = source["name"]
        url = source["url"]
        category = source.get("category", "unknown")
        language = source.get("language", "en")

        logger.info(f"수집 중: {name} ({url})")
        feed = self._fetch_feed(url)
        if not feed:
            logger.error(f"수집 실패: {name}")
            return []

        articles = []
        for entry in feed.entries[: self.max_per_source]:
            published_at = self._parse_published(entry)
            if not self._is_recent(published_at):
                continue

            article = Article(
                title=entry.get("title", "제목 없음").strip(),
                url=entry.get("link", ""),
                source_name=name,
                category=category,
                language=language,
                published_at=published_at,
                summary=entry.get("summary", "")[:500],  # 요약 최대 500자
            )
            articles.append(article)

        logger.info(f"  → {len(articles)}건 수집 완료")
        return articles

    def collect_all(self) -> list[Article]:
        """
        모든 활성화된 소스에서 기사를 수집합니다.
        Returns: 수집된 Article 리스트
        """
        sources = self.config.get("sources", [])
        all_articles: list[Article] = []

        for source in sources:
            articles = self.collect_from_source(source)
            all_articles.extend(articles)
            time.sleep(0.5)  # 서버 부하 방지

        # URL 기준 중복 제거
        seen_urls: set[str] = set()
        unique_articles = []
        for article in all_articles:
            if article.url not in seen_urls:
                seen_urls.add(article.url)
                unique_articles.append(article)

        logger.info(f"총 수집: {len(all_articles)}건 → 중복 제거 후: {len(unique_articles)}건")
        return unique_articles


# ──────────────────────────────────────────────
# 단독 실행 (테스트용)
# ──────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    collector = RssCollector()
    articles = collector.collect_all()
    print(f"\n✅ 수집 완료: {len(articles)}건")
    for a in articles[:5]:
        print(f"  [{a.source_name}] {a.title[:60]} — {a.url}")
