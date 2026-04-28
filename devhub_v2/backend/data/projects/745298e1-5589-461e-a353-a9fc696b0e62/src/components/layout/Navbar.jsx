import { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { Activity, User, Menu, X } from 'lucide-react'
import { patient_profile } from '../../mockData'
import Button from '../ui/Button'

export default function Navbar() {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false)
  const location = useLocation()

  const navLinks = [
    { name: 'Dashboard', path: '/dashboard' },
    { name: 'Find Doctors', path: '/doctors' },
    { name: 'History', path: '/history' },
  ]

  const isActive = (path) => {
    if (path === '/dashboard' && location.pathname === '/') return true
    return location.pathname.includes(path)
  }

  return (
    <nav className="bg-white border-b border-slate-200 sticky top-0 z-50 shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16">
          {/* Left side: Logo and Desktop Nav */}
          <div className="flex items-center gap-8">
            <Link to="/" className="flex items-center gap-2 group">
              <div className="bg-sky-600 p-1.5 rounded-xl shadow-sm group-hover:bg-sky-700 transition-colors">
                <Activity className="h-5 w-5 text-white" strokeWidth={2.5} />
              </div>
              <span className="font-display font-bold text-xl text-slate-900 tracking-tight">
                Omnia
              </span>
            </Link>

            <div className="hidden md:flex md:items-center md:space-x-1">
              {navLinks.map((link) => (
                <Link
                  key={link.name}
                  to={link.path}
                  className={`px-3 py-2 rounded-lg text-sm font-medium transition-all duration-200 ${
                    isActive(link.path)
                      ? 'bg-sky-50 text-sky-700'
                      : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                  }`}
                >
                  {link.name}
                </Link>
              ))}
            </div>
          </div>

          {/* Right side: Actions and Profile */}
          <div className="hidden md:flex items-center gap-6">
            <Link to="/booking">
              <Button variant="primary" size="sm">
                Book Consultation
              </Button>
            </Link>

            <div className="flex items-center gap-3 border-l border-slate-200 pl-6">
              <div className="text-right">
                <p className="text-sm font-semibold text-slate-900 leading-tight">
                  {patient_profile.name}
                </p>
                <div className="flex items-center justify-end gap-1 mt-0.5">
                  <span className="flex h-2 w-2 rounded-full bg-emerald-500"></span>
                  <p className="text-xs font-medium text-emerald-600">
                    Score: {patient_profile.health_score}
                  </p>
                </div>
              </div>
              
              {patient_profile.avatar ? (
                <img 
                  src={patient_profile.avatar} 
                  alt={patient_profile.name} 
                  className="h-10 w-10 rounded-full object-cover border-2 border-white shadow-sm ring-1 ring-slate-200" 
                />
              ) : (
                <div className="h-10 w-10 rounded-full bg-slate-100 flex items-center justify-center border border-slate-200 shadow-sm">
                  <User className="h-5 w-5 text-slate-500" />
                </div>
              )}
            </div>
          </div>

          {/* Mobile menu button */}
          <div className="flex items-center md:hidden gap-4">
            <Link to="/booking">
              <Button variant="primary" size="sm" className="px-3 py-1.5 text-xs">
                Book
              </Button>
            </Link>
            <button
              onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
              className="text-slate-500 hover:text-slate-900 hover:bg-slate-50 p-2 rounded-lg transition-colors focus:outline-none"
              aria-expanded="false"
            >
              <span className="sr-only">Open main menu</span>
              {isMobileMenuOpen ? (
                <X className="block h-6 w-6" aria-hidden="true" />
              ) : (
                <Menu className="block h-6 w-6" aria-hidden="true" />
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Mobile Menu Panel */}
      {isMobileMenuOpen && (
        <div className="md:hidden border-t border-slate-200 bg-white shadow-lg absolute w-full">
          <div className="px-4 pt-2 pb-4 space-y-1">
            {navLinks.map((link) => (
              <Link
                key={link.name}
                to={link.path}
                onClick={() => setIsMobileMenuOpen(false)}
                className={`block px-3 py-2.5 rounded-lg text-base font-medium transition-colors ${
                  isActive(link.path)
                    ? 'bg-sky-50 text-sky-700'
                    : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                }`}
              >
                {link.name}
              </Link>
            ))}
          </div>
          
          <div className="pt-4 pb-5 border-t border-slate-100 bg-slate-50/50">
            <div className="flex items-center px-5 gap-4">
              {patient_profile.avatar ? (
                <img 
                  src={patient_profile.avatar} 
                  alt={patient_profile.name} 
                  className="h-12 w-12 rounded-full object-cover border-2 border-white shadow-sm ring-1 ring-slate-200" 
                />
              ) : (
                <div className="h-12 w-12 rounded-full bg-white flex items-center justify-center border border-slate-200 shadow-sm">
                  <User className="h-6 w-6 text-slate-500" />
                </div>
              )}
              <div>
                <div className="text-base font-semibold text-slate-900">
                  {patient_profile.name}
                </div>
                <div className="flex items-center gap-1.5 mt-0.5">
                  <span className="flex h-2 w-2 rounded-full bg-emerald-500"></span>
                  <div className="text-sm font-medium text-emerald-600">
                    Health Score: {patient_profile.health_score}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </nav>
  )
}