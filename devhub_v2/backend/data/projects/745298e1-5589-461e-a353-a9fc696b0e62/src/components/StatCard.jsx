import React from 'react';
import { ArrowUpRight, ArrowDownRight, Minus } from 'lucide-react';
import { cn } from '../utils/cn';

/**
 * StatCard Component
 * 
 * A reusable metric card for dashboard summaries, trust indicators, 
 * counts, ratings, progress, or product metrics.
 * 
 * @param {Object} props
 * @param {string} props.title - The title of the metric (e.g., "Total Patients")
 * @param {React.ReactNode} props.value - The main value to display
 * @param {React.ElementType} [props.icon] - Lucide icon component
 * @param {Object} [props.trend] - Trend information
 * @param {string} props.trend.value - The trend value (e.g., "12%")
 * @param {boolean} [props.trend.isPositive] - Whether the trend is positive
 * @param {boolean} [props.trend.isNeutral] - Whether the trend is neutral
 * @param {string} [props.description] - Additional context text
 * @param {number} [props.progress] - Progress bar value (0-100)
 * @param {React.ReactNode} [props.action] - Optional action element (e.g., a button or link)
 * @param {string} [props.className] - Additional wrapper classes
 * @param {string} [props.iconClassName] - Additional icon classes
 * @param {string} [props.iconWrapperClassName] - Additional icon wrapper classes
 * @param {string} [props.valueClassName] - Additional value classes
 */
export default function StatCard({
  title,
  value,
  icon: Icon,
  trend,
  description,
  progress,
  action,
  className,
  iconClassName,
  iconWrapperClassName,
  valueClassName,
}) {
  return (
    <div
      className={cn(
        "bg-white border border-slate-200 rounded-2xl p-6 shadow-sm hover:shadow-md transition-all duration-200 flex flex-col group",
        className
      )}
    >
      <div className="flex items-start justify-between mb-4">
        <h3 className="text-sm font-medium text-slate-500 font-body leading-tight group-hover:text-slate-700 transition-colors">
          {title}
        </h3>
        {Icon && (
          <div 
            className={cn(
              "p-2.5 rounded-xl bg-sky-50 text-sky-600 shrink-0 ml-4 transition-colors group-hover:bg-sky-100", 
              iconWrapperClassName
            )}
          >
            <Icon className={cn("w-5 h-5", iconClassName)} strokeWidth={2.5} />
          </div>
        )}
      </div>
      
      <div className="flex items-baseline gap-2 mt-auto">
        <span className={cn("text-3xl font-bold text-slate-900 font-display tracking-tight", valueClassName)}>
          {value}
        </span>
      </div>

      {typeof progress === 'number' && (
        <div 
          className="mt-5 w-full bg-slate-100 rounded-full h-1.5 overflow-hidden" 
          role="progressbar" 
          aria-valuenow={progress} 
          aria-valuemin="0" 
          aria-valuemax="100"
        >
          <div 
            className="bg-sky-600 h-1.5 rounded-full transition-all duration-1000 ease-out"
            style={{ width: `${Math.min(Math.max(progress, 0), 100)}%` }}
          />
        </div>
      )}

      {(trend || description || action) && (
        <div className="mt-4 flex items-center justify-between gap-4">
          <div className="flex items-center gap-2 text-sm font-body overflow-hidden">
            {trend && (
              <span
                className={cn(
                  "flex items-center font-medium px-2 py-0.5 rounded-md text-xs shrink-0",
                  trend.isNeutral
                    ? "text-slate-600 bg-slate-100"
                    : trend.isPositive
                    ? "text-emerald-700 bg-emerald-50"
                    : "text-rose-700 bg-rose-50"
                )}
              >
                {trend.isNeutral ? (
                  <Minus className="w-3 h-3 mr-1" strokeWidth={2.5} />
                ) : trend.isPositive ? (
                  <ArrowUpRight className="w-3 h-3 mr-1" strokeWidth={2.5} />
                ) : (
                  <ArrowDownRight className="w-3 h-3 mr-1" strokeWidth={2.5} />
                )}
                {trend.value}
              </span>
            )}
            {description && (
              <span className="text-slate-500 truncate">{description}</span>
            )}
          </div>
          
          {action && (
            <div className="shrink-0">
              {action}
            </div>
          )}
        </div>
      )}
    </div>
  );
}