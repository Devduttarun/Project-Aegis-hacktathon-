import httpx, json, time
from pathlib import Path
from core.token_vault import get_token

UNDO_DIR = Path("./data/undo")
UNDO_DIR.mkdir(parents=True, exist_ok=True)
UNDO_TTL = 300

def save_undo_actions(session_id: str, user_id: str, actions: list):
    data = {"session_id": session_id, "user_id": user_id, "created_at": time.time(), "actions": actions, "undone": False}
    (UNDO_DIR / f"{session_id}.json").write_text(json.dumps(data))

def load_undo(session_id: str):
    p = UNDO_DIR / f"{session_id}.json"
    if not p.exists(): return None
    data = json.loads(p.read_text())
    if time.time() - data["created_at"] > UNDO_TTL or data.get("undone"): return None
    return data

def mark_undone(session_id: str):
    p = UNDO_DIR / f"{session_id}.json"
    if not p.exists(): return
    data = json.loads(p.read_text())
    data["undone"] = True
    p.write_text(json.dumps(data))

async def execute_undo(session_id: str) -> dict:
    data = load_undo(session_id)
    if not data:
        return {"success": False, "reason": "Nothing to undo — 5 min window may have expired."}
    undone, failed = [], []
    for action in reversed(data["actions"]):
        try:
            if action["type"] == "notion.create_page":
                token = await get_token(data["user_id"], "notion")
                async with httpx.AsyncClient() as c:
                    r = await c.patch(f"https://api.notion.com/v1/pages/{action['payload']['page_id']}",
                        headers={"Authorization": f"Bearer {token['access_token']}",
                                 "Notion-Version": "2022-06-28", "Content-Type": "application/json"},
                        json={"archived": True})
                    r.raise_for_status()
                undone.append(f"Deleted Notion page: '{action['payload'].get('title','Untitled')}'")
        except Exception as e:
            failed.append(str(e))
    mark_undone(session_id)
    return {"success": True, "undone": undone, "failed": failed,
            "message": f"Reversed {len(undone)} action(s)."}
