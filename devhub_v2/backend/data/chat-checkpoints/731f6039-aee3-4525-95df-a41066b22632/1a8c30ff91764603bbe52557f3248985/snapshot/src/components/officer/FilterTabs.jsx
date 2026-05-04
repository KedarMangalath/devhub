import React from 'react';
import { cn } from '../../utils/cn';

export default function FilterTabs({ tabs = [], activeTab, onChange }) {
  return (
    <div className="w-full border-b border-slate-200">
      <nav 
        className="-mb-px flex space-x-6 overflow-x-auto [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]" 
        aria-label="Tabs"
      >
        {tabs.map((tab) => {
          const isActive = activeTab === tab;
          return (
            <button
              key={tab}
              onClick={() => onChange(tab)}
              className={cn(
                "whitespace-nowrap border-b-2 py-4 px-2 text-sm font-medium transition-all duration-200 outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2",
                isActive
                  ? "border-blue-700 text-blue-800"
                  : "border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-800"
              )}
              aria-current={isActive ? 'page' : undefined}
            >
              {tab}
            </button>
          );
        })}
      </nav>
    </div>
  );
}