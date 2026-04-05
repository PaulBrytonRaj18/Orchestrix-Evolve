import React from 'react'
import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom'
import Search from './pages/Search.jsx'
import Dashboard from './pages/Dashboard.jsx'
import SessionCompare from './pages/SessionCompare.jsx'

function App() {
  const location = useLocation()

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <nav style={{
        background: '#1e293b',
        padding: '1rem 2rem',
        display: 'flex',
        alignItems: 'center',
        gap: '2rem',
        borderBottom: '1px solid #334155'
      }}>
        <Link to="/" style={{
          textDecoration: 'none',
          color: '#60a5fa',
          fontSize: '1.5rem',
          fontWeight: 'bold'
        }}>
          Orchestrix
        </Link>
        <div style={{ display: 'flex', gap: '1.5rem' }}>
          <Link 
            to="/" 
            style={{
              textDecoration: 'none',
              color: location.pathname === '/' ? '#60a5fa' : '#94a3b8',
              fontWeight: location.pathname === '/' ? '600' : '400'
            }}
          >
            Search
          </Link>
          <Link 
            to="/dashboard" 
            style={{
              textDecoration: 'none',
              color: location.pathname === '/dashboard' ? '#60a5fa' : '#94a3b8',
              fontWeight: location.pathname === '/dashboard' ? '600' : '400'
            }}
          >
            Dashboard
          </Link>
          <Link 
            to="/compare" 
            style={{
              textDecoration: 'none',
              color: location.pathname === '/compare' ? '#60a5fa' : '#94a3b8',
              fontWeight: location.pathname === '/compare' ? '600' : '400'
            }}
          >
            Compare
          </Link>
        </div>
      </nav>
      <main style={{ flex: 1, padding: '2rem' }}>
        <Routes>
          <Route path="/" element={<Search />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/dashboard/:sessionId" element={<Dashboard />} />
          <Route path="/compare" element={<SessionCompare />} />
        </Routes>
      </main>
    </div>
  )
}

function AppWrapper() {
  return (
    <Router>
      <App />
    </Router>
  )
}

export default AppWrapper
