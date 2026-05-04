import React, { useState, useEffect, useRef } from 'react';
import { NavLink, Link, useLocation } from 'react-router-dom';
import { 
  Shield, 
  Menu, 
  X, 
  User, 
  Settings, 
  LogOut, 
  ChevronDown, 
  Mail, 
  ArrowRight, 
  Twitter, 
  Facebook, 
  Linkedin, 
  Github,
  Bell
} from 'lucide-react';
import { userProfile } from '../mockData';

const NAV_LINKS = [
  { name: 'Home', path: '/' },
  { name: 'Explore', path: '/explore' },
  { name: 'Dashboard', path: '/dashboard' },
  { name: 'About', path: '/about' },
];

const FOOTER_LINKS = {
  product: [
    { name: 'Features', path: '/#features' },
    { name: 'Security', path: '/about#security' },
    { name: 'Blockchain Verification', path: '/explore' },
    { name: 'Predictive AI', path: '/dashboard' },
  ],
  company: [
    { name: 'About Us', path: '/about' },
    { name: 'Careers', path: '#' },
    { name: 'Press', path: '#' },
    { name: 'Contact', path: '/about#contact' },
  ],
  legal: [
    { name: 'Privacy Policy', path: '#' },
    { name: 'Terms of Service', path: '#' },
    { name: 'Whistleblower Protection', path: '#' },
    { name: 'Cookie Policy', path: '#' },
  ],
};

