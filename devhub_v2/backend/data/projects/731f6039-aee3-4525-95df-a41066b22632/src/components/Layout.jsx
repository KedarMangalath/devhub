import { Outlet, Link, useLocation } from 'react-router-dom';
import { Shield, FileText, Search, LayoutDashboard, BarChart3, Menu } from 'lucide-react';
import { useState } from 'react';

export default function Layout() {
  const location = useLocation();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const navLinks = [
    { path: '/', label: 'Home', icon: Shield, public: true },
    { path: '/submit', label: 'File Complaint', icon: FileText, public: true },
    { path: '/track', label: 'Track Status', icon: Search, public: true },
    { path: '/officer', label: 'Officer Portal', icon: LayoutDashboard, public: false },
    { path: '/director', label: 'Analytics', icon: BarChart3, public: false },
  ];

  return (
    <div className="min-h-screen flex flex-col">
      <header className="bg-vacb-900 text-white shadow-md">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16 items-center">
            <div className="flex items-center space-x-3">
              <Shield className="h-8 w-8 text-vacb-100" />
              <div>
                <h1 className="text-xl font-bold leading-tight">C3MS Kerala</h1>
                <p className="text-xs text-vacb-100">Vigilance & Anti-Corruption Bureau</p>
              </div>
            </div>
            
            {/* Desktop Nav */}
            <nav className="hidden md:flex space-x-1">
              {navLinks.map((link) => {
                const Icon = link.icon;
                const isActive = location.pathname === link.path || (link.path !== '/' && location.pathname.startsWith(link.path));
                return (
                  <Link
                    key={link.path}
                    to={link.path}
                    className={`flex items-center px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                      isActive ? 'bg-vacb-700 text-white' : 'text-vacb-100 hover:bg-vacb-800 hover:text-white'
                    }`}
                  >
                    <Icon className="h-4 w-4 mr-2" />
                    {link.label}
                  </Link>
                );
              })}
            </nav>

            {/* Mobile menu button */}
            <div className="md:hidden">
              <button 
                onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
                className="text-vacb-100 hover:text-white focus:outline-none"
              >
                <Menu className="h-6 w-6" />
              </button>
            </div>
          </div>
        </div>

        {/* Mobile Nav */}
        {mobileMenuOpen && (
          <div className="md:hidden bg-vacb-800 px-2 pt-2 pb-3 space-y-1">
            {navLinks.map((link) => {
              const Icon = link.icon;
              return (
                <Link
                  key={link.path}
                  to={link.path}
                  onClick={() => setMobileMenuOpen(false)}
                  className="flex items-center px-3 py-2 rounded-md text-base font-medium text-white hover:bg-vacb-700"
                >
                  <Icon className="h-5 w-5 mr-3" />
                  {link.label}
                </Link>
              );
            })}
          </div>
        )}
      </header>

      <main className="flex-grow max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Outlet />
      </main>

      <footer className="bg-gray-800 text-gray-300 py-6">
        <div className="max-w-7xl mx-auto px-4 text-center text-sm">
          <p>&copy; 2025 Vigilance and Anti-Corruption Bureau, Government of Kerala.</p>
          <p className="mt-1 text-gray-500">Secured by Blockchain • Powered by AI</p>
        </div>
      </footer>
    </div>
  );
}