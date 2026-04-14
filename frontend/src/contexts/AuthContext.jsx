import React, { createContext, useContext, useState, useEffect } from 'react'
import { api, isAuthenticated, getUser } from '../api.js'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(getUser())
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const handleStorageChange = () => {
      setUser(getUser())
    }
    
    const handleLogout = () => {
      setUser(null)
    }

    window.addEventListener('storage', handleStorageChange)
    window.addEventListener('auth:logout', handleLogout)
    
    setLoading(false)
    
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
    isAuthenticated: !!user,
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
