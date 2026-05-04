import { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { Shield, Menu, X } from 'lucide-react'

export default function Navbar() {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false)
  const location = useLocation()

  const navLinks = [
    { name: 'Home', path: '/' },
    { name: 'Explore', path: '/explore' },
    { name: 'Dashboard', path: '/dashboard' },
    { name: 'History', path: '/history' },
    { name: 'About', path: '/about' },
  ]

  const isActive = (path) => {
    if (path === '/' && location.pathname !== '/') return false
    return location.pathname.startsWith(path)
  }

  const closeMobileMenu = () => {
    setIsMobileMenuOpen(false)
  }

  return (
    <nav className="sticky top-0 z-50 w-full border-b border-slate-200 bg-white/95 backdrop-blur supports-[backdrop-filter]:bg-white/60 shadow-sm">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="flex h-16 items-center justify-between">
          {/* Logo Section */}
          <div className="flex-shrink-0">
            <Link 
              to="/" 
              className="flex items-center gap-2.5 group"
              onClick={closeMobileMenu}
            >
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#059669] text-white transition-transform group-hover:scale-105">
                <Shield className="h-5 w-5" strokeWidth={2.5} />
              </div>
              <span className="font-display text-xl font-bold tracking-tight text-slate-900">
                Vigilance <span className="text-[#059669]">C3MS</span>
              </span>
            </Link>
          </div>

          {/* Desktop Navigation */}
          <div className="hidden md:block">
            <div className="ml-10 flex items-baseline space-x-1">
              {navLinks.map((link) => (
                <Link
                  key={link.name}
                  to={link.path}
                  className={`px-4 py-2 rounded-md text-sm font-medium font-body transition-all duration-200 ${
                    isActive(link.path)
                      ? 'bg-slate-100 text-[#059669]'
                      : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                  }`}
                >
                  {link.name}
                </Link>
              ))}
            </div>
          </div>

          {/* Desktop CTA */}
          <div className="hidden md:flex items-center">
            <Link
              to="/report"
              className="inline-flex items-center justify-center rounded-md bg-[#059669] px-5 py-2.5 text-sm font-medium text-white shadow-sm transition-colors hover:bg-[#047857] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#059669] focus-visible:ring-offset-2 font-body"
            >
              File Report
            </Link>
          </div>

          {/* Mobile menu button */}
          <div className="flex md:hidden">
            <button
              type="button"
              onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
              className="inline-flex items-center justify-center rounded-md p-2 text-slate-500 hover:bg-slate-100 hover:text-slate-900 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-[#059669]"
              aria-controls="mobile-menu"
              aria-expanded={isMobileMenuOpen}
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

      {/* Mobile Menu Dropdown */}
      <div
        className={`md:hidden transition-all duration-300 ease-in-out overflow-hidden ${
          isMobileMenuOpen ? 'max-h-96 border-b border-slate-200 opacity-100' : 'max-h-0 opacity-0'
        }`}
        id="mobile-menu"
      >
        <div className="space-y-1 px-4 pb-4 pt-2 bg-white sm:px-6">
          {navLinks.map((link) => (
            <Link
              key={link.name}
              to={link.path}
              onClick={closeMobileMenu}
              className={`block rounded-md px-3 py-3 text-base font-medium font-body ${
                isActive(link.path)
                  ? 'bg-slate-50 text-[#059669]'
                  : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
              }`}
            >
              {link.name}
            </Link>
          ))}
          <div className="pt-4 pb-2">
            <Link
              to="/report"
              onClick={closeMobileMenu}
              className="flex w-full items-center justify-center rounded-md bg-[#059669] px-4 py-3 text-base font-medium text-white shadow-sm hover:bg-[#047857] font-body"
            >
              File Report
            </Link>
          </div>
        </div>
      </div>
    </nav>
  )
}