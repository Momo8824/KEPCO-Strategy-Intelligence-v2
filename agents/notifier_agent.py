"""
notifier_agent.py — Slack + 카카오워크 알림 발송 에이전트
KEPCO E&C 전략 인텔리전스 시스템 v2.0

분석 완료된 Article 중 중요도 'High' 기사를 Slack Block Kit과
카카오워크 Incoming Webhook으로 동시 발송합니다.
"""

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import settings

import httpx

from scv.rss_collector import Article

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Slack 발송 (Block Kit)
# ──────────────────────────────────────────────

class SlackNotifier:
    """Slack Incoming Webhook 기반 알림 발송"""

    IMPORTANCE_EMOJI = {"High": "🔴", "Medium": "🟡", "Low": "🔵"}

    def __init__(self):
        self.webhook_url = settings.slack_webhook_url or ""
        if not settings.slack_enabled:
            logger.warning("SLACK_WEBHOOK_URL이 설정되지 않았습니다.")

    def _build_article_block(self, article: Article, index: int) -> list[dict]:
        """단일 기사를 Slack Block Kit 섹션으로 변환"""
        emoji = self.IMPORTANCE_EMOJI.get(article.importance, "⚪")
        published = (
            article.published_at.strftime("%Y-%m-%d")
            if article.published_at
            else "날짜 미상"
        )

        return [
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"{emoji} *[{index}] {article.title}*\n"
                        f"출처: `{article.source_name}` | {published}"
                    ),
                },
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*📈 기회*\n{article.opportunity or '—'}",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*⚠️ 위협*\n{article.threat or '—'}",
                    },
                ],
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*🎯 Action*: {article.action_point or '—'}",
                },
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "원문 보기"},
                    "url": article.url,
                    "action_id": f"read_more_{index}",
                },
            },
        ]

    def _build_payload(self, articles: list[Article], date_str: str) -> dict:
        """전체 메시지 페이로드 구성"""
        header_blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"📋 KEPCO E&C 전략 브리핑 — {date_str}",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"오늘 주요 기사 *{len(articles)}건* (🔴 High 등급)을 보고드립니다."
                    ),
                },
            },
        ]

        article_blocks = []
        for i, article in enumerate(articles, 1):
            article_blocks.extend(self._build_article_block(article, i))

        footer_blocks = [
            {"type": "divider"},
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "🤖 KEPCO E&C 전략 인텔리전스 시스템 v2.0 | 경영전략기획운영팀",
                    }
                ],
            },
        ]

        return {"blocks": header_blocks + article_blocks + footer_blocks}

    def send(self, articles: list[Article]) -> bool:
        """High 등급 기사 목록을 Slack으로 발송"""
        if not self.webhook_url:
            logger.warning("Slack Webhook URL 미설정 — 발송 건너뜀")
            return False
        if not articles:
            logger.info("발송할 Slack 기사 없음")
            return True

        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        payload = self._build_payload(articles, date_str)

        try:
            resp = httpx.post(self.webhook_url, json=payload, timeout=10)
            resp.raise_for_status()
            logger.info(f"Slack 발송 완료: {len(articles)}건")
            return True
        except Exception as e:
            logger.error(f"Slack 발송 실패: {e}")
            return False


# ──────────────────────────────────────────────
# 카카오워크 발송 (Incoming Webhook)
# ──────────────────────────────────────────────

class KakaoWorkNotifier:
    """카카오워크 Incoming Webhook 기반 알림 발송"""

    IMPORTANCE_EMOJI = {"High": "🔴", "Medium": "🟡", "Low": "🔵"}

    def __init__(self):
        self.webhook_url = settings.kakaowork_webhook_url or ""
        if not settings.kakaowork_enabled:
            logger.warning("KAKAOWORK_WEBHOOK_URL이 설정되지 않았습니다.")

    def _build_payload(self, articles: list[Article], date_str: str) -> dict:
        """카카오워크 메시지 페이로드 구성 (버튼 블록 포함)"""
        # 기사 텍스트 요약
        article_lines = []
        for i, a in enumerate(articles, 1):
            emoji = self.IMPORTANCE_EMOJI.get(a.importance, "⚪")
            line = f"{emoji} [{i}] {a.title}\n출처: {a.source_name} | Action: {a.action_point or '—'}"
            article_lines.append(line)

        body_text = f"📋 KEPCO E&C 전략 브리핑 ({date_str})\n\n" + "\n\n".join(article_lines)

        return {
            "text": body_text,
            "blocks": [
                {
                    "type": "header",
                    "text": f"KEPCO 전략 브리핑({date_str[5:]})",
                    "style": "blue",
                },
                {
                    "type": "text",
                    "text": f"오늘 주요 기사 {len(articles)}건 (🔴 High 등급)",
                    "inlines": [
                        {"type": "styled", "text": f"오늘 주요 기사 {len(articles)}건 (🔴 High 등급)", "bold": True}
                    ]
                },
                *[
                    {
                        "type": "text",
                        "text": (
                            f"🔴 [{i}] {a.title}\n"
                            f"출처: {a.source_name}\n"
                            f"📈 기회: {a.opportunity or '—'}\n"
                            f"⚠️ 위협: {a.threat or '—'}\n"
                            f"🎯 Action: {a.action_point or '—'}"
                        )
                    }
                    for i, a in enumerate(articles, 1)
                ],
                {
                    "type": "button",
                    "text": "Notion DB 바로가기",
                    "style": "default",
                    "action_type": "open_system_browser",
                    "value": f"https://notion.so/{settings.notion_database_id or ''}",
                },
            ],
        }

    def send(self, articles: list[Article]) -> bool:
        """High 등급 기사 목록을 카카오워크로 발송"""
        if not self.webhook_url:
            logger.warning("카카오워크 Webhook URL 미설정 — 발송 건너뜀")
            return False
        if not articles:
            logger.info("발송할 카카오워크 기사 없음")
            return True

        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        payload = self._build_payload(articles, date_str)

        try:
            resp = httpx.post(self.webhook_url, json=payload, timeout=10)
            resp.raise_for_status()
            logger.info(f"카카오워크 발송 완료: {len(articles)}건")
            return True
        except Exception as e:
            logger.error(f"카카오워크 발송 실패: {e}")
            return False


# ──────────────────────────────────────────────
# 통합 알림 에이전트
# ──────────────────────────────────────────────

class NotifierAgent:
    """
    High 중요도 기사를 Slack + 카카오워크로 동시 발송하는 에이전트.

    Usage:
        agent = NotifierAgent()
        agent.run(analyzed_articles)
    """

    def __init__(self):
        self.slack = SlackNotifier()
        self.kakaowork = KakaoWorkNotifier()

    def run(self, articles: list[Article]) -> dict:
        """
        중요도 'High' 기사만 필터링 후 양 채널 동시 발송.
        Returns: {"slack": bool, "kakaowork": bool}
        """
        high_articles = [a for a in articles if a.importance == "High"]
        logger.info(f"알림 대상: {len(high_articles)}건 (High 등급)")

        slack_ok = self.slack.send(high_articles)
        kakao_ok = self.kakaowork.send(high_articles)

        return {"slack": slack_ok, "kakaowork": kakao_ok}
