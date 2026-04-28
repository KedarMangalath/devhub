import { useState, useEffect, createContext, useContext } from 'react'
import { login as apiLogin } from '../api/endpoints.js'
import { jwtDecode } from 'jwt-decode'

const AuthContext = createContext(null)

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null)
  const [token, setToken] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const initializeAuth = () => {
      const storedToken = localStorage.getItem('token')
      if (storedToken) {
        try {
          const decoded = jwtDecode(storedToken)
          if (decoded.exp * 1000 < Date.now()) {
            localStorage.removeItem('token')
            setUser(null)
            setToken(null)
          } else {
            setToken(storedToken)
            setUser(decoded)
          }
        } catch (error) {
          console.error('Failed to decode token:', error)
          localStorage.removeItem('token')
          setUser(null)
          setToken(null)
        }
      }
      setLoading(false)
    }

    initializeAuth()
  }, [])

  const login = async (email, password) => {
    try {
      const response = await apiLogin(email, password)
      const accessToken = response.access_token || (response.data && response.data.access_token)
      
      if (accessToken) {
        localStorage.setItem('token', accessToken)
        setToken(accessToken)
        
        const decoded = jwtDecode(accessToken)
        setUser(decoded)
        
        return { success: true }
      } else {
        return { success: false, error: 'Invalid response from server' }
      }
    } catch (error) {
      console.error('Login error:', error)
      const errorMessage = error.response?.data?.detail || 'Login failed. Please check your credentials.'
      return { success: false, error: errorMessage }
    }
  }

  const logout = () => {
    localStorage.removeItem('token')
    setToken(null)
    setUser(null)
  }

  const value = {
    user,
    token,
    login,
    logout,
    isAuthenticated: !!user,
    loading
  }

  return (
    <AuthContext.Provider value={value}>
      {!loading && children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}