export default function AppShell({ children }) {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [isProfileDropdownOpen, setIsProfileDropdownOpen] = useState(false);
  const [isLoggedIn, setIsLoggedIn] = useState(true); // Default to true to show rich UI
  const location = useLocation();
  const dropdownRef = useRef(null);

  // Close mobile menu and dropdowns on route change
  useEffect(() => {
    setIsMobileMenuOpen(false);
    setIsProfileDropdownOpen(false);
  }, [location.pathname]);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsProfileDropdownOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Prevent body scroll when mobile menu is open
  useEffect(() => {
    if (isMobileMenuOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = 'unset';
    }
    return () => {
      document.body.style.overflow = 'unset';
    };
  }, [isMobileMenuOpen]);

  const handleNewsletterSubmit = (e) => {
    e.preventDefault();
    // Mock submission
    alert('Subscribed to newsletter!');
    e.target.reset();
  };

  return (
    <div className="min-h-screen flex flex-col bg-[#F8FAFC] font-body text-[#0F172A]">
      {/* Sticky Header */}
      <header className="sticky top-0 z-40 w-full border-b border-slate-200 bg-white/90 backdrop-blur-md shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            
            {/* Logo */}
            <div className="flex-shrink-0 flex items-center">
              <Link to="/" className="flex items-center gap-2 group">
                <div className="bg-[#059669] p-2 rounded-lg group-hover:bg-[#047857] transition-colors">
                  <Shield className="h-6 w-6 text-white" />
                </div>
                <span className="font-display font-bold text-xl tracking-tight text-slate-900">
                  Vigilance <span className="text-[#059669]">C3MS</span>
                </span>
              </Link>
            </div>

            {/* Desktop Navigation */}
            <nav className="hidden md:flex space-x-8">
              {NAV_LINKS.map((link) => (
                <NavLink
                  key={link.name}
                  to={link.path}
                  className={({ isActive }) =>
                    `inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium transition-colors ${
                      isActive
                        ? 'border-[#059669] text-[#059669]'
                        : 'border-transparent text-slate-600 hover:text-slate-900 hover:border-slate-300'
                    }`
                  }
                >
                  {link.name}
                </NavLink>
              ))}
            </nav>

            {/* Desktop Auth / Profile */}
            <div className="hidden md:flex items-center space-x-4">
              {isLoggedIn ? (
                <div className="flex items-center gap-4">
                  <button className="p-2 text-slate-400 hover:text-slate-600 relative rounded-full hover:bg-slate-100 transition-colors">
                    <Bell className="h-5 w-5" />
                    {userProfile.stats.activeAlerts > 0 && (
                      <span className="absolute top-1.5 right-1.5 block h-2 w-2 rounded-full bg-red-500 ring-2 ring-white" />
                    )}
                  </button>
                  
                  <div className="relative" ref={dropdownRef}>
                    <button
                      onClick={() => setIsProfileDropdownOpen(!isProfileDropdownOpen)}
                      className="flex items-center gap-2 p-1 pr-2 rounded-full border border-slate-200 hover:border-slate-300 bg-white transition-all focus:outline-none focus:ring-2 focus:ring-[#059669] focus:ring-offset-2"
                    >
                      <img
                        className="h-8 w-8 rounded-full object-cover bg-slate-100"
                        src={userProfile.avatar}
                        alt={userProfile.name}
                      />
                      <span className="text-sm font-medium text-slate-700 max-w-[100px] truncate">
                        {userProfile.name.split(' ')[1] || userProfile.name}
                      </span>
                      <ChevronDown className={`h-4 w-4 text-slate-400 transition-transform duration-200 ${isProfileDropdownOpen ? 'rotate-180' : ''}`} />
                    </button>

                    {/* Profile Dropdown */}
                    {isProfileDropdownOpen && (
                      <div className="absolute right-0 mt-2 w-56 rounded-xl bg-white shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none overflow-hidden animate-in fade-in slide-in-from-top-2 duration-200">
                        <div className="px-4 py-3 border-b border-slate-100 bg-slate-50/50">
                          <p className="text-sm font-medium text-slate-900 truncate">{userProfile.name}</p>
                          <p className="text-xs text-slate-500 truncate">{userProfile.email}</p>
                        </div>
                        <div className="py-1">
                          <Link to="/dashboard" className="group flex items-center px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 hover:text-[#059669]">
                            <User className="mr-3 h-4 w-4 text-slate-400 group-hover:text-[#059669]" />
                            My Profile
                          </Link>
                          <Link to="/settings" className="group flex items-center px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 hover:text-[#059669]">
                            <Settings className="mr-3 h-4 w-4 text-slate-400 group-hover:text-[#059669]" />
                            Settings
                          </Link>
                        </div>
                        <div className="py-1 border-t border-slate-100">
                          <button
                            onClick={() => setIsLoggedIn(false)}
                            className="group flex w-full items-center px-4 py-2 text-sm text-red-600 hover:bg-red-50"
                          >
                            <LogOut className="mr-3 h-4 w-4 text-red-500" />
                            Sign out
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                <div className="flex items-center space-x-3">
                  <Link
                    to="/login"
                    className="text-sm font-medium text-slate-600 hover:text-slate-900 px-3 py-2 rounded-md transition-colors"
                  >
                    Log in
                  </Link>
                  <Link
                    to="/register"
                    className="inline-flex items-center justify-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-[#059669] hover:bg-[#047857] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[#059669] transition-colors"
                  >
                    Report Now
                  </Link>
                </div>
              )}
            </div>

            {/* Mobile menu button */}
            <div className="flex items-center md:hidden">
              <button
                onClick={() => setIsMobileMenuOpen(true)}
                className="inline-flex items-center justify-center p-2 rounded-md text-slate-400 hover:text-slate-500 hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-[#059669]"
              >
                <span className="sr-only">Open main menu</span>
                <Menu className="block h-6 w-6" aria-hidden="true" />
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Mobile Menu Slide-out */}
      <div className={`fixed inset-0 z-50 md:hidden ${isMobileMenuOpen ? '' : 'pointer-events-none'}`}>
        {/* Overlay */}
        <div 
          className={`fixed inset-0 bg-slate-900/80 backdrop-blur-sm transition-opacity duration-300 ease-in-out ${isMobileMenuOpen ? 'opacity-100' : 'opacity-0'}`}
          onClick={() => setIsMobileMenuOpen(false)}
        />
        
        {/* Panel */}
        <div className={`fixed inset-y-0 right-0 w-full max-w-sm bg-white shadow-2xl transform transition-transform duration-300 ease-in-out flex flex-col ${isMobileMenuOpen ? 'translate-x-0' : 'translate-x-full'}`}>
          <div className="flex items-center justify-between px-4 pt-5 pb-4 border-b border-slate-100">
            <div className="flex items-center gap-2">
              <div className="bg-[#059669] p-1.5 rounded-md">
                <Shield className="h-5 w-5 text-white" />
              </div>
              <span className="font-display font-bold text-lg text-slate-900">C3MS Menu</span>
            </div>
            <button
              onClick={() => setIsMobileMenuOpen(false)}
              className="rounded-md p-2 text-slate-400 hover:text-slate-500 hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-[#059669]"
            >
              <span className="sr-only">Close menu</span>
              <X className="h-6 w-6" aria-hidden="true" />
            </button>
          </div>
          
          <div className="flex-1 h-0 overflow-y-auto">
            <nav className="px-2 py-4 space-y-1">
              {NAV_LINKS.map((link) => (
                <NavLink
                  key={link.name}
                  to={link.path}
                  className={({ isActive }) =>
                    `block px-3 py-4 rounded-md text-base font-medium transition-colors ${
                      isActive
                        ? 'bg-emerald-50 text-[#059669]'
                        : 'text-slate-900 hover:bg-slate-50 hover:text-slate-900'
                    }`
                  }
                >
                  {link.name}
                </NavLink>
              ))}
            </nav>
          </div>

          {/* Mobile Auth Section */}
          <div className="p-4 border-t border-slate-100 bg-slate-50">
            {isLoggedIn ? (
              <div className="space-y-4">
                <div className="flex items-center px-2">
                  <img
                    className="h-10 w-10 rounded-full object-cover border border-slate-200"
                    src={userProfile.avatar}
                    alt=""
                  />
                  <div className="ml-3">
                    <div className="text-base font-medium text-slate-800">{userProfile.name}</div>
                    <div className="text-sm font-medium text-slate-500">{userProfile.role}</div>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <Link to="/dashboard" className="flex items-center justify-center px-4 py-2 border border-slate-200 rounded-md shadow-sm text-sm font-medium text-slate-700 bg-white hover:bg-slate-50">
                    Profile
                  </Link>
                  <button 
                    onClick={() => setIsLoggedIn(false)}
                    className="flex items-center justify-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-red-600 hover:bg-red-700"
                  >
                    Sign out
                  </button>
                </div>
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-4">
                <Link
                  to="/login"
                  className="flex items-center justify-center px-4 py-2 border border-slate-300 rounded-md shadow-sm text-sm font-medium text-slate-700 bg-white hover:bg-slate-50"
                >
                  Log in
                </Link>
                <Link
                  to="/register"
                  className="flex items-center justify-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-[#059669] hover:bg-[#047857]"
                >
                  Report Now
                </Link>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Main Content Area */}
      <main className="flex-grow flex flex-col relative">
        {children}
      </main>

      {/* Footer */}
      <footer className="bg-[#020617] text-slate-300 border-t border-slate-800" aria-labelledby="footer-heading">
        <h2 id="footer-heading" className="sr-only">Footer</h2>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 lg:py-16">
          <div className="xl:grid xl:grid-cols-3 xl:gap-8">
            
            {/* Brand & Newsletter */}
            <div className="space-y-8 xl:col-span-1">
              <Link to="/" className="flex items-center gap-2">
                <div className="bg-[#059669] p-2 rounded-lg">
                  <Shield className="h-6 w-6 text-white" />
                </div>
                <span className="font-display font-bold text-2xl tracking-tight text-white">
                  Vigilance <span className="text-[#059669]">C3MS</span>
                </span>
              </Link>
              <p className="text-sm leading-6 text-slate-400 max-w-xs">
                Empowering citizens to securely report, track, and combat corruption with AI-driven transparency and blockchain verification.
              </p>
              
              <form onSubmit={handleNewsletterSubmit} className="mt-6 sm:flex sm:max-w-md">
                <label htmlFor="email-address" className="sr-only">Email address</label>
                <div className="relative flex-grow focus-within:z-10">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <Mail className="h-5 w-5 text-slate-500" aria-hidden="true" />
                  </div>
                  <input
                    type="email"
                    name="email-address"
                    id="email-address"
                    autoComplete="email"
                    required
                    className="block w-full rounded-l-md border-0 py-2.5 pl-10 text-slate-900 ring-1 ring-inset ring-slate-800 bg-slate-900/50 text-white placeholder:text-slate-500 focus:ring-2 focus:ring-inset focus:ring-[#059669] sm:text-sm sm:leading-6"
                    placeholder="Enter your email"
                  />
                </div>
                <button
                  type="submit"
                  className="relative -ml-px inline-flex items-center gap-x-1.5 rounded-r-md px-4 py-2.5 text-sm font-semibold text-white bg-[#059669] hover:bg-[#047857] focus:z-10 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#059669] transition-colors"
                >
                  Subscribe
                  <ArrowRight className="-mr-0.5 h-4 w-4" aria-hidden="true" />
                </button>
              </form>
            </div>

            {/* Links Columns */}
            <div className="mt-16 grid grid-cols-2 gap-8 xl:col-span-2 xl:mt-0">
              <div className="md:grid md:grid-cols-2 md:gap-8">
                <div>
                  <h3 className="text-sm font-semibold leading-6 text-white font-display tracking-wider uppercase">Product</h3>
                  <ul role="list" className="mt-6 space-y-4">
                    {FOOTER_LINKS.product.map((item) => (
                      <li key={item.name}>
                        <Link to={item.path} className="text-sm leading-6 text-slate-400 hover:text-white transition-colors">
                          {item.name}
                        </Link>
                      </li>
                    ))}
                  </ul>
                </div>
                <div className="mt-10 md:mt-0">
                  <h3 className="text-sm font-semibold leading-6 text-white font-display tracking-wider uppercase">Company</h3>
                  <ul role="list" className="mt-6 space-y-4">
                    {FOOTER_LINKS.company.map((item) => (
                      <li key={item.name}>
                        <Link to={item.path} className="text-sm leading-6 text-slate-400 hover:text-white transition-colors">
                          {item.name}
                        </Link>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
              <div className="md:grid md:grid-cols-2 md:gap-8">
                <div>
                  <h3 className="text-sm font-semibold leading-6 text-white font-display tracking-wider uppercase">Legal</h3>
                  <ul role="list" className="mt-6 space-y-4">
                    {FOOTER_LINKS.legal.map((item) => (
                      <li key={item.name}>
                        <Link to={item.path} className="text-sm leading-6 text-slate-400 hover:text-white transition-colors">
                          {item.name}
                        </Link>
                      </li>
                    ))}
                  </ul>
                </div>
                <div className="mt-10 md:mt-0">
                  <h3 className="text-sm font-semibold leading-6 text-white font-display tracking-wider uppercase">Connect</h3>
                  <div className="mt-6 flex space-x-4">
                    <a href="#" className="text-slate-500 hover:text-[#059669] transition-colors">
                      <span className="sr-only">Twitter</span>
                      <Twitter className="h-6 w-6" aria-hidden="true" />
                    </a>
                    <a href="#" className="text-slate-500 hover:text-[#059669] transition-colors">
                      <span className="sr-only">Facebook</span>
                      <Facebook className="h-6 w-6" aria-hidden="true" />
                    </a>
                    <a href="#" className="text-slate-500 hover:text-[#059669] transition-colors">
                      <span className="sr-only">LinkedIn</span>
                      <Linkedin className="h-6 w-6" aria-hidden="true" />
                    </a>
                    <a href="#" className="text-slate-500 hover:text-[#059669] transition-colors">
                      <span className="sr-only">GitHub</span>
                      <Github className="h-6 w-6" aria-hidden="true" />
                    </a>
                  </div>
                  
                  {/* Demo Toggle for Auth State */}
                  <div className="mt-8 pt-8 border-t border-slate-800">
                    <button 
                      onClick={() => setIsLoggedIn(!isLoggedIn)}
                      className="text-xs text-slate-600 hover:text-slate-400 underline decoration-slate-700 underline-offset-4"
                    >
                      Toggle Demo Auth State ({isLoggedIn ? 'Logged In' : 'Logged Out'})
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
          
          <div className="mt-16 border-t border-slate-800 pt-8 sm:mt-20 lg:mt-24 flex flex-col md:flex-row justify-between items-center gap-4">
            <p className="text-xs leading-5 text-slate-500">
              &copy; {new Date().getFullYear()} Vigilance C3MS. All rights reserved. A secure initiative for public transparency.
            </p>
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <span className="flex h-2 w-2 relative">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#059669] opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-[#059669]"></span>
              </span>
              System Status: All Systems Operational
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}