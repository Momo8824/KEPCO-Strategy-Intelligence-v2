import os
from dotenv import load_dotenv
from notion_client import Client

load_dotenv()

client = Client(auth=os.environ.get("NOTION_API_KEY"))
db_id = os.environ.get("NOTION_DATABASE_ID")

db = client.databases.retrieve(database_id=db_id)

# 기존 title 속성 찾기 (이름, Name 등)
title_prop_name = None
for k, v in db["properties"].items():
    if v["type"] == "title":
        title_prop_name = k
        break

properties_to_update = {
    "Source": {"select": {}},
    "URL": {"url": {}},
    "PublishedDate": {"date": {}},
    "Importance": {"select": {}},
    "Summary": {"rich_text": {}},
    "Opportunity": {"rich_text": {}},
    "Threat": {"rich_text": {}},
    "ActionPoint": {"rich_text": {}},
    "ProcessedAt": {"date": {}},
}

# 기존 title 속성의 이름이 'Title'이 아닐 경우 이름 변경
if title_prop_name and title_prop_name != "Title":
    properties_to_update[title_prop_name] = {"name": "Title", "title": {}}
elif not title_prop_name:
    # 혹시 없다면 (거의 불가능하지만) 새로 생성 시도
    properties_to_update["Title"] = {"title": {}}

try:
    print(f"Updating Database: {db_id}")
    client.databases.update(
        database_id=db_id,
        properties=properties_to_update
    )
    print("✅ 성공적으로 10개 속성(Property)이 추가/업데이트 되었습니다.")
except Exception as e:
    print(f"❌ 속성 업데이트 실패:")
    import traceback
    traceback.print_exc()
