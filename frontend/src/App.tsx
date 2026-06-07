import React, { Suspense, lazy, useEffect, useState } from 'react'
import { BrowserRouter as Router, Routes, Route, Link, useLocation, Navigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import { ThemeProvider, useTheme } from './contexts/ThemeContext'
import ErrorBoundary from './components/ErrorBoundary'
import { ToastProvider } from './contexts/ToastContext'
import { Sun, Moon, SearchIcon, LayoutDashboard, Map, GitCompare, Mail, LogOut, Menu, X } from 'lucide-react'
import './app.css'

const Search = lazy(() => import('./pages/Search'))
const Dashboard = lazy(() => import('./pages/Dashboard'))
const SessionCompare = lazy(() => import('./pages/SessionCompare'))
const Roadmap = lazy(() => import('./pages/Roadmap'))
const DigestManagement = lazy(() => import('./components/DigestManagement'))
const Login = lazy(() => import('./pages/Login'))
const Register = lazy(() => import('./pages/Register'))

function ProtectedRoute({ children }: { children: React.ReactNode }) {
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
  
  return <>{children}</>
}

function GuestRoute({ children }: { children: React.ReactNode }) {
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
  
  return <>{children}</>
}

interface NavItem {
  path: string;
  label: string;
  icon: React.ElementType;
}

const navItems: NavItem[] = [
  { path: '/', label: 'Search', icon: SearchIcon },
  { path: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/roadmap', label: 'Roadmap', icon: Map },
  { path: '/compare', label: 'Compare', icon: GitCompare },
  { path: '/digests', label: 'Digests', icon: Mail }
]

function ScrollToTop() {
  const { pathname } = useLocation()
  useEffect(() => { window.scrollTo(0, 0) }, [pathname])
  return null
}

function NavContent() {
  const location = useLocation()
  const { user, signOut, isAuthenticated } = useAuth()
  const { theme, toggleTheme } = useTheme()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  useEffect(() => {
    setMobileMenuOpen(false)
  }, [location.pathname])

  const isActiveRoute = (path: string): boolean => {
    if (path === '/') return location.pathname === '/'
    return location.pathname.startsWith(path)
  }

  return (
    <>
      <a href="#main-content" className="skip-to-content">
        Skip to content
      </a>

      <motion.nav 
        className="app-nav"
        initial={{ y: -20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ duration: 0.3, ease: 'easeOut' }}
        role="navigation"
        aria-label="Main navigation"
      >
        <div className="nav-content">
          <Link to="/" className="nav-logo" aria-label="Orchestrix Home">
            <div className="nav-logo-icon" aria-hidden="true">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="11" cy="11" r="8"/>
                <path d="m21 21-4.3-4.3"/>
              </svg>
            </div>
            <span className="nav-logo-text">Orchestrix</span>
          </Link>

          <div className="nav-links" role="menubar" aria-label="Navigation links">
            {navItems.map((item) => {
              const Icon = item.icon
              return (
                <Link 
                  key={item.path}
                  to={item.path}
                  className={`nav-link ${isActiveRoute(item.path) ? 'active' : ''}`}
                  role="menuitem"
                >
                  <Icon size={16} strokeWidth={1.75} aria-hidden="true" />
                  <span>{item.label}</span>
                </Link>
              )
            })}
          </div>

          <div className="nav-actions">
            <button 
              className="nav-icon-btn nav-icon-btn-mobile"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              aria-label={mobileMenuOpen ? 'Close menu' : 'Open menu'}
            >
              {mobileMenuOpen ? <X size={20} aria-hidden="true" /> : <Menu size={20} aria-hidden="true" />}
            </button>
            <button 
              className="nav-icon-btn nav-icon-btn-desktop" 
              onClick={toggleTheme}
              aria-label={theme === 'light' ? 'Switch to dark mode' : 'Switch to light mode'}
            >
              {theme === 'light' ? <Moon size={18} strokeWidth={1.75} aria-hidden="true" /> : <Sun size={18} strokeWidth={1.75} aria-hidden="true" />}
            </button>
            
            {isAuthenticated ? (
              <div className="user-menu" onClick={signOut} role="button" tabIndex={0} onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') signOut(); }} aria-label="Sign out">
                <div className="user-avatar" aria-hidden="true">
                  {user?.username?.[0]?.toUpperCase() || user?.email?.[0]?.toUpperCase() || 'U'}
                </div>
                <span className="user-name">{user?.username || user?.email?.split('@')[0]}</span>
                <LogOut size={14} strokeWidth={1.75} aria-hidden="true" style={{ color: 'var(--text-tertiary)' }} />
              </div>
            ) : (
              <Link to="/login" className="btn btn-primary">
                Sign in
              </Link>
            )}
          </div>
        </div>

        {/* Mobile Menu */}
        <AnimatePresence>
          {mobileMenuOpen && (
            <motion.div
              className="nav-mobile-menu"
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
            >
              <div className="nav-mobile-links">
                {navItems.map((item) => {
                  const Icon = item.icon
                  return (
                    <Link
                      key={item.path}
                      to={item.path}
                      className={`nav-link ${isActiveRoute(item.path) ? 'active' : ''}`}
                    >
                      <Icon size={16} strokeWidth={1.75} aria-hidden="true" />
                      <span>{item.label}</span>
                    </Link>
                  )
                })}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.nav>

      <main className="app-main" id="main-content">
        <AnimatePresence mode="wait">
          <motion.div
            key={location.pathname}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.2 }}
            className="page-container"
          >
            <Suspense fallback={
              <div className="loading-screen" style={{ minHeight: '40vh' }}>
                <div className="loading-spinner" />
              </div>
            }>
              <Routes>
                <Route path="/login" element={<GuestRoute><Login /></GuestRoute>} />
                <Route path="/register" element={<GuestRoute><Register /></GuestRoute>} />
                <Route path="/" element={<ProtectedRoute><Search /></ProtectedRoute>} />
                <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
                <Route path="/dashboard/:sessionId" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
                <Route path="/roadmap" element={<ProtectedRoute><Roadmap /></ProtectedRoute>} />
                <Route path="/compare" element={<ProtectedRoute><SessionCompare /></ProtectedRoute>} />
                <Route path="/digests" element={<ProtectedRoute><DigestManagement /></ProtectedRoute>} />
                <Route path="*" element={
                  <div className="empty-state" style={{ paddingTop: 'var(--space-16)' }}>
                    <div className="empty-icon">
                      <SearchIcon size={48} strokeWidth={1} />
                    </div>
                    <h2 className="empty-title">Page not found</h2>
                    <p className="empty-description">
                      The page you're looking for doesn't exist or has been moved.
                    </p>
                    <Link to="/" className="btn btn-primary" style={{ marginTop: 'var(--space-6)' }}>
                      Go Home
                    </Link>
                  </div>
                } />
              </Routes>
            </Suspense>
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
            <ToastProvider>
              <Router>
                <ScrollToTop />
                <NavContent />
              </Router>
            </ToastProvider>
          </ThemeProvider>
        </AuthProvider>
      </div>
    </ErrorBoundary>
  )
}

export default App
