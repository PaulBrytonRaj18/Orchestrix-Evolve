import { React, useEffect } from 'react'
import { BrowserRouter as Router, Routes, Route, Link, useLocation, Navigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { AuthProvider, useAuth } from './contexts/AuthContext.jsx'
import Search from './pages/Search.jsx'
import Dashboard from './pages/Dashboard.jsx'
import SessionCompare from './pages/SessionCompare.jsx'
import Roadmap from './pages/Roadmap.jsx'
import DigestManagement from './components/DigestManagement.jsx'
import Login from './pages/Login.jsx'
import Register from './pages/Register.jsx'
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
  { path: '/', label: 'Search', icon: '🔍' },
  { path: '/dashboard', label: 'Dashboard', icon: '📊' },
  { path: '/roadmap', label: 'Roadmap', icon: '🗺️' },
  { path: '/compare', label: 'Compare', icon: '⚖️' },
  { path: '/digests', label: 'Digests', icon: '📬' }
]

function NavContent() {
  const location = useLocation()
  const { user, logout, isAuthenticated } = useAuth()

  useEffect(() => {
    const handleMouseMove = (e) => {
      document.body.style.setProperty('--mouse-x', e.clientX + 'px')
      document.body.style.setProperty('--mouse-y', e.clientY + 'px')
    }

    window.addEventListener("mousemove", handleMouseMove)
    return () => window.removeEventListener("mousemove", handleMouseMove)
  }, [])

  const isActiveRoute = (path) => {
    if (path === '/') return location.pathname === '/'
    return location.pathname.startsWith(path)
  }

  return (
    <>
      <div className="app-bg-gradient" />
      <motion.div 
        className="app-spotlight"
        animate={{
          left: 'var(--mouse-x)',
          top: 'var(--mouse-y)'
        }}
        transition={{ type: "spring", damping: 30, stiffness: 200 }}
      />
      
      <div className="app-particles">
        {[...Array(20)].map((_, i) => (
          <motion.div
            key={i}
            className="app-particle"
            animate={{
              y: [0, -30, 0],
              opacity: [0.1, 0.5, 0.1],
            }}
            transition={{
              duration: 3 + Math.random() * 2,
              repeat: Infinity,
              delay: Math.random() * 2,
              ease: "easeInOut"
            }}
            style={{
              left: `${Math.random() * 100}%`,
              top: `${Math.random() * 100}%`
            }}
          />
        ))}
      </div>

      <motion.nav 
        className="app-nav"
        initial={{ y: -100, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ type: "spring", stiffness: 100, damping: 20 }}
      >
        <div className="nav-glow" />
        <div className="nav-content">
          <Link to="/" className="nav-logo">
            <motion.div 
              className="logo-icon"
              animate={{ 
                rotate: [0, 5, -5, 0],
              }}
              transition={{ 
                duration: 4, 
                repeat: Infinity, 
                ease: "easeInOut" 
              }}
            >
              🔬
            </motion.div>
            <motion.span 
              className="logo-text"
              whileHover={{ scale: 1.05 }}
            >
              Orchestrix
            </motion.span>
            <motion.div 
              className="logo-badge"
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ delay: 0.5, type: "spring" }}
            >
              RESEARCH
            </motion.div>
          </Link>

          <div className="nav-links">
            {navItems.map((item, index) => (
              <motion.div
                key={item.path}
                initial={{ opacity: 0, y: -20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 * index }}
              >
                <Link 
                  to={item.path}
                  className={`nav-link ${isActiveRoute(item.path) ? 'active' : ''}`}
                >
                  <motion.div
                    className="nav-link-content"
                    whileHover={{ scale: 1.05, y: -2 }}
                    whileTap={{ scale: 0.98 }}
                  >
                    <span className="nav-icon">{item.icon}</span>
                    <span className="nav-label">{item.label}</span>
                    {isActiveRoute(item.path) && (
                      <motion.div
                        className="nav-active-indicator"
                        layoutId="navIndicator"
                        transition={{ type: "spring", stiffness: 500, damping: 30 }}
                      />
                    )}
                  </motion.div>
                </Link>
              </motion.div>
            ))}
          </div>

          <div className="nav-actions">
            {isAuthenticated ? (
              <div className="user-menu">
                <span className="user-name">{user?.username || user?.email}</span>
                <motion.button 
                  className="nav-action-btn logout-btn"
                  onClick={logout}
                  whileHover={{ scale: 1.1 }}
                  whileTap={{ scale: 0.95 }}
                >
                  <span>🚪</span>
                </motion.button>
              </div>
            ) : (
              <Link to="/login" className="nav-login-btn">
                Sign In
              </Link>
            )}
          </div>
        </div>
        
        <motion.div 
          className="nav-border"
          initial={{ scaleX: 0 }}
          animate={{ scaleX: 1 }}
          transition={{ delay: 0.3, duration: 0.8 }}
        />
      </motion.nav>

      <main className="app-main">
        <AnimatePresence mode="wait">
          <motion.div
            key={location.pathname}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            transition={{ duration: 0.3 }}
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

      <motion.footer 
        className="app-footer"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.5 }}
      >
        <div className="footer-content">
          <div className="footer-glow" />
          <span className="footer-text">
            Orchestrix Research Platform
          </span>
          <span className="footer-divider">•</span>
          <span className="footer-version">v2.0.0</span>
        </div>
      </motion.footer>
    </>
  )
}

function App() {
  return (
    <div className="app-container">
      <AuthProvider>
        <Router>
          <NavContent />
        </Router>
      </AuthProvider>
    </div>
  )
}

export default App
