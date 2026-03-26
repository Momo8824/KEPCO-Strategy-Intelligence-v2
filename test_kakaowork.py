import sys
from datetime import datetime, timezone
sys.path.append("f:\\KEPCO_E&C_Strategy_Intelligence")
from scv.rss_collector import Article
from agents.notifier_agent import KakaoWorkNotifier
import logging

logging.basicConfig(level=logging.INFO)

dummy_article = Article(
    title='[테스트] 카카오워크 Webhook 연동 정상 작동 확인',
    url='https://example.com',
    source_name='System',
    published_at=datetime.now(timezone.utc),
    summary='카카오워크 연동 테스트를 위한 가짜 기사입니다.',
    importance='High',
    opportunity='N/A',
    threat='N/A',
    action_point='연동 성공 확인',
    category='test',
    language='ko'
)

agent = KakaoWorkNotifier()
print(f"[{datetime.now().strftime('%H:%M:%S')}] 카카오워크 전송 테스트 중...")
result = agent.send([dummy_article])
print(f"테스트 전송 결과: {'성공 (200 OK)' if result else '실패'}")
