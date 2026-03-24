import json, os
from pathlib import Path
from groq import Groq

client = Groq(api_key=os.environ.get("GROQ_API_KEY", ""))
MEMORY_DIR = Path("./data/memory")
MEMORY_DIR.mkdir(parents=True, exist_ok=True)

def _path(user_id: str) -> Path:
    return MEMORY_DIR / f"{user_id.replace('|','_').replace('/','_')}.json"

def load_memory(user_id: str) -> dict:
    p = _path(user_id)
    return json.loads(p.read_text()) if p.exists() else {"memories":[],"permission_rules":[],"scope_config":{},"templates":[]}

def save_memory(user_id: str, data: dict):
    _path(user_id).write_text(json.dumps(data, indent=2))

def get_memory_context(user_id: str) -> str:
    data = load_memory(user_id)
    parts = []
    if data.get("memories"):
        parts.append("User preferences:")
        for m in data["memories"][-20:]:
            parts.append(f"  - {m['value']}")
    if data.get("permission_rules"):
        parts.append("Permission rules (enforce these):")
        for r in data["permission_rules"]:
            parts.append(f"  - {r}")
    return "\n".join(parts)

def add_permission_rule(user_id: str, rule: str, scope_update: dict):
    data = load_memory(user_id)
    rules = data.get("permission_rules", [])
    if rule not in rules:
        rules.append(rule)
    data["permission_rules"] = rules
    data["scope_config"] = scope_update
    save_memory(user_id, data)

def save_template(user_id: str, name: str, task: str, icon: str = "⚡"):
    data = load_memory(user_id)
    templates = [t for t in data.get("templates", []) if t["task"] != task]
    templates.insert(0, {"name": name, "task": task, "icon": icon})
    data["templates"] = templates[:20]
    save_memory(user_id, data)

def get_templates(user_id: str) -> list:
    return load_memory(user_id).get("templates", [])

async def extract_and_save_memories(user_id: str, task: str, result_summary: str):
    try:
        resp = client.chat.completions.create(
            model="llama-3.1-8b-instant", max_tokens=200,
            messages=[{"role":"user","content":f"""Extract user preferences worth remembering from this completed task.
Task: "{task}" Result: "{result_summary}"
Reply ONLY with JSON: {{"new_memories":[{{"key":"...","value":"...","category":"preference/fact/style"}}]}}
If nothing: {{"new_memories":[]}}"""}])
        result = json.loads(resp.choices[0].message.content.strip())
        new_mems = result.get("new_memories", [])
        if new_mems:
            data = load_memory(user_id)
            existing = data.get("memories", [])
            keys = {m["key"] for m in existing}
            for nm in new_mems:
                if nm["key"] not in keys:
                    existing.append(nm)
                else:
                    for m in existing:
                        if m["key"] == nm["key"]:
                            m["value"] = nm["value"]
            data["memories"] = existing[-50:]
            save_memory(user_id, data)
    except Exception:
        pass
