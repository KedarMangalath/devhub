import { useState } from 'react'
import { NavLink } from 'react-router-dom'
import { LayoutDashboard, Briefcase, Bell, BarChart3, Settings, ChevronLeft, ChevronRight } from 'lucide-react'
import { userProfile } from '../../mockData.js'

export default function DashboardSidebar() {
  const [isCollapsed, setIsCollapsed] = useState(false)

  const navItems = [
    { name: 'Overview', path: '/dashboard', icon: LayoutDashboard },
    { name: 'Assigned Cases', path: '/dashboard/cases', icon: Briefcase },
    { name: 'AI Alerts', path: '/dashboard/alerts', icon: Bell },
    { name: 'Analytics', path: '/analytics', icon: BarChart3 },
    { name: 'Settings', path: '/settings', icon: Settings },
  ]

  return (
    <aside 
      className={`relative flex flex-col h-screen bg-card border-r border-border transition-all duration-300 z-20 ${
        isCollapsed ? 'w-20' : 'w-64'
      }`}
    >
      {/* Header / Logo Area */}
      <div className="flex items-center h-16 px-4 border-b border-border">
        <div className={`flex items-center gap-3 overflow-hidden ${isCollapsed ? 'justify-center w-full' : ''}`}>
          <div className="flex-shrink-0 w-8 h-8 rounded bg-primary flex items-center justify-center text-primary-foreground font-bold font-display">
            C3
          </div>
          {!isCollapsed && (
            <span className="font-display font-semibold text-lg text-foreground whitespace-nowrap">
              Vigilance C3MS
            </span>
          )}
        </div>
      </div>

      {/* Collapse Toggle Button */}
      <button
        onClick={() => setIsCollapsed(!isCollapsed)}
        className="absolute -right-3 top-12 flex items-center justify-center w-6 h-6 rounded-full bg-card border border-border text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors shadow-sm z-30 focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-background"
        aria-label={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
      >
        {isCollapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
      </button>

      {/* Navigation Links */}
      <nav className="flex-1 overflow-y-auto py-6 px-3 space-y-1.5 scrollbar-hide">
        {navItems.map((item) => (
          <NavLink
            key={item.name}
            to={item.path}
            title={isCollapsed ? item.name : undefined}
            className={({ isActive }) => `
              flex items-center gap-3 px-3 py-2.5 rounded-md transition-all duration-200 group
              ${isActive 
                ? 'bg-primary/10 text-primary font-medium' 
                : 'text-muted-foreground hover:bg-secondary hover:text-foreground'
              }
              ${isCollapsed ? 'justify-center' : ''}
            `}
          >
            {({ isActive }) => (
              <>
                <item.icon 
                  size={20} 
                  className={`flex-shrink-0 transition-colors ${
                    isActive ? 'text-primary' : 'text-muted-foreground group-hover:text-foreground'
                  }`} 
                />
                {!isCollapsed && (
                  <span className="font-body text-sm truncate">
                    {item.name}
                  </span>
                )}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      {/* User Profile Snippet */}
      <div className="p-4 border-t border-border bg-card/50">
        <div className={`flex items-center gap-3 ${isCollapsed ? 'justify-center' : ''}`}>
          <div className="relative flex-shrink-0">
            <img 
              src={userProfile.avatar} 
              alt={userProfile.name} 
              className="w-10 h-10 rounded-full object-cover border-2 border-background shadow-sm"
            />
            <span className="absolute bottom-0 right-0 w-2.5 h-2.5 bg-green-500 border-2 border-background rounded-full"></span>
          </div>
          
          {!isCollapsed && (
            <div className="flex flex-col overflow-hidden">
              <span className="text-sm font-medium text-foreground truncate font-display">
                {userProfile.name}
              </span>
              <span className="text-xs text-muted-foreground truncate font-body">
                {userProfile.role}
              </span>
            </div>
          )}
        </div>
      </div>
    </aside>
  )
}