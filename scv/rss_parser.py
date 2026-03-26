"""
rss_parser.py — 키워드 필터 및 데이터 정제
KEPCO E&C 전략 인텔리전스 시스템 v2.0

수집된 Article 목록에서 전략적으로 관련 있는 기사를 필터링하고
데이터를 정제(텍스트 클리닝, HTML 제거)합니다.
"""

import html
import logging
import re
from typing import Optional

import yaml
from pathlib import Path

from .rss_collector import Article

logger = logging.getLogger(__name__)

SOURCES_YAML = Path(__file__).parent / "sources.yaml"


# ──────────────────────────────────────────────
# 텍스트 정제 유틸
# ──────────────────────────────────────────────

def clean_html(text: str) -> str:
    """HTML 태그 및 엔티티 제거"""
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)  # HTML 태그 제거
    text = re.sub(r"\s+", " ", text).strip()
    return text


def truncate(text: str, max_length: int = 300) -> str:
    """텍스트 최대 길이 제한"""
    if len(text) <= max_length:
        return text
    return text[:max_length].rsplit(" ", 1)[0] + "..."


# ──────────────────────────────────────────────
# 키워드 필터
# ──────────────────────────────────────────────

class KeywordFilter:
    """
    sources.yaml의 keywords 설정 기반 기사 필터링

    Usage:
        filter = KeywordFilter()
        passed = filter.filter(articles)
    """

    def __init__(self, sources_path: Optional[Path] = None):
        path = sources_path or SOURCES_YAML
        with open(path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        kw_config = config.get("keywords", {})
        self.must_include: list[str] = [k.lower() for k in kw_config.get("must_include", [])]
        self.exclude: list[str] = [k.lower() for k in kw_config.get("exclude", [])]

    def _matches(self, article: Article) -> bool:
        """기사가 필터 조건을 통과하는지 판단"""
        searchable = (article.title + " " + article.summary).lower()

        # 제외 키워드 확인
        for exc_kw in self.exclude:
            if exc_kw in searchable:
                return False

        # 필수 키워드 중 하나 이상 포함 확인
        for inc_kw in self.must_include:
            if inc_kw in searchable:
                return True

        return False

    def filter(self, articles: list[Article]) -> list[Article]:
        """키워드 필터를 통과한 기사 목록 반환"""
        passed = [a for a in articles if self._matches(a)]
        logger.info(f"키워드 필터: {len(articles)}건 → {len(passed)}건 통과")
        return passed


# ──────────────────────────────────────────────
# 데이터 정제기
# ──────────────────────────────────────────────

class ArticleCleaner:
    """
    수집된 기사의 텍스트 데이터를 정제합니다.
    - HTML 태그 제거
    - 불필요한 공백 정리
    - 제목/요약 길이 제한
    """

    MAX_TITLE_LENGTH = 150
    MAX_SUMMARY_LENGTH = 400

    def clean(self, article: Article) -> Article:
        """단일 Article 정제"""
        article.title = truncate(clean_html(article.title), self.MAX_TITLE_LENGTH)
        article.summary = truncate(clean_html(article.summary), self.MAX_SUMMARY_LENGTH)
        return article

    def clean_all(self, articles: list[Article]) -> list[Article]:
        """Article 목록 전체 정제"""
        return [self.clean(a) for a in articles]


# ──────────────────────────────────────────────
# 파서 파이프라인 (필터 + 정제 통합)
# ──────────────────────────────────────────────

class RssParser:
    """
    수집된 기사를 필터링하고 정제하는 통합 파서.

    Usage:
        parser = RssParser()
        refined_articles = parser.process(raw_articles)
    """

    def __init__(self):
        self.keyword_filter = KeywordFilter()
        self.cleaner = ArticleCleaner()

    def process(self, articles: list[Article]) -> list[Article]:
        """
        1) 키워드 필터링
        2) 텍스트 정제
        Returns: 정제된 Article 리스트
        """
        filtered = self.keyword_filter.filter(articles)
        cleaned = self.cleaner.clean_all(filtered)
        logger.info(f"파싱 완료: {len(cleaned)}건")
        return cleaned


# ──────────────────────────────────────────────
# 단독 실행 (테스트용)
# ──────────────────────────────────────────────

if __name__ == "__main__":
    import json
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    # 테스트용 더미 기사
    dummy = [
        Article(
            title="<b>Czech Nuclear Plant</b> SMR contract awarded",
            url="https://example.com/1",
            source_name="WNN",
            category="global_nuclear",
            language="en",
            summary="The Czech government awarded a contract for SMR deployment near Prague...",
        ),
        Article(
            title="광고: 에너지 박람회 참가 신청",
            url="https://example.com/2",
            source_name="에너지경제",
            category="domestic_media",
            language="ko",
            summary="광고 내용입니다.",
        ),
    ]

    parser = RssParser()
    result = parser.process(dummy)
    print(f"\n✅ 파싱 결과: {len(result)}건")
    for a in result:
        print(json.dumps(a.to_dict(), ensure_ascii=False, indent=2))
