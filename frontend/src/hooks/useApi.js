import { useAuth0 } from '@auth0/auth0-react'
export function useApi() {
  const { getAccessTokenSilently } = useAuth0()
  async function req(method, path, body) {
    const token = await getAccessTokenSilently()
    const res = await fetch('/api' + path, { method, headers: {'Authorization':`Bearer ${token}`,'Content-Type':'application/json'}, body: body ? JSON.stringify(body) : undefined })
    if (!res.ok) { const e = await res.json().catch(()=>({})); throw {status:res.status,detail:e.detail||e} }
    return res.json()
  }
  async function stream(path, body, onEvent) {
    const token = await getAccessTokenSilently()
    const res = await fetch('/api' + path, { method:'POST', headers:{'Authorization':`Bearer ${token}`,'Content-Type':'application/json'}, body: JSON.stringify(body) })
    if (!res.ok) { const e = await res.json().catch(()=>({})); throw {status:res.status,detail:e.detail||e} }
    const reader = res.body.getReader(); const dec = new TextDecoder(); let buf = ''
    while (true) {
      const {done,value} = await reader.read(); if (done) break
      buf += dec.decode(value,{stream:true})
      const lines = buf.split('\n'); buf = lines.pop()
      for (const line of lines) { if (line.startsWith('data: ')) { const d=line.slice(6); if(d==='[DONE]') return; try{onEvent(JSON.parse(d))}catch{} } }
    }
  }
  return { get:(p)=>req('GET',p), post:(p,b)=>req('POST',p,b), del:(p)=>req('DELETE',p), stream }
}
