"use client";

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { LayoutDashboard, Users, Calendar, Stethoscope, Activity } from 'lucide-react';

export default function Sidebar() {
  const pathname = usePathname();

  const links = [
    { name: 'Dashboard', href: '/', icon: LayoutDashboard },
    { name: 'Doctors', href: '/doctors', icon: Users },
    { name: 'Appointments', href: '/appointments', icon: Calendar },
    { name: 'AI Symptom Checker', href: '/ai-symptom-checker', icon: Activity },
  ];

  return (
    <div className="w-64 bg-white border-r border-slate-200 h-screen flex flex-col">
      <div className="p-6 flex items-center space-x-3">
        <div className="bg-omnia-500 p-2 rounded-lg">
          <Stethoscope className="text-white w-6 h-6" />
        </div>
        <span className="text-2xl font-bold text-slate-800 tracking-tight">Omnia.</span>
      </div>
      
      <nav className="flex-1 px-4 space-y-2 mt-4">
        {links.map((link) => {
          const Icon = link.icon;
          const isActive = pathname === link.href;
          return (
            <Link
              key={link.name}
              href={link.href}
              className={`flex items-center space-x-3 px-4 py-3 rounded-xl transition-colors ${
                isActive 
                  ? 'bg-omnia-50 text-omnia-600 font-medium' 
                  : 'text-slate-500 hover:bg-slate-50 hover:text-slate-900'
              }`}
            >
              <Icon className={`w-5 h-5 ${isActive ? 'text-omnia-600' : 'text-slate-400'}`} />
              <span>{link.name}</span>
            </Link>
          );
        })}
      </nav>

      <div className="p-4 border-t border-slate-100">
        <div className="flex items-center space-x-3 px-4 py-2">
          <div className="w-8 h-8 rounded-full bg-slate-200 flex items-center justify-center text-slate-600 font-bold">
            AJ
          </div>
          <div className="text-sm">
            <p className="font-medium text-slate-700">Alex Johnson</p>
            <p className="text-slate-400 text-xs">Patient</p>
          </div>
        </div>
      </div>
    </div>
  );
}
