import React from 'react';
import { cn } from '../utils/cn.js';

/**
 * TabbedPanel Component
 * 
 * A reusable, accessible tabbed interface for switching between different views 
 * or sections within a dashboard or workspace. Follows the C3MS design system 
 * with crisp white cards, subtle borders, and clear visual hierarchy.
 *
 * @param {Object[]} tabs - Array of tab objects: { id, label, icon: IconComponent, content: ReactNode, badge: string|number, disabled: boolean }
 * @param {string} defaultTabId - The ID of the tab to open by default on initial render
 * @param {string} className - Additional Tailwind classes for the outer container
 * @param {string} panelClassName - Additional Tailwind classes for the inner content panel
 * @param {Function} onTabChange - Optional callback fired when a tab is selected, receives the tab id
 */
export default function TabbedPanel({
  tabs = [],
  defaultTabId,
  className,
  panelClassName,
  onTabChange
}) {
  // Initialize state with defaultTabId or the first available non-disabled tab
  const [activeTabId, setActiveTabId] = React.useState(() => {
    if (defaultTabId) return defaultTabId;
    const firstAvailable = tabs.find(t => !t.disabled);
    return firstAvailable ? firstAvailable.id : null;
  });

  const handleTabClick = (id, disabled) => {
    if (disabled) return;
    
    setActiveTabId(id);
    if (onTabChange) {
      onTabChange(id);
    }
  };

  // Find the currently active tab object to render its content
  const activeTab = tabs.find((tab) => tab.id === activeTabId);

  if (!tabs || tabs.length === 0) {
    return (
      <div className={cn("bg-white rounded-lg shadow-sm border border-slate-200 p-8 text-center text-slate-500", className)}>
        No tabs available.
      </div>
    );
  }

  return (
    <div className={cn("bg-white rounded-lg shadow-sm border border-slate-200 overflow-hidden flex flex-col", className)}>
      {/* Tab Header Navigation */}
      <div 
        className="flex overflow-x-auto border-b border-slate-200 hide-scrollbar bg-slate-50/50"
        role="tablist"
        aria-orientation="horizontal"
      >
        {tabs.map((tab) => {
          const isActive = tab.id === activeTabId;
          const Icon = tab.icon;
          const isDisabled = tab.disabled;

          return (
            <button
              key={tab.id}
              id={`tab-${tab.id}`}
              role="tab"
              aria-selected={isActive}
              aria-controls={`panel-${tab.id}`}
              disabled={isDisabled}
              onClick={() => handleTabClick(tab.id, isDisabled)}
              className={cn(
                "group flex items-center gap-2 px-6 py-4 text-sm font-medium transition-all duration-200 whitespace-nowrap border-b-2 focus:outline-none focus-visible:ring-2 focus-visible:ring-[#047857] focus-visible:ring-inset",
                isActive
                  ? "border-[#047857] text-[#047857] bg-white"
                  : "border-transparent text-slate-600 hover:text-slate-900 hover:bg-slate-100/50",
                isDisabled && "opacity-50 cursor-not-allowed hover:text-slate-600 hover:bg-transparent"
              )}
            >
              {Icon && (
                <Icon 
                  className={cn(
                    "w-4 h-4 transition-colors", 
                    isActive ? "text-[#047857]" : "text-slate-400 group-hover:text-slate-600",
                    isDisabled && "group-hover:text-slate-400"
                  )} 
                  aria-hidden="true"
                />
              )}
              
              <span>{tab.label}</span>
              
              {/* Optional Badge (e.g., for counts) */}
              {tab.badge !== undefined && (
                <span 
                  className={cn(
                    "ml-1.5 inline-flex items-center justify-center px-2 py-0.5 text-xs font-semibold rounded-full transition-colors",
                    isActive 
                      ? "bg-[#047857]/10 text-[#047857]" 
                      : "bg-slate-200 text-slate-600 group-hover:bg-slate-300",
                    isDisabled && "group-hover:bg-slate-200"
                  )}
                >
                  {tab.badge}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Active Tab Content Panel */}
      <div 
        id={`panel-${activeTabId}`}
        role="tabpanel"
        aria-labelledby={`tab-${activeTabId}`}
        className={cn("p-6 flex-1 overflow-y-auto focus:outline-none", panelClassName)}
        tabIndex={0}
      >
        {activeTab ? (
          <div className="animate-in fade-in slide-in-from-bottom-1 duration-300">
            {activeTab.content}
          </div>
        ) : (
          <div className="flex items-center justify-center h-full text-slate-500 italic">
            Select a tab to view content
          </div>
        )}
      </div>
    </div>
  );
}