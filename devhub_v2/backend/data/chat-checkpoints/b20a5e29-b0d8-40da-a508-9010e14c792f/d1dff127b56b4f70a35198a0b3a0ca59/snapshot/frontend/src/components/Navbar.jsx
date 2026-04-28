import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth.jsx'
import { Activity, User, LogOut } from 'lucide-react'

export default function Navbar() {
  const { isAuthenticated, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/')
  }

  return (
    <nav className="bg-white shadow-sm border-b border-gray-200 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16 items-center">
          
          {/* Logo and primary nav */}
          <div className="flex items-center flex-1">
            <Link to="/" className="flex-shrink-0 flex items-center gap-2 mr-8">
              <Activity className="h-8 w-8 text-blue-600" />
              <span className="font-bold text-xl text-gray-900 tracking-tight">Omnia</span>
            </Link>
            
            <div className="hidden md:flex space-x-8">
              <Link 
                to="/" 
                className="text-sm font-medium text-gray-600 hover:text-blue-600 transition-colors"
              >
                Home
              </Link>
              <Link 
                to="/doctors" 
                className="text-sm font-medium text-gray-600 hover:text-blue-600 transition-colors"
              >
                Doctors
              </Link>
              <Link 
                to="/pharmacy" 
                className="text-sm font-medium text-gray-600 hover:text-blue-600 transition-colors"
              >
                Pharmacy
              </Link>
            </div>
          </div>

          {/* Secondary nav / Auth */}
          <div className="flex items-center space-x-3 sm:space-x-4">
            {isAuthenticated ? (
              <>
                <Link
                  to="/dashboard"
                  className="inline-flex items-center gap-2 px-3 py-2 sm:px-4 sm:py-2 text-sm font-medium rounded-md text-gray-700 bg-gray-100 hover:bg-gray-200 transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gray-500"
                >
                  <User className="h-4 w-4" />
                  <span className="hidden sm:inline">Dashboard</span>
                </Link>
                <button
                  onClick={handleLogout}
                  className="inline-flex items-center gap-2 px-3 py-2 sm:px-4 sm:py-2 text-sm font-medium rounded-md text-white bg-red-600 hover:bg-red-700 transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500"
                >
                  <LogOut className="h-4 w-4" />
                  <span className="hidden sm:inline">Logout</span>
                </button>
              </>
            ) : (
              <Link
                to="/login"
                className="inline-flex items-center px-5 py-2 sm:px-6 sm:py-2 text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
              >
                Login
              </Link>
            )}
          </div>
          
        </div>
      </div>
      
      {/* Mobile Navigation Links (Visible only on small screens) */}
      <div className="md:hidden border-t border-gray-100 bg-gray-50 px-4 py-3 flex justify-center space-x-6">
        <Link 
          to="/" 
          className="text-sm font-medium text-gray-600 hover:text-blue-600 transition-colors"
        >
          Home
        </Link>
        <Link 
          to="/doctors" 
          className="text-sm font-medium text-gray-600 hover:text-blue-600 transition-colors"
        >
          Doctors
        </Link>
        <Link 
          to="/pharmacy" 
          className="text-sm font-medium text-gray-600 hover:text-blue-600 transition-colors"
        >
          Pharmacy
        </Link>
      </div>
    </nav>
  )
}