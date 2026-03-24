import httpx, base64
from typing import Optional
from core.token_vault import get_token
from core.provenance import ProvenanceTracker
from core.intent_drift import check_intent_drift

class GmailTool:
    def __init__(self, user_id, tracker, scope_config):
        self.user_id = user_id
        self.tracker = tracker
        self.scope_config = scope_config
        self.base_url = "https://gmail.googleapis.com/gmail/v1"

    async def _headers(self):
        t = await get_token(self.user_id, "google-oauth2")
        return {"Authorization": f"Bearer {t['access_token']}"}

    async def get_unread_emails(self, max_results=10, parent_record_id=None):
        if not self.scope_config.get("can_read", True):
            raise PermissionError("Gmail read disabled in scope settings.")
        drift = await check_intent_drift(self.tracker.original_intent,
            f"Read up to {max_results} unread emails", "gmail.read_unread")
        if drift["risk_level"] == "block":
            raise ValueError(f"Blocked: {drift['reason']}")
        record = self.tracker.record("GmailAgent", "gmail.read_unread",
            f"Read up to {max_results} unread emails",
            "gmail.readonly", {"max_results": max_results},
            parent_id=parent_record_id, hop_count=1)
        headers = await self._headers()
        async with httpx.AsyncClient() as c:
            resp = await c.get(f"{self.base_url}/users/me/messages",
                headers=headers, params={"q": "is:unread", "maxResults": max_results})
            resp.raise_for_status()
            ids = [m["id"] for m in resp.json().get("messages", [])]
            emails = []
            for mid in ids[:max_results]:
                mr = await c.get(f"{self.base_url}/users/me/messages/{mid}",
                    headers=headers, params={"format": "full"})
                if mr.status_code != 200: continue
                msg = mr.json()
                hmap = {h["name"].lower(): h["value"] for h in msg.get("payload",{}).get("headers",[])}
                body = ""
                payload = msg.get("payload", {})
                if payload.get("body",{}).get("data"):
                    body = base64.urlsafe_b64decode(payload["body"]["data"]+"==").decode("utf-8",errors="ignore")
                elif payload.get("parts"):
                    for p in payload["parts"]:
                        if p.get("mimeType")=="text/plain" and p.get("body",{}).get("data"):
                            body = base64.urlsafe_b64decode(p["body"]["data"]+"==").decode("utf-8",errors="ignore")
                            break
                emails.append({"id": mid, "subject": hmap.get("subject","(no subject)"),
                    "from": hmap.get("from","unknown"), "date": hmap.get("date",""),
                    "snippet": msg.get("snippet",""), "body": body[:2000]})
        return {"emails": emails, "count": len(emails),
                "provenance_record_id": record.record_id, "drift_check": drift}

    async def search_emails(self, query, max_results=10, parent_record_id=None):
        if not self.scope_config.get("can_read", True):
            raise PermissionError("Gmail read disabled.")
        drift = await check_intent_drift(self.tracker.original_intent,
            f"Search Gmail: {query}", "gmail.search")
        if drift["risk_level"] == "block":
            raise ValueError(f"Blocked: {drift['reason']}")
        record = self.tracker.record("GmailAgent", "gmail.search",
            f"Search Gmail: '{query}'", "gmail.readonly",
            {"query": query}, parent_id=parent_record_id, hop_count=1)
        headers = await self._headers()
        async with httpx.AsyncClient() as c:
            resp = await c.get(f"{self.base_url}/users/me/messages",
                headers=headers, params={"q": query, "maxResults": max_results})
            resp.raise_for_status()
            data = resp.json()
        return {"message_ids": [m["id"] for m in data.get("messages",[])],
                "count": data.get("resultSizeEstimate",0),
                "provenance_record_id": record.record_id}
