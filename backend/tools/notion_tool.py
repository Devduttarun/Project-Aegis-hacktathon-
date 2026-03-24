import os
import httpx
from typing import Optional
from core.token_vault import get_token
from core.provenance import ProvenanceTracker
from core.intent_drift import check_intent_drift


class NotionTool:
    def __init__(self, user_id, tracker, scope_config):
        self.user_id = user_id
        self.tracker = tracker
        self.scope_config = scope_config
        self.base_url = "https://api.notion.com/v1"

    async def _headers(self):
        t = await get_token(self.user_id, "notion")
        return {"Authorization": f"Bearer {t['access_token']}",
                "Notion-Version": "2022-06-28", "Content-Type": "application/json"}

    async def get_databases(self, parent_record_id=None):
        record = self.tracker.record("NotionAgent","notion.list_databases",
            "List Notion databases","notion.read_content",{},
            parent_id=parent_record_id, hop_count=1)
        headers = await self._headers()
        async with httpx.AsyncClient() as c:
            resp = await c.post(f"{self.base_url}/search", headers=headers,
                json={"filter":{"value":"database","property":"object"}})
            resp.raise_for_status()
            dbs = [{"id":d["id"],"title":d.get("title",[{}])[0].get("plain_text","Untitled")
                    if d.get("title") else "Untitled"} for d in resp.json().get("results",[])]
        return {"databases": dbs, "provenance_record_id": record.record_id}

    async def create_page(self, title, content_blocks, parent_page_id=None,
                          parent_database_id=None, parent_record_id=None):
        if not self.scope_config.get("can_write", True):
            raise PermissionError("Notion write disabled.")
        drift = await check_intent_drift(self.tracker.original_intent,
            f"Create Notion page '{title}'","notion.create_page")
        if drift["risk_level"] == "block":
            raise ValueError(f"Blocked: {drift['reason']}")
        record = self.tracker.record("NotionAgent","notion.create_page",
            f"Create page: '{title}'","notion.insert_content",
            {"title":title,"blocks":len(content_blocks)},
            parent_id=parent_record_id, hop_count=1)
        if parent_database_id:
            parent = {"database_id": parent_database_id}
            props = {"Name":{"title":[{"text":{"content":title}}]}}
        elif parent_page_id:
            parent = {"page_id": parent_page_id}
            props = {"title":[{"text":{"content":title}}]}
        else:
            default_page_id = os.environ.get("NOTION_PAGE_ID", "")
            if default_page_id:
                parent = {"page_id": default_page_id}
            else:
                parent = {"type":"workspace","workspace":True}
            props = {"title":[{"text":{"content":title}}]}
        headers = await self._headers()
        async with httpx.AsyncClient() as c:
            resp = await c.post(f"{self.base_url}/pages", headers=headers,
                json={"parent":parent,"properties":props,"children":content_blocks})
            resp.raise_for_status()
            page = resp.json()
        return {"page_id":page["id"],"page_url":page.get("url",""),
                "title":title,"provenance_record_id":record.record_id,"drift_check":drift}