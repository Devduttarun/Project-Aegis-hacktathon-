import json, os
from groq import Groq

client = Groq(api_key=os.environ.get("GROQ_API_KEY", ""))

async def check_intent_drift(original_intent: str, proposed_action: str, action_type: str, context: str = "") -> dict:
    prompt = f"""You are a security guardrail for an AI agent.
User's ORIGINAL intent: "{original_intent}"
Sub-agent proposes: "{proposed_action}" (type: {action_type})
{f'Context: {context}' if context else ''}
Reply ONLY with valid JSON:
{{"aligned": true/false, "confidence": "high"/"medium"/"low", "reason": "one sentence", "risk_level": "safe"/"caution"/"block"}}
Block if: destructive, irreversible, or clearly unrelated. Caution if: writing/creating/sending."""
    try:
        resp = client.chat.completions.create(
            model="llama-3.1-8b-instant", max_tokens=150,
            messages=[{"role": "user", "content": prompt}])
        return json.loads(resp.choices[0].message.content.strip())
    except Exception:
        return {"aligned": True, "confidence": "low", "reason": "Could not evaluate", "risk_level": "caution"}
