import React from 'react';
import { Outlet, NavLink, Link, useLocation } from 'react-router-dom';
import { Menu, X, Activity, Home, Users, Calendar, FileText, Bell, User } from 'lucide-react';
import { cn } from '../utils/cn';
import { patient_profile } from '../mockData';

const navItems = [
  { name: 'Dashboard', path: '/dashboard', icon: Home },
  { name: 'Find Doctors', path: '/doctors', icon: Users },
  { name: 'Appointments', path: '/appointments', icon: Calendar },
  { name: 'Medical History', path: '/history', icon: FileText },
];

export default function AppShell() {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = React.useState(false);
  const location = useLocation();

  // Close mobile menu automatically when route changes
  React.useEffect(() => {
    setIsMobileMenuOpen(false);
  }, [location.pathname]);

  return (
    <div className="min-h-screen bg-[#F8FAFC] text-[#0F172A] flex flex-col font-sans">
      {/* Header */}
      <header className="sticky top-0 z-50 w-full bg-white border-b border-slate-200 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            {/* Logo */}
            <div className="flex items-center gap-2">
              <Link to="/" className="flex items-center gap-2 group">
                <div className="bg-[#0284C7] p-1.5 rounded-lg group-hover:bg-[#026aa2] transition-colors">
                  <Activity className="w-6 h-6 text-white" />
                </div>
                <span className="font-bold text-xl tracking-tight text-[#0F172A]">
                  Omnia
                </span>
              </Link>
            </div>

            {/* Desktop Nav */}
            <nav className="hidden md:flex items-center gap-1">
              {navItems.map((item) => {
                const Icon = item.icon;
                return (
                  <NavLink
                    key={item.name}
                    to={item.path}
                    className={({ isActive }) =>
                      cn(
                        "flex items-center gap-2 px-3 py-2 rounded-md text-sm font-medium transition-colors",
                        isActive
                          ? "bg-sky-50 text-[#0284C7]"
                          : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                      )
                    }
                  >
                    <Icon className="w-4 h-4" />
                    {item.name}
                  </NavLink>
                );
              })}
            </nav>

            {/* Right Actions */}
            <div className="hidden md:flex items-center gap-4">
              <button className="relative p-2 text-slate-400 hover:text-slate-500 transition-colors rounded-full hover:bg-slate-50">
                <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-red-500 rounded-full border-2 border-white"></span>
                <Bell className="w-5 h-5" />
              </button>
              
              <div className="flex items-center gap-3 pl-4 border-l border-slate-200">
                <div className="text-right hidden lg:block">
                  <p className="text-sm font-medium text-slate-900">{patient_profile.name}</p>
                  <p className="text-xs text-slate-500">
                    Health Score: <span className="text-[#10B981] font-semibold">{patient_profile.health_score}</span>
                  </p>
                </div>
                <img
                  src={patient_profile.avatar}
                  alt={patient_profile.name}
                  className="w-9 h-9 rounded-full object-cover border border-slate-200"
                />
              </div>
            </div>

            {/* Mobile menu button */}
            <div className="flex items-center md:hidden gap-4">
              <button className="relative p-2 text-slate-400 hover:text-slate-500 transition-colors">
                <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-red-500 rounded-full border-2 border-white"></span>
                <Bell className="w-5 h-5" />
              </button>
              <button
                onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
                className="p-2 -mr-2 text-slate-400 hover:text-slate-500 hover:bg-slate-50 rounded-md transition-colors"
                aria-label="Toggle menu"
              >
                {isMobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
              </button>
            </div>
          </div>
        </div>

        {/* Mobile Nav Drawer */}
        {isMobileMenuOpen && (
          <div className="md:hidden border-t border-slate-200 bg-white shadow-lg absolute w-full z-40">
            <div className="px-2 pt-2 pb-3 space-y-1">
              {navItems.map((item) => {
                const Icon = item.icon;
                return (
                  <NavLink
                    key={item.name}
                    to={item.path}
                    className={({ isActive }) =>
                      cn(
                        "flex items-center gap-3 px-3 py-2.5 rounded-md text-base font-medium transition-colors",
                        isActive
                          ? "bg-sky-50 text-[#0284C7]"
                          : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                      )
                    }
                  >
                    <Icon className="w-5 h-5" />
                    {item.name}
                  </NavLink>
                );
              })}
            </div>
            <div className="pt-4 pb-3 border-t border-slate-200 bg-slate-50">
              <div className="flex items-center px-5 gap-3">
                <img
                  src={patient_profile.avatar}
                  alt={patient_profile.name}
                  className="w-10 h-10 rounded-full object-cover border border-slate-200 bg-white"
                />
                <div>
                  <div className="text-base font-medium text-slate-900">{patient_profile.name}</div>
                  <div className="text-sm font-medium text-slate-500">{patient_profile.email}</div>
                </div>
              </div>
              <div className="mt-3 px-2 space-y-1">
                <Link
                  to="/profile"
                  className="flex items-center gap-3 px-3 py-2.5 rounded-md text-base font-medium text-slate-600 hover:bg-slate-100 hover:text-slate-900 transition-colors"
                >
                  <User className="w-5 h-5" />
                  Your Profile
                </Link>
              </div>
            </div>
          </div>
        )}
      </header>

      {/* Main Content */}
      <main className="flex-1 w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Outlet />
      </main>
    </div>
  );
}