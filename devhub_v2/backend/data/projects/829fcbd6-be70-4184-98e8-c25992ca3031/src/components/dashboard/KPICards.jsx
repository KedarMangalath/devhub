import React from 'react';
import { TrendingUp, TrendingDown, Activity, AlertOctagon } from 'lucide-react';
import { FileText, CheckCircle, Clock, Search } from 'lucide-react';
import { dashboardMetrics } from '../../mockData';

const iconMap = {
  FileText,
  CheckCircle,
  Clock,
  Search,
  Activity,
  AlertOctagon
};

export default function KPICards({ metrics }) {
  // Fallback to specific metrics if none provided, matching the requested 4 types:
  // Total cases, resolved cases, avg resolution time, and active alerts/investigations
  const displayMetrics = metrics && metrics.length > 0 
    ? metrics.slice(0, 4) 
    : [
        dashboardMetrics[0], // Total Complaints
        dashboardMetrics[1], // Resolved Cases
        dashboardMetrics[4], // Avg Resolution Time
        dashboardMetrics[2], // Active Investigations
      ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 w-full">
      {displayMetrics.map((metric, index) => {
        const IconComponent = iconMap[metric.icon] || Activity;
        
        // Determine trend direction and color context
        // For metrics like "Resolution Time", a negative trend (decrease) is positive/good.
        const isNegative = metric.trend.startsWith('-');
        const isLowerBetter = metric.label.toLowerCase().includes('time') || metric.label.toLowerCase().includes('alert');
        
        let trendColor = 'text-emerald-600 dark:text-emerald-400';
        let trendBg = 'bg-emerald-50 dark:bg-emerald-500/10';
        
        if ((isNegative && !isLowerBetter) || (!isNegative && isLowerBetter)) {
          trendColor = 'text-rose-600 dark:text-rose-400';
          trendBg = 'bg-rose-50 dark:bg-rose-500/10';
        }

        return (
          <div 
            key={metric.id || index} 
            className="bg-card border border-border rounded-xl p-6 shadow-sm hover:shadow-md transition-all duration-200 flex flex-col group"
          >
            <div className="flex justify-between items-start">
              <p className="text-muted-foreground font-body text-sm font-medium tracking-wide">
                {metric.label}
              </p>
              <div className="p-2.5 bg-primary/10 text-primary rounded-lg group-hover:bg-primary group-hover:text-white transition-colors duration-200">
                <IconComponent className="w-5 h-5" />
              </div>
            </div>
            
            <div className="mt-4">
              <h3 className="text-foreground font-display text-3xl font-bold tracking-tight">
                {metric.value}
              </h3>
            </div>
            
            <div className="mt-4 flex items-center text-sm font-body">
              <span className={`flex items-center font-medium px-2 py-1 rounded-md ${trendBg} ${trendColor}`}>
                {isNegative ? (
                  <TrendingDown className="w-4 h-4 mr-1" />
                ) : (
                  <TrendingUp className="w-4 h-4 mr-1" />
                )}
                {metric.trend}
              </span>
              <span className="text-muted-foreground ml-3 truncate text-xs font-medium uppercase tracking-wider">
                {metric.detail}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}