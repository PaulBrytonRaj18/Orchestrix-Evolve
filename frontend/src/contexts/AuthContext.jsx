import React, { createContext, useContext, useState, useEffect } from 'react'
import { api, isAuthenticated as checkToken, getUser } from '../api.js'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const initAuth = () => {
      const storedUser = getUser()
      const hasToken = checkToken()
      
      if (storedUser && hasToken) {
        setUser(storedUser)
      }
      setLoading(false)
    }
    
    initAuth()
    
    const handleStorageChange = () => {
      initAuth()
    }
    
    const handleLogout = () => {
      setUser(null)
    }

    window.addEventListener('storage', handleStorageChange)
    window.addEventListener('auth:logout', handleLogout)
    
    return () => {
      window.removeEventListener('storage', handleStorageChange)
      window.removeEventListener('auth:logout', handleLogout)
    }
  }, [])

  const login = async (email, password) => {
    const data = await api.login(email, password)
    setUser(data.user)
    return data
  }

  const register = async (email, username, password, confirmPassword) => {
    const data = await api.register(email, username, password, confirmPassword)
    setUser(data.user)
    return data
  }

  const logout = () => {
    api.logout()
    setUser(null)
  }

  const value = {
    user,
    loading,
    isAuthenticated: checkToken(),
    login,
    register,
    logout
  }

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
