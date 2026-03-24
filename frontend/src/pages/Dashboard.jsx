import { useState, useEffect } from 'react'
import { useAuth0 } from '@auth0/auth0-react'
import { useApi } from '../hooks/useApi.js'

export default function Dashboard() {
  const { user, logout } = useAuth0()
  const api = useApi()
  const [task, setTask] = useState('')
  const [phase, setPhase] = useState('idle')
  const [steps, setSteps] = useState([])
  const [result, setResult] = useState(null)
  const [risk, setRisk] = useState(null)
  const [errorMsg, setErrorMsg] = useState('')
  const [templates, setTemplates] = useState([])
  const [rules, setRules] = useState([])
  const [memories, setMemories] = useState([])
  const [activeTab, setActiveTab] = useState('run')
  const [ruleInput, setRuleInput] = useState('')
  const [sandboxOpen, setSandboxOpen] = useState(false)
  const [driftWarnings, setDriftWarnings] = useState([])
  const [templateName, setTemplateName] = useState('')
  const [saved, setSaved] = useState(false)

  useEffect(() => { loadAll() }, [])

  async function loadAll() {
    try {
      const [t,p,m] = await Promise.allSettled([api.get('/templates'),api.get('/permissions'),api.get('/memory')])
      if(t.status==='fulfilled') setTemplates(t.value.templates||[])
      if(p.status==='fulfilled') setRules(p.value.rules||[])
      if(m.status==='fulfilled') setMemories(m.value.memories||[])
    } catch{}
  }

  async function handleRun() {
    if(!task.trim()||phase!=='idle') return
    setPhase('assessing'); setResult(null); setSteps([])
    setDriftWarnings([]); setErrorMsg(''); setSaved(false)
    try {
      const res = await api.post('/task/assess',{task})
      setRisk(res.risk)
      if(res.requires_approval) { setSandboxOpen(true); setPhase('idle'); return }
      await executeTask()
    } catch(e) { setPhase('error'); setErrorMsg('Could not assess task.') }
  }

  async function executeTask() {
    setSandboxOpen(false); setPhase('running')
    try {
      await api.stream('/task/run',{task,skip_sandbox:true},(event)=>{
        if(event.type==='step'||event.type==='tool_call') {
          setSteps(prev=>[...prev,{message:event.description||event.message,status:event.status||'running',icon:event.icon||'·'}])
        } else if(event.type==='drift_warning') {
          setDriftWarnings(prev=>[...prev,event])
        } else if(event.type==='complete') {
          setResult(event); setPhase('done')
          if(event.suggested_template_name) setTemplateName(event.suggested_template_name)
        } else if(event.type==='error') {
          setErrorMsg(event.message); setPhase('error')
        }
      })
    } catch(e) { setPhase('error'); setErrorMsg(e?.detail?.message||'Something went wrong') }
  }

  async function saveTemplate() {
    if(!templateName.trim()) return
    await api.post('/templates',{name:templateName,task,icon:'⚡'})
    setSaved(true)
    const t = await api.get('/templates')
    setTemplates(t.templates||[])
  }

  async function addRule() {
    if(!ruleInput.trim()) return
    await api.post('/permissions/rule',{rule:ruleInput})
    setRules(prev=>[...prev,ruleInput]); setRuleInput('')
  }

  async function deleteRule(rule) {
    await api.del(`/permissions/rule?rule=${encodeURIComponent(rule)}`)
    setRules(prev=>prev.filter(r=>r!==rule))
  }

  function reset() {
    setPhase('idle'); setTask(''); setResult(null)
    setSteps([]); setErrorMsg(''); setDriftWarnings([])
    setRisk(null); setSaved(false)
  }

  const isRunning = phase==='running'
  const color = risk ? (risk.risk_level==='high'?'#ff6b6b':risk.risk_level==='medium'?'#ffb347':'#5dd8b8') : '#5dd8b8'

  return (
    <div style={{minHeight:'100vh',display:'flex',flexDirection:'column'}}>
      <header style={{borderBottom:'1px solid rgba(255,255,255,0.07)',padding:'0 24px',height:52,display:'flex',alignItems:'center',gap:16,flexShrink:0}}>
        <div style={{display:'flex',alignItems:'center',gap:8}}>
          <div style={{width:8,height:8,borderRadius:'50%',background:'#c8f060'}}/>
          <span style={{fontFamily:'var(--font-display)',fontSize:18,letterSpacing:'-0.02em'}}>Aegis</span>
        </div>
        <div style={{display:'flex',gap:2,marginLeft:24}}>
          {[['run','Run task'],['permissions','Permissions'],['memory','Memory']].map(([tab,label])=>(
            <button key={tab} onClick={()=>setActiveTab(tab)} style={{background:activeTab===tab?'rgba(255,255,255,0.07)':'none',border:'none',color:activeTab===tab?'#e8e6e0':'#888680',padding:'6px 14px',borderRadius:6,cursor:'pointer',fontSize:13,fontFamily:'var(--font-body)'}}>{label}</button>
          ))}
        </div>
        <div style={{marginLeft:'auto',display:'flex',alignItems:'center',gap:12}}>
          <span style={{fontSize:12,color:'#555350'}}>{user?.email}</span>
          <button onClick={()=>logout({logoutParams:{returnTo:window.location.origin}})} style={{background:'none',border:'1px solid rgba(255,255,255,0.07)',borderRadius:6,padding:'4px 10px',fontSize:11,color:'#888680',cursor:'pointer'}}>Sign out</button>
        </div>
      </header>

      <main style={{flex:1,maxWidth:760,width:'100%',margin:'0 auto',padding:'32px 24px'}}>

        {activeTab==='run' && (
          <div>
            {templates.length>0 && (
              <div style={{display:'flex',gap:8,flexWrap:'wrap',marginBottom:20}}>
                {templates.map((t,i)=>(
                  <button key={i} onClick={()=>{reset();setTask(t.task)}} style={{background:'rgba(255,255,255,0.05)',border:'1px solid rgba(255,255,255,0.07)',borderRadius:6,padding:'6px 12px',fontSize:12,color:'#888680',cursor:'pointer'}}>{t.icon} {t.name}</button>
                ))}
              </div>
            )}

            <div style={{border:`1px solid ${isRunning?'#c8f060':'rgba(255,255,255,0.13)'}`,borderRadius:16,overflow:'hidden',background:'#141416',transition:'border-color 0.3s'}}>
              <textarea value={task} onChange={e=>setTask(e.target.value)}
                onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();handleRun()}}}
                placeholder="e.g. Summarize my unread emails and save action items to Notion"
                disabled={isRunning} rows={3}
                style={{width:'100%',padding:'18px 20px',background:'transparent',border:'none',outline:'none',resize:'none',fontSize:15,color:'#e8e6e0',fontFamily:'var(--font-body)',lineHeight:1.6}}/>
              <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',padding:'8px 12px 12px',borderTop:'1px solid rgba(255,255,255,0.07)'}}>
                <span style={{fontSize:11,color:'#555350',fontFamily:'var(--font-mono)'}}>{isRunning?'running...':'enter ↵ to run'}</span>
                <div style={{display:'flex',gap:8}}>
                  {phase!=='idle'&&!isRunning&&(
                    <button onClick={reset} style={{background:'none',border:'1px solid rgba(255,255,255,0.13)',borderRadius:8,padding:'8px 16px',fontSize:13,color:'#888680',cursor:'pointer'}}>Clear</button>
                  )}
                  <button onClick={handleRun} disabled={!task.trim()||phase!=='idle'}
                    style={{background:task.trim()&&phase==='idle'?'#c8f060':'rgba(255,255,255,0.05)',color:task.trim()&&phase==='idle'?'#0c0c0e':'#555350',border:'none',borderRadius:8,padding:'8px 20px',fontSize:13,fontWeight:500,cursor:task.trim()&&phase==='idle'?'pointer':'default',fontFamily:'var(--font-body)'}}>
                    {phase==='assessing'?'Assessing...':'Run →'}
                  </button>
                </div>
              </div>
            </div>

            {risk && (
              <div style={{marginTop:16,padding:16,borderRadius:10,border:`1px solid ${color}44`,background:`${color}09`}}>
                <div style={{display:'flex',justifyContent:'space-between',marginBottom:8}}>
                  <span style={{fontSize:13,fontFamily:'var(--font-mono)',color,textTransform:'uppercase',letterSpacing:'0.1em'}}>{risk.risk_level} risk</span>
                  <span style={{fontSize:20,fontWeight:500,fontFamily:'var(--font-mono)',color}}>{risk.score}</span>
                </div>
                <div style={{height:4,borderRadius:2,background:'rgba(255,255,255,0.07)',marginBottom:8}}>
                  <div style={{height:'100%',width:`${risk.score}%`,background:color,borderRadius:2,transition:'width 0.6s ease'}}/>
                </div>
                <p style={{fontSize:13,color:'#e8e6e0'}}>{risk.headline}</p>
              </div>
            )}

            {driftWarnings.map((w,i)=>(
              <div key={i} style={{marginTop:8,padding:'8px 12px',borderRadius:8,background:'rgba(255,179,71,0.07)',border:'1px solid rgba(255,179,71,0.2)',fontSize:12,color:'#ffb347'}}>⚠ Intent drift: {w.reason}</div>
            ))}

            {steps.length>0 && (
              <div style={{marginTop:20}}>
                <p style={{fontSize:11,fontFamily:'var(--font-mono)',color:'#555350',textTransform:'uppercase',letterSpacing:'0.1em',marginBottom:12}}>Live activity</p>
                <div style={{display:'flex',flexDirection:'column',gap:6}}>
                  {steps.map((s,i)=>(
                    <div key={i} style={{display:'flex',alignItems:'center',gap:10,padding:'8px 12px',borderRadius:8,background:'rgba(255,255,255,0.03)',border:'1px solid rgba(255,255,255,0.07)'}}>
                      <span style={{fontSize:14,minWidth:20}}>{s.status==='done'?'✓':s.icon}</span>
                      <span style={{fontSize:13,color:s.status==='done'?'#888680':'#e8e6e0',flex:1}}>{s.message}</span>
                      {s.status==='running'&&<div style={{width:12,height:12,borderRadius:'50%',border:'1.5px solid rgba(255,255,255,0.13)',borderTopColor:'#c8f060',animation:'spin 0.7s linear infinite'}}/>}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {result && (
              <div style={{marginTop:20}}>
                <div style={{display:'flex',alignItems:'center',gap:10,marginBottom:16}}>
                  <div style={{width:8,height:8,borderRadius:'50%',background:'#c8f060'}}/>
                  <span style={{fontSize:13,fontFamily:'var(--font-mono)',color:'#888680',textTransform:'uppercase',letterSpacing:'0.1em'}}>
                    Task complete {result.chain_verified?'· ✓ chain verified':''}
                  </span>
                </div>
                <div style={{background:'rgba(255,255,255,0.03)',borderRadius:10,padding:16,border:'1px solid rgba(255,255,255,0.07)',marginBottom:12}}>
                  <p style={{fontSize:13,color:'#e8e6e0',lineHeight:1.7,whiteSpace:'pre-wrap'}}>{result.summary}</p>
                </div>
                {result.outputs?.map((o,i)=>(
                  <a key={i} href={o.url} target="_blank" rel="noreferrer"
                    style={{display:'flex',alignItems:'center',gap:10,padding:'10px 14px',borderRadius:8,background:'rgba(255,255,255,0.03)',border:'1px solid rgba(255,255,255,0.07)',textDecoration:'none',color:'#e8e6e0',marginBottom:6}}>
                    <span>📝</span>
                    <div>
                      <p style={{fontSize:13}}>{o.title}</p>
                      <p style={{fontSize:11,color:'#555350',fontFamily:'var(--font-mono)'}}>Notion page created →</p>
                    </div>
                  </a>
                ))}
                {!saved ? (
                  <div style={{display:'flex',gap:8,padding:12,background:'rgba(255,255,255,0.03)',borderRadius:8,border:'1px solid rgba(255,255,255,0.07)',marginTop:12}}>
                    <input placeholder="Save as template..." value={templateName}
                      onChange={e=>setTemplateName(e.target.value)}
                      onKeyDown={e=>e.key==='Enter'&&saveTemplate()}
                      style={{flex:1,background:'transparent',border:'none',outline:'none',fontSize:13,color:'#e8e6e0',fontFamily:'var(--font-body)'}}/>
                    <button onClick={saveTemplate} disabled={!templateName.trim()}
                      style={{background:templateName.trim()?'#c8f060':'rgba(255,255,255,0.05)',color:templateName.trim()?'#0c0c0e':'#555350',border:'none',borderRadius:6,padding:'6px 14px',fontSize:12,cursor:templateName.trim()?'pointer':'default'}}>
                      Save
                    </button>
                  </div>
                ) : (
                  <p style={{fontSize:12,color:'#5dd8b8',fontFamily:'var(--font-mono)',marginTop:8}}>✓ Template saved</p>
                )}
              </div>
            )}

            {phase==='error' && (
              <div style={{marginTop:16,padding:'12px 16px',borderRadius:8,background:'rgba(255,107,107,0.07)',border:'1px solid rgba(255,107,107,0.2)'}}>
                <p style={{fontSize:13,color:'#ff6b6b'}}>⚠ {errorMsg}</p>
              </div>
            )}
          </div>
        )}

        {activeTab==='permissions' && (
          <div>
            <h2 style={{fontFamily:'var(--font-display)',fontSize:28,marginBottom:8,letterSpacing:'-0.02em'}}>Permissions</h2>
            <p style={{color:'#888680',fontSize:14,marginBottom:28,lineHeight:1.6}}>Tell Aegis what it's allowed to do in plain English.</p>
            <div style={{display:'flex',gap:8,marginBottom:16}}>
              <input value={ruleInput} onChange={e=>setRuleInput(e.target.value)}
                onKeyDown={e=>e.key==='Enter'&&addRule()}
                placeholder='e.g. "Never delete emails"'
                style={{flex:1,background:'rgba(255,255,255,0.05)',border:'1px solid rgba(255,255,255,0.13)',borderRadius:10,padding:'10px 14px',fontSize:13,color:'#e8e6e0',outline:'none',fontFamily:'var(--font-body)'}}/>
              <button onClick={addRule} style={{background:'#c8f060',color:'#0c0c0e',border:'none',borderRadius:10,padding:'10px 18px',fontSize:13,cursor:'pointer',fontWeight:500}}>Add</button>
            </div>
            <div style={{display:'flex',gap:6,flexWrap:'wrap',marginBottom:16}}>
              {['Never delete emails','Only read last 7 days','Never create more than 3 pages','Never share externally'].map((ex,i)=>(
                <button key={i} onClick={()=>setRuleInput(ex)} style={{background:'none',border:'1px solid rgba(255,255,255,0.07)',borderRadius:999,padding:'4px 10px',fontSize:11,color:'#888680',cursor:'pointer',fontFamily:'var(--font-mono)'}}>{ex}</button>
              ))}
            </div>
            {rules.map((r,i)=>(
              <div key={i} style={{display:'flex',alignItems:'center',gap:10,padding:'8px 12px',background:'rgba(255,255,255,0.03)',borderRadius:8,border:'1px solid rgba(255,255,255,0.07)',marginBottom:6}}>
                <span style={{fontSize:12,color:'#5dd8b8'}}>🔒</span>
                <span style={{flex:1,fontSize:13,color:'#e8e6e0'}}>{r}</span>
                <button onClick={()=>deleteRule(r)} style={{background:'none',border:'none',cursor:'pointer',color:'#555350',fontSize:14}}>×</button>
              </div>
            ))}
            {rules.length===0 && <p style={{fontSize:13,color:'#555350',fontStyle:'italic'}}>No rules set. Using safe defaults.</p>}
          </div>
        )}

        {activeTab==='memory' && (
          <div>
            <div style={{display:'flex',alignItems:'baseline',justifyContent:'space-between',marginBottom:8}}>
              <h2 style={{fontFamily:'var(--font-display)',fontSize:28,letterSpacing:'-0.02em'}}>Smart memory</h2>
              {memories.length>0 && (
                <button onClick={async()=>{await api.del('/memory');setMemories([])}}
                  style={{background:'none',border:'1px solid rgba(255,255,255,0.07)',borderRadius:6,padding:'4px 12px',fontSize:12,color:'#555350',cursor:'pointer'}}>Clear all</button>
              )}
            </div>
            <p style={{color:'#888680',fontSize:14,marginBottom:28,lineHeight:1.6}}>Aegis learns your preferences as you use it.</p>
            {memories.length===0 ? (
              <p style={{fontSize:13,color:'#555350',fontStyle:'italic'}}>No memories yet. Run a few tasks first.</p>
            ) : (
              <div style={{display:'flex',flexDirection:'column',gap:8}}>
                {memories.map((m,i)=>(
                  <div key={i} style={{display:'flex',gap:12,padding:'10px 14px',background:'rgba(255,255,255,0.03)',borderRadius:8,border:'1px solid rgba(255,255,255,0.07)'}}>
                    <span style={{fontSize:11,padding:'2px 8px',borderRadius:999,background:'rgba(255,255,255,0.05)',color:'#555350',fontFamily:'var(--font-mono)',whiteSpace:'nowrap'}}>{m.category}</span>
                    <p style={{fontSize:13,color:'#e8e6e0',flex:1,lineHeight:1.5}}>{m.value}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </main>

      {sandboxOpen && risk && (
        <div style={{position:'fixed',inset:0,background:'rgba(0,0,0,0.75)',display:'flex',alignItems:'center',justifyContent:'center',zIndex:1000,padding:'1rem'}}>
          <div style={{background:'#141416',border:'1px solid rgba(255,255,255,0.13)',borderRadius:16,padding:28,maxWidth:520,width:'100%'}}>
            <p style={{fontSize:13,fontFamily:'var(--font-mono)',color:'#888680',textTransform:'uppercase',letterSpacing:'0.1em',marginBottom:20}}>⚠ Action sandbox — review before running</p>
            <div style={{background:'rgba(255,255,255,0.03)',borderRadius:10,padding:'12px 16px',marginBottom:16,border:'1px solid rgba(255,255,255,0.07)'}}>
              <p style={{fontSize:14,color:'#e8e6e0',lineHeight:1.6}}>"{task}"</p>
            </div>
            <p style={{fontSize:13,color:'#888680',marginBottom:20}}>Risk score: <strong style={{color}}>{risk.score}/100 — {risk.risk_level}</strong></p>
            <p style={{fontSize:13,color:'#888680',marginBottom:20,lineHeight:1.6}}>{risk.headline}</p>
            <div style={{display:'flex',gap:10}}>
              <button onClick={executeTask} style={{flex:1,padding:12,borderRadius:10,background:'#c8f060',color:'#0c0c0e',border:'none',cursor:'pointer',fontSize:14,fontWeight:500}}>Approve and run →</button>
              <button onClick={()=>{setSandboxOpen(false);reset()}} style={{padding:'12px 20px',borderRadius:10,background:'transparent',color:'#888680',border:'1px solid rgba(255,255,255,0.13)',cursor:'pointer',fontSize:14}}>Cancel</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
