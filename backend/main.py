import json, os
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import httpx

from agents.orchestrator import run_task
from core.token_vault import get_token, list_connections, revoke_token
from core.risk_meter import score_task
from core.nl_permissions import parse_permission_rule, DEFAULT_SCOPE
from core.undo import execute_undo
from core.memory import (load_memory, save_memory, add_permission_rule,
    save_template, get_templates, extract_and_save_memories, get_memory_context)

app = FastAPI(title="Aegis API", version="2.0.0")
app.add_middleware(CORSMiddleware,
    allow_origins=[os.environ.get("FRONTEND_URL","http://localhost:5173")],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

AUTH0_DOMAIN = os.environ.get("AUTH0_DOMAIN","")

async def get_current_user(request: Request) -> dict:
    auth = request.headers.get("Authorization","")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Missing auth header")
    async with httpx.AsyncClient() as c:
        r = await c.get(f"https://{AUTH0_DOMAIN}/userinfo",
            headers={"Authorization": auth})
        if r.status_code != 200:
            raise HTTPException(401, "Invalid token")
        return r.json()

class TaskRequest(BaseModel):
    task: str
    skip_sandbox: bool = False

class RiskRequest(BaseModel):
    task: str

class PermissionRuleRequest(BaseModel):
    rule: str

class TemplateSaveRequest(BaseModel):
    name: str
    task: str
    icon: str = "⚡"

@app.get("/health")
async def health():
    return {"status":"ok","version":"2.0.0"}

@app.post("/api/task/assess")
async def assess(body: RiskRequest, user: dict = Depends(get_current_user)):
    memory = load_memory(user["sub"])
    risk = await score_task(body.task, memory.get("permission_rules",[]))
    return {"risk":risk,"scope_config":memory.get("scope_config",DEFAULT_SCOPE),
            "requires_approval":risk.get("requires_sandbox_approval",False)}

@app.post("/api/task/run")
async def run(body: TaskRequest, user: dict = Depends(get_current_user)):
    uid = user["sub"]
    memory = load_memory(uid)
    scope = memory.get("scope_config", DEFAULT_SCOPE)
    if not body.skip_sandbox:
        risk = await score_task(body.task, memory.get("permission_rules",[]))
        if risk.get("requires_sandbox_approval"):
            raise HTTPException(428, detail={"risk":risk,"message":"sandbox_approval_required"})
    async def stream():
        final = ""
        async for event in run_task(uid, body.task, scope, get_memory_context(uid)):
            if event.get("type")=="complete":
                final = event.get("summary","")
            yield f"data: {json.dumps(event)}\n\n"
        if final:
            await extract_and_save_memories(uid, body.task, final)
        yield "data: [DONE]\n\n"
    return StreamingResponse(stream(), media_type="text/event-stream",
        headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})

@app.get("/api/connections")
async def connections(user: dict = Depends(get_current_user)):
    try:
        conns = await list_connections(user["sub"])
        return {"connections":conns,"user":user.get("email",user["sub"])}
    except Exception as e:
        return {"connections":[],"error":str(e)}

@app.delete("/api/connections/{connection}")
async def revoke(connection: str, user: dict = Depends(get_current_user)):
    await revoke_token(user["sub"], connection)
    return {"revoked":connection}

@app.get("/api/permissions")
async def get_perms(user: dict = Depends(get_current_user)):
    m = load_memory(user["sub"])
    return {"rules":m.get("permission_rules",[]),"scope_config":m.get("scope_config",DEFAULT_SCOPE)}

@app.post("/api/permissions/rule")
async def add_rule(body: PermissionRuleRequest, user: dict = Depends(get_current_user)):
    m = load_memory(user["sub"])
    result = await parse_permission_rule(body.rule, m.get("scope_config",DEFAULT_SCOPE))
    add_permission_rule(user["sub"], body.rule, result)
    return {"rule_saved":body.rule,"parsed_as":result.get("parsed_rule",body.rule)}

@app.delete("/api/permissions/rule")
async def del_rule(rule: str, user: dict = Depends(get_current_user)):
    m = load_memory(user["sub"])
    m["permission_rules"] = [r for r in m.get("permission_rules",[]) if r!=rule]
    save_memory(user["sub"], m)
    return {"deleted":rule}

@app.get("/api/templates")
async def list_tmpl(user: dict = Depends(get_current_user)):
    return {"templates":get_templates(user["sub"])}

@app.post("/api/templates")
async def save_tmpl(body: TemplateSaveRequest, user: dict = Depends(get_current_user)):
    save_template(user["sub"], body.name, body.task, body.icon)
    return {"saved":True}

@app.delete("/api/templates/{name}")
async def del_tmpl(name: str, user: dict = Depends(get_current_user)):
    m = load_memory(user["sub"])
    m["templates"] = [t for t in m.get("templates",[]) if t["name"]!=name]
    save_memory(user["sub"], m)
    return {"deleted":name}

@app.get("/api/memory")
async def get_mem(user: dict = Depends(get_current_user)):
    return {"memories":load_memory(user["sub"]).get("memories",[])}

@app.delete("/api/memory")
async def clear_mem(user: dict = Depends(get_current_user)):
    m = load_memory(user["sub"])
    m["memories"] = []
    save_memory(user["sub"], m)
    return {"cleared":True}

@app.post("/api/task/undo/{session_id}")
async def undo(session_id: str, user: dict = Depends(get_current_user)):
    return await execute_undo(session_id)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
