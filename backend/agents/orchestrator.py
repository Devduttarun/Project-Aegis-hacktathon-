import json, uuid, os
from typing import AsyncGenerator
from groq import Groq
from core.provenance import ProvenanceTracker
from core.intent_drift import check_intent_drift
from tools.gmail_tool import GmailTool
from tools.notion_tool import NotionTool

client = Groq(api_key=os.environ.get("GROQ_API_KEY",""))

TOOLS = [
    {"type":"function","function":{"name":"gmail_get_unread","description":"Get unread emails from Gmail inbox.",
     "parameters":{"type":"object","properties":{"max_results":{"type":"integer","default":10}}}}},
    {"type":"function","function":{"name":"gmail_search","description":"Search Gmail.",
     "parameters":{"type":"object","properties":{"query":{"type":"string"},"max_results":{"type":"integer","default":10}},"required":["query"]}}},
    {"type":"function","function":{"name":"notion_create_page","description":"Create a Notion page.",
     "parameters":{"type":"object","properties":{"title":{"type":"string"},"sections":{"type":"array","items":{"type":"object","properties":{"heading":{"type":"string"},"items":{"type":"array","items":{"type":"string"}}}}}},"required":["title","sections"]}}},
    {"type":"function","function":{"name":"notion_get_databases","description":"List Notion databases.",
     "parameters":{"type":"object","properties":{}}}}
]

async def generate_template_name(task: str) -> str:
    try:
        resp = client.chat.completions.create(model="llama-3.1-8b-instant", max_tokens=20,
            messages=[{"role":"user","content":f"Give this task a name (3-5 words, title case, no punctuation): {task}\nReply with ONLY the name."}])
        return resp.choices[0].message.content.strip().strip('"').strip("'")
    except Exception:
        return "Saved Task"

def build_notion_blocks(sections):
    blocks = []
    for s in sections:
        if s.get("heading"):
            blocks.append({"object":"block","type":"heading_2","heading_2":{"rich_text":[{"type":"text","text":{"content":s["heading"]}}]}})
        for item in s.get("items",[]):
            blocks.append({"object":"block","type":"bulleted_list_item","bulleted_list_item":{"rich_text":[{"type":"text","text":{"content":item}}]}})
        blocks.append({"object":"block","type":"paragraph","paragraph":{"rich_text":[]}})
    return blocks

async def run_task(user_id, task, scope_config, memory_context="") -> AsyncGenerator[dict, None]:
    session_id = str(uuid.uuid4())[:8]
    tracker = ProvenanceTracker(session_id=session_id, original_intent=task)
    gmail = GmailTool(user_id=user_id, tracker=tracker, scope_config=scope_config.get("gmail",{}))
    notion = NotionTool(user_id=user_id, tracker=tracker, scope_config=scope_config.get("notion",{}))
    steps_log, outputs, undo_actions = [], [], []

    def log_step(msg, status="running", icon=""):
        e = {"message":msg,"status":status,"icon":icon}
        steps_log.append(e)
        return e

    try:
        yield {"type":"step","message":"Understanding your request...","status":"running","icon":"🧠"}
        orch = tracker.record("Orchestrator","orchestrator.plan",f"Planning: {task}","none",{"task":task},hop_count=0)
        mem_section = f"\n\n{memory_context}" if memory_context else ""
        system = f"You are Aegis, a secure AI agent. Use tools to complete the user's task. Be thorough but focused. Summarise clearly when done.{mem_section}"
        messages = [{"role":"user","content":task}]

        for _ in range(8):
            resp = client.chat.completions.create(
                model="llama-3.3-70b-versatile", max_tokens=4096,
                tools=TOOLS, tool_choice="auto",
                messages=[{"role":"system","content":system}]+messages)
            msg = resp.choices[0].message
            messages.append({"role":"assistant","content":msg.content or "",
                             "tool_calls": [{"id":t.id,"type":"function","function":{"name":t.function.name,"arguments":t.function.arguments}} for t in (msg.tool_calls or [])]})

            if not msg.tool_calls:
                suggested = await generate_template_name(task)
                if undo_actions:
                    from core.undo import save_undo_actions
                    save_undo_actions(session_id, user_id, undo_actions)
                log_step("Task complete","done","✅")
                yield {"type":"complete","summary":msg.content or "Done.",
                       "steps":steps_log,"audit_trail":tracker.to_audit_trail(),
                       "chain_verified":tracker.verify_chain(),"outputs":outputs,
                       "session_id":session_id,"suggested_template_name":suggested,
                       "has_undo":len(undo_actions)>0}
                return

            tool_results = []
            for tc in msg.tool_calls:
                name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments)
                except Exception:
                    args = {}
                desc = {"gmail_get_unread":f"Reading {args.get('max_results',10)} unread emails",
                        "gmail_search":f"Searching Gmail: '{args.get('query','')}'",
                        "notion_create_page":f"Creating Notion page: '{args.get('title','')}'",
                        "notion_get_databases":"Listing Notion databases"}.get(name, name)
                icon = {"gmail_get_unread":"📧","gmail_search":"🔍","notion_create_page":"📝","notion_get_databases":"🗂️"}.get(name,"⚙️")
                yield {"type":"tool_call","tool":name,"description":desc,"icon":icon}
                log_step(desc,"running",icon)
                try:
                    if name=="gmail_get_unread":
                        result = await gmail.get_unread_emails(args.get("max_results",10),orch.record_id)
                    elif name=="gmail_search":
                        result = await gmail.search_emails(args["query"],args.get("max_results",10),orch.record_id)
                    elif name=="notion_get_databases":
                        result = await notion.get_databases(orch.record_id)
                    elif name=="notion_create_page":
                        blocks = build_notion_blocks(args.get("sections",[]))
                        result = await notion.create_page(args["title"],blocks,parent_record_id=orch.record_id)
                        if result.get("page_url"):
                            outputs.append({"type":"notion_page","title":result.get("title","Untitled"),"url":result["page_url"]})
                            undo_actions.append({"type":"notion.create_page","payload":{"page_id":result["page_id"],"title":result.get("title","")}})
                    else:
                        result = {"error":f"Unknown tool: {name}"}
                    if result.get("drift_check",{}).get("risk_level")=="caution":
                        yield {"type":"drift_warning","action":desc,"reason":result["drift_check"]["reason"]}
                    log_step(desc,"done",icon)
                    tool_results.append({"role":"tool","tool_call_id":tc.id,"content":json.dumps(result,default=str)})
                except Exception as e:
                    yield {"type":"step","message":f"Issue: {str(e)}","status":"error","icon":"⚠️"}
                    tool_results.append({"role":"tool","tool_call_id":tc.id,"content":f"Error: {str(e)}"})
            messages.extend(tool_results)

        yield {"type":"complete","summary":"Task completed.","steps":steps_log,
               "audit_trail":tracker.to_audit_trail(),"chain_verified":tracker.verify_chain(),
               "outputs":outputs,"session_id":session_id,"suggested_template_name":"Saved Task","has_undo":False}
    except Exception as e:
        yield {"type":"error","message":str(e)}
