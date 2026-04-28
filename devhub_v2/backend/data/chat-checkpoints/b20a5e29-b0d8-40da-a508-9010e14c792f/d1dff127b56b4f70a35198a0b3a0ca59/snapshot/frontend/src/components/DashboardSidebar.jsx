import React from 'react';
import { Calendar, FileText, Settings } from 'lucide-react';

export default function DashboardSidebar({ activeTab = 'appointments', onTabChange }) {
  const navItems = [
    { id: 'appointments', label: 'Appointments', icon: Calendar },
    { id: 'prescriptions', label: 'Prescriptions', icon: FileText },
    { id: 'settings', label: 'Settings', icon: Settings },
  ];

  return (
    <aside className="w-full md:w-64 bg-white border border-gray-200 shadow-sm rounded-xl p-4 h-fit flex-shrink-0">
      <div className="mb-6 px-4 hidden md:block">
        <h2 className="text-lg font-semibold text-gray-800">Dashboard</h2>
        <p className="text-sm text-gray-500">Manage your health</p>
      </div>
      
      <nav className="flex md:flex-col space-x-2 md:space-x-0 md:space-y-2 overflow-x-auto md:overflow-visible pb-2 md:pb-0">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;
          
          return (
            <button
              key={item.id}
              onClick={() => onTabChange && onTabChange(item.id)}
              className={`flex items-center space-x-3 px-4 py-3 rounded-lg transition-colors duration-200 whitespace-nowrap w-full ${
                isActive
                  ? 'bg-blue-50 text-blue-700 font-medium'
                  : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
              }`}
            >
              <Icon 
                className={`w-5 h-5 flex-shrink-0 ${
                  isActive ? 'text-blue-600' : 'text-gray-400'
                }`} 
              />
              <span>{item.label}</span>
            </button>
          );
        })}
      </nav>
    </aside>
  );
}