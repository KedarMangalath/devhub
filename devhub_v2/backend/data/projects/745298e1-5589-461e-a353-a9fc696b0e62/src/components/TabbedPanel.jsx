import React from 'react'
import { cn } from '../utils/cn.js'

export default function TabbedPanel({ 
  tabs = [], 
  defaultTab, 
  className,
  variant = 'underline', // 'underline' | 'pills' | 'enclosed'
  contentClassName,
  onTabChange
}) {
  const [activeTabId, setActiveTabId] = React.useState(
    defaultTab || (tabs.length > 0 ? tabs[0].id : null)
  )

  if (!tabs || tabs.length === 0) {
    return null
  }

  const handleTabClick = (tabId) => {
    setActiveTabId(tabId)
    if (onTabChange) {
      onTabChange(tabId)
    }
  }

  const activeTab = tabs.find((tab) => tab.id === activeTabId) || tabs[0]

  return (
    <div className={cn("flex flex-col w-full", className)}>
      {variant === 'underline' && (
        <div className="border-b border-slate-200">
          <nav className="-mb-px flex space-x-8 overflow-x-auto no-scrollbar" aria-label="Tabs">
            {tabs.map((tab) => {
              const isActive = tab.id === activeTabId
              const Icon = tab.icon
              
              return (
                <button
                  key={tab.id}
                  onClick={() => !tab.disabled && handleTabClick(tab.id)}
                  disabled={tab.disabled}
                  className={cn(
                    "whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm flex items-center gap-2 transition-all outline-none focus-visible:ring-2 focus-visible:ring-sky-500 focus-visible:ring-offset-2",
                    isActive
                      ? "border-sky-600 text-sky-600"
                      : "border-transparent text-slate-500 hover:text-slate-800 hover:border-slate-300",
                    tab.disabled && "opacity-50 cursor-not-allowed hover:text-slate-500 hover:border-transparent"
                  )}
                  aria-current={isActive ? 'page' : undefined}
                >
                  {Icon && (
                    <Icon 
                      className={cn(
                        "w-4 h-4 transition-colors",
                        isActive ? "text-sky-600" : "text-slate-400 group-hover:text-slate-500"
                      )} 
                      aria-hidden="true" 
                    />
                  )}
                  {tab.label}
                  {tab.badge && (
                    <span
                      className={cn(
                        "ml-1.5 rounded-full py-0.5 px-2 text-xs font-semibold transition-colors",
                        isActive
                          ? "bg-sky-100 text-sky-700"
                          : "bg-slate-100 text-slate-600"
                      )}
                    >
                      {tab.badge}
                    </span>
                  )}
                </button>
              )
            })}
          </nav>
        </div>
      )}

      {variant === 'pills' && (
        <div className="flex items-center space-x-2 overflow-x-auto no-scrollbar pb-2">
          {tabs.map((tab) => {
            const isActive = tab.id === activeTabId
            const Icon = tab.icon
            
            return (
              <button
                key={tab.id}
                onClick={() => !tab.disabled && handleTabClick(tab.id)}
                disabled={tab.disabled}
                className={cn(
                  "whitespace-nowrap px-4 py-2 rounded-full font-medium text-sm flex items-center gap-2 transition-all outline-none focus-visible:ring-2 focus-visible:ring-sky-500 focus-visible:ring-offset-2",
                  isActive
                    ? "bg-sky-600 text-white shadow-sm"
                    : "bg-white text-slate-600 hover:bg-slate-50 border border-slate-200",
                  tab.disabled && "opacity-50 cursor-not-allowed hover:bg-white"
                )}
                aria-current={isActive ? 'page' : undefined}
              >
                {Icon && (
                  <Icon 
                    className={cn(
                      "w-4 h-4",
                      isActive ? "text-white" : "text-slate-400"
                    )} 
                    aria-hidden="true" 
                  />
                )}
                {tab.label}
                {tab.badge && (
                  <span
                    className={cn(
                      "ml-1.5 rounded-full py-0.5 px-2 text-xs font-semibold",
                      isActive
                        ? "bg-sky-500/30 text-white"
                        : "bg-slate-100 text-slate-600"
                    )}
                  >
                    {tab.badge}
                  </span>
                )}
              </button>
            )
          })}
        </div>
      )}

      {variant === 'enclosed' && (
        <div className="bg-slate-100/80 p-1 rounded-xl inline-flex overflow-x-auto no-scrollbar">
          {tabs.map((tab) => {
            const isActive = tab.id === activeTabId
            const Icon = tab.icon
            
            return (
              <button
                key={tab.id}
                onClick={() => !tab.disabled && handleTabClick(tab.id)}
                disabled={tab.disabled}
                className={cn(
                  "whitespace-nowrap px-4 py-2 rounded-lg font-medium text-sm flex items-center gap-2 transition-all outline-none focus-visible:ring-2 focus-visible:ring-sky-500 focus-visible:ring-offset-2",
                  isActive
                    ? "bg-white text-slate-900 shadow-sm"
                    : "text-slate-600 hover:text-slate-900 hover:bg-slate-200/50",
                  tab.disabled && "opacity-50 cursor-not-allowed hover:bg-transparent hover:text-slate-600"
                )}
                aria-current={isActive ? 'page' : undefined}
              >
                {Icon && (
                  <Icon 
                    className={cn(
                      "w-4 h-4",
                      isActive ? "text-sky-600" : "text-slate-400"
                    )} 
                    aria-hidden="true" 
                  />
                )}
                {tab.label}
                {tab.badge && (
                  <span
                    className={cn(
                      "ml-1.5 rounded-full py-0.5 px-2 text-xs font-semibold",
                      isActive
                        ? "bg-slate-100 text-slate-900"
                        : "bg-slate-200/50 text-slate-600"
                    )}
                  >
                    {tab.badge}
                  </span>
                )}
              </button>
            )
          })}
        </div>
      )}
      
      <div 
        className={cn("mt-6 focus:outline-none", contentClassName)} 
        tabIndex={0}
      >
        {activeTab?.content}
      </div>
    </div>
  )
}