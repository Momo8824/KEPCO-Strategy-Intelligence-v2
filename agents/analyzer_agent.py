"""
analyzer_agent.py — AI 분석 에이전트 (OpenAI)
KEPCO E&C 전략 인텔리전스 시스템 v2.0

OpenAI SDK 기반으로
Analyst 1(선별) → Analyst 2(심층분석) 2단계 파이프라인을 실행합니다.
"""

import json
import logging
import sys
import time
from pathlib import Path

from openai import OpenAI

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import settings
from scv.rss_collector import Article

logger = logging.getLogger(__name__)

STAFF_DIR = Path(__file__).parent.parent / "staff"


def _load_prompt(filename: str) -> str:
    return (STAFF_DIR / filename).read_text(encoding="utf-8")


def _get_client() -> OpenAI:
    return OpenAI(api_key=settings.openai_api_key)


class AnalyzerAgent:
    """
    OpenAI SDK를 사용하여 기사를 선별하고 심층 분석합니다.

    Usage:
        agent = AnalyzerAgent()
        analyzed = agent.run(filtered_articles)
    """

    RETRY_COUNT = 3
    RETRY_DELAY = 5

    def __init__(self):
        self.client = _get_client()
        self.analyst1_prompt = _load_prompt("02_analyst1_strategy.md")
        self.analyst2_prompt = _load_prompt("03_analyst2_industry.md")

    def _call_openai(self, system_prompt: str, user_content: str) -> str:
        """OpenAI API 호출 (재시도 포함)"""
        for attempt in range(1, self.RETRY_COUNT + 1):
            try:
                response = self.client.chat.completions.create(
                    model=settings.openai_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content}
                    ],
                    temperature=0.3
                )
                return response.choices[0].message.content
            except Exception as e:
                logger.warning(f"OpenAI 호출 실패 [{attempt}/{self.RETRY_COUNT}]: {e}")
                if attempt < self.RETRY_COUNT:
                    time.sleep(self.RETRY_DELAY * attempt)
        raise RuntimeError("OpenAI API 호출 최대 재시도 초과")

    def _step1_filter(self, articles: list[Article]) -> list[Article]:
        """Analyst 1: 상위 5건 선별 + 중요도 평가"""
        if not articles:
            return []

        article_list_text = "\n".join(
            f"{i+1}. [{a.source_name}] {a.title}\n   URL: {a.url}\n   요약: {a.summary[:200]}"
            for i, a in enumerate(articles)
        )
        user_content = (
            f"아래 {len(articles)}건의 기사 중 KEPCO E&C 관점에서 오늘 가장 중요한 5건을 선별하세요.\n"
            f"각 기사에 중요도(High/Medium/Low)를 명시하고 URL을 반드시 포함하세요.\n\n"
            f"기사 목록:\n{article_list_text}"
        )

        logger.info("Analyst 1: 핵심 기사 선별 중...")
        response_text = self._call_openai(self.analyst1_prompt, user_content)
        logger.debug(f"Analyst 1 응답:\n{response_text[:500]}")

        url_to_article = {a.url: a for a in articles}
        selected: list[Article] = []

        for line in response_text.splitlines():
            for url, article in url_to_article.items():
                if url in line and article not in selected:
                    article.importance = (
                        "High" if "high" in line.lower()
                        else "Medium" if "medium" in line.lower()
                        else "Low"
                    )
                    selected.append(article)
                    if len(selected) >= 5:
                        break
            if len(selected) >= 5:
                break

        if not selected:
            logger.warning("URL 매칭 실패 — 상위 5건 폴백 사용")
            selected = articles[:5]
            for a in selected:
                a.importance = "High"

        logger.info(f"Analyst 1 선별: {len(selected)}건")
        return selected

    def _step2_analyze(self, article: Article) -> Article:
        """Analyst 2: 단일 기사 기회·위협·Action 분석 (JSON 응답)"""
        user_content = (
            f"기사 제목: {article.title}\n"
            f"출처: {article.source_name}\n"
            f"URL: {article.url}\n"
            f"원문 요약: {article.summary}\n\n"
            f"다음을 JSON 형식으로만 작성하세요 (다른 텍스트 금지):\n"
            f'{{"summary": "3문장 이내 한국어 요약", '
            f'"opportunity": "KEPCO E&C 기회 요인 1~2문장", '
            f'"threat": "KEPCO E&C 위협 요인 1~2문장", '
            f'"action_point": "구체적 Action Point 1가지 (담당부서+행동+기한)"}}'
        )

        logger.info(f"Analyst 2: 분석 중 — {article.title[:50]}...")
        response_text = self._call_openai(self.analyst2_prompt, user_content)

        try:
            cleaned = response_text.strip().replace("```json", "").replace("```", "").strip()
            data = json.loads(cleaned)
            article.summary = data.get("summary", article.summary)
            article.opportunity = data.get("opportunity", "")
            article.threat = data.get("threat", "")
            article.action_point = data.get("action_point", "")
        except json.JSONDecodeError:
            logger.warning(f"JSON 파싱 실패 — 원문 저장: {article.title[:40]}")
            article.summary = response_text[:400]

        return article

    def run(self, articles: list[Article]) -> list[Article]:
        """전체 분석 실행: 선별 → 심층분석"""
        if not articles:
            logger.warning("분석할 기사가 없습니다.")
            return []

        selected = self._step1_filter(articles)

        analyzed: list[Article] = []
        for article in selected:
            try:
                analyzed.append(self._step2_analyze(article))
                time.sleep(1)
            except Exception as e:
                logger.error(f"분석 오류 ({article.title[:40]}): {e}")
                analyzed.append(article)

        logger.info(f"AI 분석 완료: {len(analyzed)}건")
        return analyzed
