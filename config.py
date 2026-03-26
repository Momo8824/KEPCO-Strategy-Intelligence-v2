"""
config.py — 환경변수 설정 관리 (pydantic-settings 2.x / pydantic v2)
KEPCO E&C 전략 인텔리전스 시스템 v2.0

.env 파일을 자동으로 로드하여 타입 검증된 설정 객체를 제공합니다.

Usage:
    from config import settings

    print(settings.openai_api_key)
    print(settings.notion_enabled)
"""

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    프로젝트 전체 환경변수를 타입-안전하게 관리하는 설정 클래스.
    .env 파일 또는 OS 환경변수에서 자동 로드됩니다.
    """

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ── OpenAI ───────────────────────────
    openai_api_key: str = Field(
        ...,
        description="OpenAI API 키 (필수)",
    )
    openai_model: str = Field(
        default="gpt-4o",
        description="사용할 OpenAI 모델명",
    )

    # ── Notion ──────────────────────────────────
    notion_api_key: Optional[str] = Field(default=None)
    notion_database_id: Optional[str] = Field(default=None)

    # ── Slack ───────────────────────────────────
    slack_webhook_url: Optional[str] = Field(default=None)

    # ── 카카오워크 ───────────────────────────────
    kakaowork_webhook_url: Optional[str] = Field(default=None)

    # ── 시스템 설정 ─────────────────────────────
    log_level: str = Field(default="INFO")
    schedule_hour: int = Field(default=7, ge=0, le=23)
    schedule_minute: int = Field(default=0, ge=0, le=59)
    max_articles_per_run: int = Field(default=30, ge=1)
    high_importance_only_notify: bool = Field(default=True)

    # ── 검증 (pydantic v2) ───────────────────────
    @field_validator("log_level", mode="before")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in allowed:
            raise ValueError(f"log_level은 {allowed} 중 하나여야 합니다.")
        return upper

    @field_validator("openai_api_key", mode="before")
    @classmethod
    def validate_openai_key(cls, v: str) -> str:
        placeholder = "여기에_OpenAI_API_키_입력"
        if not v or v.strip() in ("", placeholder):
            raise ValueError(
                "OPENAI_API_KEY가 설정되지 않았습니다. "
                f".env 파일의 '{placeholder}' 부분을 실제 API 키로 교체하세요."
            )
        return v.strip()

    # ── 편의 프로퍼티 ────────────────────────────
    @property
    def notion_enabled(self) -> bool:
        return bool(self.notion_api_key and self.notion_database_id)

    @property
    def slack_enabled(self) -> bool:
        return bool(self.slack_webhook_url)

    @property
    def kakaowork_enabled(self) -> bool:
        return bool(self.kakaowork_webhook_url)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Settings 싱글턴 반환 (캐시 적용)"""
    return Settings()


# 모듈 레벨 편의 객체
settings = get_settings()


# ──────────────────────────────────────────────
# 단독 실행 — 설정 로드 확인
# ──────────────────────────────────────────────
if __name__ == "__main__":
    s = get_settings()
    print("✅ 설정 로드 성공")
    print(f"  OpenAI 모델  : {s.openai_model}")
    print(f"  API 키 앞 8자: {s.openai_api_key[:8]}***")
    print(f"  Notion 연동  : {'활성' if s.notion_enabled else '비활성 (키 미설정)'}")
    print(f"  Slack 연동   : {'활성' if s.slack_enabled else '비활성 (URL 미설정)'}")
    print(f"  카카오워크   : {'활성' if s.kakaowork_enabled else '비활성 (URL 미설정)'}")
    print(f"  실행 시각    : 매일 {s.schedule_hour:02d}:{s.schedule_minute:02d} KST")
    print(f"  로그 레벨    : {s.log_level}")
