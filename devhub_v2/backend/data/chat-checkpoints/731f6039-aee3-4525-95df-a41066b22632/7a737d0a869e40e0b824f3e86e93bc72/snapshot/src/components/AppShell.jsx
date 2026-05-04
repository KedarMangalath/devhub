import React, { useState, useEffect } from 'react';
import { NavLink, Link, useLocation, Outlet } from 'react-router-dom';
import {
  Menu,
  X,
  Shield,
  FileText,
  Search,
  LayoutDashboard,
  BarChart3,
  Bell
} from 'lucide-react';
import { currentUser } from '../mockData';
import Footer from './shared/Footer';

export default function AppShell() {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const location = useLocation();

  // Close mobile menu automatically when navigating to a new route
  useEffect(() => {
    setIsMobileMenuOpen(false);
  }, [location.pathname]);

  const navLinks = [
    { name: 'Home', path: '/', icon: Shield },
    { name: 'Track Status', path: '/track', icon: Search },
    { name: 'Officer Portal', path: '/officer', icon: LayoutDashboard },
    { name: 'Director View', path: '/director', icon: BarChart3 },
  ];

  return (
    <div className="min-h-screen flex flex-col bg-[#F8FAFC] font-sans text-[#0F172A] selection:bg-vacb-700/20 selection:text-vacb-700">
      {/* Brand Header & Navigation */}
      <header className="sticky top-0 z-50 w-full border-b border-slate-200 bg-white/90 backdrop-blur-md shadow-sm">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex h-16 items-center justify-between">
            
            {/* Logo & Brand */}
            <Link to="/" className="flex items-center gap-2.5 group focus:outline-none focus:ring-2 focus:ring-vacb-700 focus:ring-offset-2 rounded-lg p-1 -ml-1">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-vacb-700 text-white shadow-sm group-hover:bg-vacb-700/90 transition-colors">
                <Shield className="h-5 w-5" />
              </div>
              <div className="flex flex-col">
                <span className="text-lg font-bold tracking-tight text-slate-900 leading-none">C3MS</span>
                <span className="text-[10px] font-medium text-slate-500 uppercase tracking-wider mt-0.5">Kerala</span>
              </div>
            </Link>

            {/* Desktop Navigation */}
            <nav className="hidden md:flex items-center gap-1 lg:gap-2">
              {navLinks.map((link) => (
                <NavLink
                  key={link.path}
                  to={link.path}
                  className={({ isActive }) =>
                    `flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-all duration-200 ${
                      isActive
                        ? 'bg-vacb-700/10 text-vacb-700'
                        : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                    }`
                  }
                >
                  <link.icon className="h-4 w-4" />
                  {link.name}
                </NavLink>
              ))}
            </nav>

            {/* Desktop Actions & Profile */}
            <div className="hidden md:flex items-center gap-4">
              <button 
                className="relative p-2 text-slate-400 hover:text-slate-600 transition-colors rounded-full hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-vacb-700"
                aria-label="Notifications"
              >
                <Bell className="h-5 w-5" />
                <span className="absolute top-2 right-2 h-2 w-2 rounded-full bg-[#D97706] ring-2 ring-white"></span>
              </button>

              <div className="h-6 w-px bg-slate-200"></div>

              <div className="flex items-center gap-3">
                <div className="flex flex-col items-end">
                  <span className="text-sm font-semibold text-slate-900 leading-none">{currentUser.name}</span>
                  <span className="text-xs text-slate-500 mt-1">{currentUser.role}</span>
                </div>
                <img
                  src={currentUser.avatar}
                  alt={currentUser.name}
                  className="h-9 w-9 rounded-full object-cover border-2 border-slate-100 shadow-sm"
                />
              </div>

              <Link
                to="/file-complaint"
                className="ml-2 inline-flex items-center justify-center gap-2 rounded-lg bg-vacb-700 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-all hover:bg-vacb-700/90 hover:shadow focus:outline-none focus:ring-2 focus:ring-vacb-700 focus:ring-offset-2"
              >
                <FileText className="h-4 w-4" />
                File Complaint
              </Link>
            </div>

            {/* Mobile Menu Toggle */}
            <div className="flex items-center gap-3 md:hidden">
              <button 
                className="relative p-2 text-slate-400 hover:text-slate-600 transition-colors rounded-full hover:bg-slate-100"
                aria-label="Notifications"
              >
                <Bell className="h-5 w-5" />
                <span className="absolute top-2 right-2 h-2 w-2 rounded-full bg-[#D97706] ring-2 ring-white"></span>
              </button>
              <button
                onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
                className="inline-flex items-center justify-center rounded-md p-2 text-slate-500 hover:bg-slate-100 hover:text-slate-700 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-vacb-700"
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

        {/* Mobile Navigation Dropdown */}
        {isMobileMenuOpen && (
          <div className="md:hidden border-t border-slate-200 bg-white shadow-xl absolute w-full left-0">
            <div className="space-y-1 px-4 pb-3 pt-2">
              {navLinks.map((link) => (
                <NavLink
                  key={link.path}
                  to={link.path}
                  className={({ isActive }) =>
                    `flex items-center gap-3 rounded-lg px-3 py-2.5 text-base font-medium transition-colors ${
                      isActive
                        ? 'bg-vacb-700/10 text-vacb-700'
                        : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                    }`
                  }
                >
                  <link.icon className="h-5 w-5" />
                  {link.name}
                </NavLink>
              ))}
            </div>
            <div className="border-t border-slate-100 pb-5 pt-4 bg-slate-50/50">
              <div className="flex items-center gap-3 px-5 mb-5">
                <img
                  src={currentUser.avatar}
                  alt={currentUser.name}
                  className="h-10 w-10 rounded-full object-cover border-2 border-white shadow-sm"
                />
                <div>
                  <div className="text-base font-semibold text-slate-900">{currentUser.name}</div>
                  <div className="text-sm text-slate-500">{currentUser.role}</div>
                </div>
              </div>
              <div className="px-4">
                <Link
                  to="/file-complaint"
                  className="flex w-full items-center justify-center gap-2 rounded-lg bg-vacb-700 px-4 py-3 text-base font-semibold text-white shadow-sm hover:bg-vacb-700/90 transition-colors focus:outline-none focus:ring-2 focus:ring-vacb-700 focus:ring-offset-2"
                >
                  <FileText className="h-5 w-5" />
                  File a Complaint
                </Link>
              </div>
            </div>
          </div>
        )}
      </header>

      {/* Main Content Area */}
      <main className="flex-1 w-full flex flex-col relative">
        <Outlet />
      </main>

      {/* Global Footer */}
      <Footer />
    </div>
  );
}