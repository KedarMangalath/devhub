import { Outlet, Link, useLocation } from 'react-router-dom';
import { Shield, FileText, Search, BarChart3, Menu } from 'lucide-react';

export default function Layout() {
  const location = useLocation();
  const isAdmin = location.pathname.startsWith('/admin');

  return (
    <div className="min-h-screen flex flex-col">
      <header className="bg-vacb-900 text-white shadow-md">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16 items-center">
            <Link to="/" className="flex items-center space-x-3">
              <Shield className="h-8 w-8 text-vacb-500" />
              <div>
                <h1 className="font-bold text-xl leading-tight">C3MS Kerala</h1>
                <p className="text-xs text-vacb-100">Vigilance & Anti-Corruption Bureau</p>
              </div>
            </Link>
            <nav className="hidden md:flex space-x-8">
              <Link to="/submit" className="hover:text-vacb-500 transition-colors flex items-center gap-2">
                <FileText size={18}/> Report
              </Link>
              <Link to="/track" className="hover:text-vacb-500 transition-colors flex items-center gap-2">
                <Search size={18}/> Track
              </Link>
              <Link to="/admin" className="hover:text-vacb-500 transition-colors flex items-center gap-2">
                <BarChart3 size={18}/> VACB Portal
              </Link>
            </nav>
          </div>
        </div>
      </header>

      <div className="flex-1 flex max-w-7xl w-full mx-auto">
        {isAdmin && (
          <aside className="w-64 bg-white border-r border-gray-200 hidden md:block py-6">
            <nav className="space-y-1 px-3">
              <Link to="/admin" className={`flex items-center px-3 py-2 text-sm font-medium rounded-md ${location.pathname === '/admin' ? 'bg-vacb-50 text-vacb-700' : 'text-gray-700 hover:bg-gray-50'}`}>
                <BarChart3 className="mr-3 h-5 w-5" /> Dashboard
              </Link>
              <Link to="/admin/complaints" className={`flex items-center px-3 py-2 text-sm font-medium rounded-md ${location.pathname === '/admin/complaints' ? 'bg-vacb-50 text-vacb-700' : 'text-gray-700 hover:bg-gray-50'}`}>
                <FileText className="mr-3 h-5 w-5" /> All Complaints
              </Link>
            </nav>
          </aside>
        )}
        <main className="flex-1 p-4 sm:p-6 lg:p-8 overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}