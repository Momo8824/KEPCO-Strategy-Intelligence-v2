import sys
from pathlib import Path
from datetime import datetime, timezone
from scv.rss_collector import Article
from agents.analyzer_agent import AnalyzerAgent

def main():
    agent = AnalyzerAgent()
    dummy = Article(
        title="Westinghouse and CEZ sign agreement for AP1000 deployment in Czechia",
        url="https://example.com/news/123",
        source_name="Nuclear News",
        published_at=datetime.now(timezone.utc),
        summary="Westinghouse has signed a MoU with CEZ to explore deploying AP1000 reactors in the Czech Republic, intensifying competition with KEPCO.",
        category="Nuclear",
        language="en"
    )
    print("Running Analyst 2 on dummy article...")
    try:
        res = agent._step2_analyze(dummy)
        print("\n--- PASSED ---")
        print("Summary:", res.summary)
        print("Opportunity:", res.opportunity)
        print("Threat:", res.threat)
        print("Action:", res.action_point)
    except Exception as e:
        print(f"\n--- FAILED ---: {e}")

if __name__ == "__main__":
    main()
