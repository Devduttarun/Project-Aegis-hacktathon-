import { useAuth0 } from '@auth0/auth0-react'
export default function LandingPage() {
  const { loginWithRedirect } = useAuth0()
  return (
    <div style={{minHeight:'100vh',display:'flex',flexDirection:'column',alignItems:'center',justifyContent:'center',padding:'2rem',position:'relative',overflow:'hidden'}}>
      <div style={{position:'absolute',inset:0,backgroundImage:'linear-gradient(rgba(255,255,255,0.03) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,0.03) 1px,transparent 1px)',backgroundSize:'60px 60px',maskImage:'radial-gradient(ellipse 80% 60% at 50% 50%,black 40%,transparent 100%)'}}/>
      <div style={{position:'relative',textAlign:'center',maxWidth:'640px'}}>
        <div style={{display:'inline-flex',alignItems:'center',gap:'10px',marginBottom:'3rem',padding:'8px 16px',border:'1px solid rgba(255,255,255,0.13)',borderRadius:'999px',fontSize:'13px',color:'#888680',fontFamily:'monospace',letterSpacing:'0.08em'}}>
          <span style={{color:'#c8f060',fontSize:'10px'}}>●</span>
          AUTH0 FOR AI AGENTS — AUTHORIZED TO ACT HACKATHON
        </div>
        <h1 style={{fontFamily:'Georgia,serif',fontSize:'clamp(3rem,8vw,5rem)',lineHeight:'1.05',marginBottom:'1.5rem',letterSpacing:'-0.02em'}}>
          Your AI acts.<br/>
          <span style={{fontStyle:'italic',color:'#c8f060'}}>You stay in control.</span>
        </h1>
        <p style={{fontSize:'1.1rem',color:'#888680',lineHeight:'1.7',maxWidth:'480px',margin:'0 auto 2.5rem'}}>
          Aegis lets your AI read your emails, create Notion pages, and manage your digital life — without ever holding your credentials.
        </p>
        <button onClick={()=>loginWithRedirect()} style={{background:'#c8f060',color:'#0c0c0e',border:'none',borderRadius:'10px',padding:'14px 32px',fontSize:'15px',fontWeight:'500',cursor:'pointer'}}>
          Get started →
        </button>
      </div>
    </div>
  )
}