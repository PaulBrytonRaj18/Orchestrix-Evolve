import { React, useEffect } from 'react'
import { BrowserRouter as Router, Routes, Route, Link, useLocation, Navigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { AuthProvider, useAuth } from './contexts/AuthContext.jsx'
import { ThemeProvider, useTheme } from './contexts/ThemeContext.jsx'
import ErrorBoundary from './components/ErrorBoundary.jsx'
import Search from './pages/Search.jsx'
import Dashboard from './pages/Dashboard.jsx'
import SessionCompare from './pages/SessionCompare.jsx'
import Roadmap from './pages/Roadmap.jsx'
import DigestManagement from './components/DigestManagement.jsx'
import Login from './pages/Login.jsx'
import Register from './pages/Register.jsx'
import { Sun, Moon, SearchIcon, LayoutDashboard, Map, GitCompare, Mail, LogOut, User } from 'lucide-react'
import './app.css'

function ProtectedRoute({ children }) {
  const { isAuthenticated, loading } = useAuth()
  
  if (loading) {
    return (
      <div className="loading-screen">
        <div className="loading-spinner" />
      </div>
    )
  }
  
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }
  
  return children
}

function GuestRoute({ children }) {
  const { isAuthenticated, loading } = useAuth()
  
  if (loading) {
    return (
      <div className="loading-screen">
        <div className="loading-spinner" />
      </div>
    )
  }
  
  if (isAuthenticated) {
    return <Navigate to="/" replace />
  }
  
  return children
}

const navItems = [
  { path: '/', label: 'Search', icon: SearchIcon },
  { path: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/roadmap', label: 'Roadmap', icon: Map },
  { path: '/compare', label: 'Compare', icon: GitCompare },
  { path: '/digests', label: 'Digests', icon: Mail }
]

function NavContent() {
  const location = useLocation()
  const { user, logout, isAuthenticated } = useAuth()
  const { theme, toggleTheme } = useTheme()

  const isActiveRoute = (path) => {
    if (path === '/') return location.pathname === '/'
    return location.pathname.startsWith(path)
  }

  return (
    <>
      <motion.nav 
        className="app-nav"
        initial={{ y: -20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ duration: 0.3, ease: 'easeOut' }}
      >
        <div className="nav-content">
          <Link to="/" className="nav-logo">
            <div className="nav-logo-icon">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="11" cy="11" r="8"/>
                <path d="m21 21-4.3-4.3"/>
              </svg>
            </div>
            <span className="nav-logo-text">Orchestrix</span>
          </Link>

          <div className="nav-links">
            {navItems.map((item) => {
              const Icon = item.icon
              return (
                <Link 
                  key={item.path}
                  to={item.path}
                  className={`nav-link ${isActiveRoute(item.path) ? 'active' : ''}`}
                >
                  <Icon size={16} strokeWidth={1.75} />
                  <span>{item.label}</span>
                </Link>
              )
            })}
          </div>

          <div className="nav-actions">
            <button 
              className="nav-icon-btn" 
              onClick={toggleTheme}
              title={theme === 'light' ? 'Switch to dark mode' : 'Switch to light mode'}
            >
              {theme === 'light' ? <Moon size={18} strokeWidth={1.75} /> : <Sun size={18} strokeWidth={1.75} />}
            </button>
            
            {isAuthenticated ? (
              <div className="user-menu" onClick={logout}>
                <div className="user-avatar">
                  {user?.username?.[0]?.toUpperCase() || user?.email?.[0]?.toUpperCase() || 'U'}
                </div>
                <span className="user-name">{user?.username || user?.email?.split('@')[0]}</span>
                <LogOut size={14} strokeWidth={1.75} style={{ color: 'var(--text-tertiary)' }} />
              </div>
            ) : (
              <Link to="/login" className="btn btn-primary">
                Sign in
              </Link>
            )}
          </div>
        </div>
      </motion.nav>

      <main className="app-main">
        <AnimatePresence mode="wait">
          <motion.div
            key={location.pathname}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.2 }}
            className="page-container"
          >
            <Routes>
              <Route path="/login" element={<GuestRoute><Login /></GuestRoute>} />
              <Route path="/register" element={<GuestRoute><Register /></GuestRoute>} />
              <Route path="/" element={<ProtectedRoute><Search /></ProtectedRoute>} />
              <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
              <Route path="/dashboard/:sessionId" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
              <Route path="/roadmap" element={<ProtectedRoute><Roadmap /></ProtectedRoute>} />
              <Route path="/compare" element={<ProtectedRoute><SessionCompare /></ProtectedRoute>} />
              <Route path="/digests" element={<ProtectedRoute><DigestManagement /></ProtectedRoute>} />
            </Routes>
          </motion.div>
        </AnimatePresence>
      </main>

      <footer className="app-footer">
        <div className="footer-content">
          Orchestrix Research Platform
        </div>
      </footer>
    </>
  )
}

function App() {
  return (
    <ErrorBoundary>
      <div className="app-container">
        <AuthProvider>
          <ThemeProvider>
            <Router>
              <NavContent />
            </Router>
          </ThemeProvider>
        </AuthProvider>
      </div>
    </ErrorBoundary>
  )
}

export default App
