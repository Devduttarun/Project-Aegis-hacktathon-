import { useAuth0 } from '@auth0/auth0-react'
import LandingPage from './pages/LandingPage.jsx'
import Dashboard from './pages/Dashboard.jsx'
export default function App() {
  const { isLoading, isAuthenticated } = useAuth0()
  if (isLoading) return <div style={{minHeight:'100vh',display:'flex',alignItems:'center',justifyContent:'center'}}><div style={{width:40,height:40,borderRadius:'50%',border:'2px solid #333',borderTopColor:'#c8f060',animation:'spin 0.8s linear infinite'}}/></div>
  return isAuthenticated ? <Dashboard /> : <LandingPage />
}
