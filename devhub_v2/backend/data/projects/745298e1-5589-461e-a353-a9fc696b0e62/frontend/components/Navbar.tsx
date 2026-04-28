"use client";

import { Bell, Search } from 'lucide-react';

export default function Navbar() {
  return (
    <header className="bg-white border-b border-slate-200 h-16 flex items-center justify-between px-8">
      <div className="flex items-center bg-slate-100 rounded-full px-4 py-2 w-96">
        <Search className="w-4 h-4 text-slate-400 mr-2" />
        <input 
          type="text" 
          placeholder="Search doctors, appointments..." 
          className="bg-transparent border-none outline-none text-sm w-full text-slate-700"
        />
      </div>
      <div className="flex items-center space-x-4">
        <button className="relative p-2 text-slate-400 hover:text-slate-600 transition-colors">
          <Bell className="w-5 h-5" />
          <span className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full"></span>
        </button>
      </div>
    </header>
  );
}
