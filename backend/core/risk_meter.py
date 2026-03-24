import json, os
from groq import Groq

client = Groq(api_key=os.environ.get("GROQ_API_KEY", ""))

async def score_task(task: str, permission_rules: list[str]) -> dict:
    rules_text = "\n".join(f"- {r}" for r in permission_rules) if permission_rules else "- No custom rules"
    prompt = f"""Score the risk of this AI agent task (0-100).
Task: "{task}"
User rules:\n{rules_text}
Reply ONLY with valid JSON:
{{"risk_level":"low"/"medium"/"high","score":0-100,"headline":"max 10 words","reasons":["..."],"reversible":true/false,"requires_sandbox_approval":true/false,"estimated_actions":["..."]}}
low=read-only, medium=creates content, high=sends/deletes/shares. requires_sandbox_approval=true if score>=40."""
    try:
        resp = client.chat.completions.create(
            model="llama-3.1-8b-instant", max_tokens=300,
            messages=[{"role": "user", "content": prompt}])
        return json.loads(resp.choices[0].message.content.strip())
    except Exception:
        return {"risk_level":"medium","score":50,"headline":"Could not assess risk","reasons":["Manual review recommended"],
                "reversible":True,"requires_sandbox_approval":True,"estimated_actions":["Unknown"]}
