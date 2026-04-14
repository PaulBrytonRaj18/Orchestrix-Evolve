import { React, useEffect } from 'react'
import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import Search from './pages/Search.jsx'
import Dashboard from './pages/Dashboard.jsx'
import SessionCompare from './pages/SessionCompare.jsx'
import Roadmap from './pages/Roadmap.jsx'
import DigestManagement from './components/DigestManagement.jsx'
import './app.css'

const navItems = [
  { path: '/', label: 'Search', icon: '🔍' },
  { path: '/dashboard', label: 'Dashboard', icon: '📊' },
  { path: '/roadmap', label: 'Roadmap', icon: '🗺️' },
  { path: '/compare', label: 'Compare', icon: '⚖️' },
  { path: '/digests', label: 'Digests', icon: '📬' }
]

function App() {
  const location = useLocation()

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
    <div className="app-container">
      {/* Background effects */}
      <div className="app-bg-gradient" />
      <motion.div 
        className="app-spotlight"
        animate={{
          left: 'var(--mouse-x)',
          top: 'var(--mouse-y)'
        }}
        transition={{ type: "spring", damping: 30, stiffness: 200 }}
      />
      
      {/* Floating particles */}
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

      {/* Navigation */}
      <motion.nav 
        className="app-nav"
        initial={{ y: -100, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ type: "spring", stiffness: 100, damping: 20 }}
      >
        <div className="nav-glow" />
        <div className="nav-content">
          {/* Logo */}
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

          {/* Nav Links */}
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

          {/* Right section - could add user menu, settings, etc */}
          <div className="nav-actions">
            <motion.button 
              className="nav-action-btn"
              whileHover={{ scale: 1.1 }}
              whileTap={{ scale: 0.95 }}
            >
              <span>⚙️</span>
            </motion.button>
          </div>
        </div>
        
        {/* Animated bottom border */}
        <motion.div 
          className="nav-border"
          initial={{ scaleX: 0 }}
          animate={{ scaleX: 1 }}
          transition={{ delay: 0.3, duration: 0.8 }}
        />
      </motion.nav>

      {/* Main Content */}
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
              <Route path="/" element={<Search />} />
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/dashboard/:sessionId" element={<Dashboard />} />
              <Route path="/roadmap" element={<Roadmap />} />
              <Route path="/compare" element={<SessionCompare />} />
              <Route path="/digests" element={<DigestManagement />} />
            </Routes>
          </motion.div>
        </AnimatePresence>
      </main>

      {/* Footer */}
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
          <span className="footer-version">v1.0.0</span>
        </div>
      </motion.footer>
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
