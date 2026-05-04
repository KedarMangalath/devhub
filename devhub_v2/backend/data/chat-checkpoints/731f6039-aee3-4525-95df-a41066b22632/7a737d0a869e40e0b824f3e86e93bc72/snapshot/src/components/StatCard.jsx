import React from 'react'
import { ArrowUpRight, ArrowDownRight, Minus } from 'lucide-react'

/**
 * StatCard
 * 
 * A reusable metric card for dashboard summaries, trust indicators, 
 * counts, ratings, progress, or product metrics.
 * 
 * @param {Object} props
 * @param {string} props.title - The title of the metric (e.g., "Total Complaints")
 * @param {string|number} props.value - The main value to display
 * @param {React.ElementType} props.icon - Lucide icon component
 * @param {Object} [props.trend] - Trend data { value: number, isPositive: boolean|null, label: string }
 * @param {string} [props.description] - Additional context text below the value
 * @param {'primary'|'accent'|'danger'|'info'|'muted'} [props.color='primary'] - Color theme for icon and progress
 * @param {number} [props.progress] - Optional progress bar value (0-100)
 * @param {boolean} [props.isLive] - If true, shows a pulsing live indicator next to the title
 * @param {string} [props.className] - Additional Tailwind classes
 */
export default function StatCard({
  title,
  value,
  icon: Icon,
  trend,
  description,
  color = 'primary',
  progress,
  isLive = false,
  className = ''
}) {
  // Theme mappings aligned with C3MS design system
  const themeStyles = {
    primary: {
      iconBg: 'bg-vacb-50',
      iconText: 'text-vacb-700',
      progressBg: 'bg-vacb-600',
      trendUp: 'text-vacb-600',
      trendDown: 'text-red-600'
    },
    accent: {
      iconBg: 'bg-amber-50',
      iconText: 'text-amber-600',
      progressBg: 'bg-amber-500',
      trendUp: 'text-amber-600',
      trendDown: 'text-red-600'
    },
    danger: {
      iconBg: 'bg-red-50',
      iconText: 'text-red-600',
      progressBg: 'bg-red-500',
      trendUp: 'text-red-600',
      trendDown: 'text-vacb-600' // Inverse logic: down is good for danger metrics
    },
    info: {
      iconBg: 'bg-vacb-50',
      iconText: 'text-vacb-600',
      progressBg: 'bg-vacb-500',
      trendUp: 'text-vacb-600',
      trendDown: 'text-slate-500'
    },
    muted: {
      iconBg: 'bg-slate-100',
      iconText: 'text-slate-600',
      progressBg: 'bg-slate-400',
      trendUp: 'text-slate-600',
      trendDown: 'text-slate-600'
    }
  }

  const currentTheme = themeStyles[color] || themeStyles.primary

  return (
    <div className={`bg-white rounded-lg border border-slate-200 shadow-sm p-5 flex flex-col transition-all duration-200 hover:shadow-md ${className}`}>
      <div className="flex items-start justify-between">
        <div className="flex items-center space-x-2">
          <h3 className="text-sm font-medium text-slate-600 tracking-wide">
            {title}
          </h3>
          {isLive && (
            <span className="relative flex h-2.5 w-2.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-vacb-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-vacb-500"></span>
            </span>
          )}
        </div>
        
        {Icon && (
          <div className={`p-2 rounded-md ${currentTheme.iconBg} ${currentTheme.iconText}`}>
            <Icon size={20} strokeWidth={2.5} />
          </div>
        )}
      </div>
      
      <div className="mt-3">
        <p className="text-3xl font-bold text-slate-900 tracking-tight">
          {value}
        </p>
      </div>

      {/* Optional Progress Bar */}
      {typeof progress === 'number' && (
        <div className="mt-4 w-full bg-slate-100 rounded-full h-1.5 overflow-hidden">
          <div 
            className={`h-full rounded-full transition-all duration-500 ease-out ${currentTheme.progressBg}`}
            style={{ width: `${Math.min(Math.max(progress, 0), 100)}%` }}
            role="progressbar"
            aria-valuenow={progress}
            aria-valuemin="0"
            aria-valuemax="100"
          />
        </div>
      )}

      {/* Footer: Trend and Description */}
      {(trend || description) && (
        <div className="mt-4 flex items-center text-sm">
          {trend && (
            <div className={`flex items-center font-medium ${
              trend.isPositive === true ? currentTheme.trendUp : 
              trend.isPositive === false ? currentTheme.trendDown : 
              'text-slate-500'
            }`}>
              {trend.isPositive === true && <ArrowUpRight size={16} className="mr-1" strokeWidth={2.5} />}
              {trend.isPositive === false && <ArrowDownRight size={16} className="mr-1" strokeWidth={2.5} />}
              {trend.isPositive === null && <Minus size={16} className="mr-1" strokeWidth={2.5} />}
              <span>{trend.value}%</span>
            </div>
          )}
          
          {description && (
            <span className={`text-slate-500 truncate ${trend ? 'ml-2 pl-2 border-l border-slate-200' : ''}`}>
              {description}
            </span>
          )}
        </div>
      )}
    </div>
  )
}