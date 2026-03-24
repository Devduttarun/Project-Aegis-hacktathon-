"""
Token Vault — Development Mode
--------------------------------
In production this calls Auth0 Token Vault.
For local dev we use tokens stored in .env directly.
Swap this file for the real Token Vault client before final submission.
"""
import os

async def get_token(user_id: str, connection: str) -> dict:
    if connection == "google-oauth2":
        return {"access_token": os.environ.get("GOOGLE_ACCESS_TOKEN", "")}
    elif connection == "notion":
        return {"access_token": os.environ.get("NOTION_TOKEN", "")}
    raise ValueError(f"Unknown connection: {connection}")

async def list_connections(user_id: str) -> list:
    conns = []
    if os.environ.get("GOOGLE_ACCESS_TOKEN"):
        conns.append({"connection": "google-oauth2", "name": "Gmail"})
    if os.environ.get("NOTION_TOKEN"):
        conns.append({"connection": "notion", "name": "Notion"})
    return conns

async def revoke_token(user_id: str, connection: str) -> bool:
    return True
