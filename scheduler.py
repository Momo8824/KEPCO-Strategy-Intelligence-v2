"""
scheduler.py — APScheduler 기반 자동 실행 스케줄러
KEPCO E&C 전략 인텔리전스 시스템 v2.0

매일 오전 07:00 KST(UTC+9)에 pipeline.run()을 자동 실행합니다.
실행: python scheduler.py
"""

import logging
import os
import signal
import sys

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

import pipeline

logger = logging.getLogger("scheduler")

SCHEDULE_HOUR = int(os.getenv("SCHEDULE_HOUR", "7"))
SCHEDULE_MINUTE = int(os.getenv("SCHEDULE_MINUTE", "0"))

# 한국시간 KST = UTC+9이므로 GitHub Actions cron은 UTC 기준
# 로컬 실행 시 timezone="Asia/Seoul" 사용
TIMEZONE = "Asia/Seoul"


def run_pipeline():
    """스케줄러가 호출하는 파이프라인 실행 함수"""
    try:
        logger.info("스케줄러: 파이프라인 자동 실행 시작")
        pipeline.run()
    except Exception as e:
        logger.error(f"파이프라인 실행 오류: {e}", exc_info=True)


def main():
    scheduler = BlockingScheduler(timezone=TIMEZONE)

    trigger = CronTrigger(
        hour=SCHEDULE_HOUR,
        minute=SCHEDULE_MINUTE,
        timezone=TIMEZONE,
    )
    scheduler.add_job(run_pipeline, trigger, id="daily_briefing", replace_existing=True)

    logger.info(
        f"스케줄러 시작: 매일 {SCHEDULE_HOUR:02d}:{SCHEDULE_MINUTE:02d} {TIMEZONE} 자동 실행"
    )

    def _shutdown(signum, frame):
        logger.info("스케줄러 종료 신호 수신")
        scheduler.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    scheduler.start()


if __name__ == "__main__":
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    )
    main()
