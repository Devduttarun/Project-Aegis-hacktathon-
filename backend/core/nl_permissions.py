import json, os
from groq import Groq

client = Groq(api_key=os.environ.get("GROQ_API_KEY", ""))

DEFAULT_SCOPE = {
    "gmail": {"can_read": True, "can_send": False, "can_delete": False, "can_label": True, "max_emails_per_task": 20},
    "notion": {"can_write": True, "can_delete": False, "can_share": False, "max_pages_per_task": 5}
}

async def parse_permission_rule(rule: str, existing_config: dict) -> dict:
    prompt = f"""Convert this natural language permission rule into a structured scope config.
Rule: "{rule}"
Existing config: {json.dumps(existing_config)}
Merge and return ONLY valid JSON with updated config plus:
"parsed_rule": "plain English confirmation", "affected_field": "e.g. gmail.can_delete"
Format: {{"gmail":{{...}},"notion":{{...}},"parsed_rule":"...","affected_field":"..."}}"""
    try:
        resp = client.chat.completions.create(
            model="llama-3.1-8b-instant", max_tokens=300,
            messages=[{"role": "user", "content": prompt}])
        return json.loads(resp.choices[0].message.content.strip())
    except Exception:
        return {**existing_config, "parsed_rule": f"Could not parse: {rule}", "affected_field": "unknown"}
