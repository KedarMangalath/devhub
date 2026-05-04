import React from 'react';
import { 
  FileText, 
  CheckCircle, 
  Search, 
  IndianRupee, 
  Clock, 
  AlertTriangle, 
  UserX, 
  Server,
  TrendingUp,
  TrendingDown,
  Minus,
  Activity,
  Shield,
  ShoppingCart,
  BookOpen,
  TreePine,
  Wine,
  HardHat,
  Building,
  Car,
  HelpCircle
} from 'lucide-react';

const IconMap = {
  FileText,
  CheckCircle,
  Search,
  IndianRupee,
  Clock,
  AlertTriangle,
  UserX,
  Server,
  Activity,
  Shield,
  ShoppingCart,
  BookOpen,
  TreePine,
  Wine,
  HardHat,
  Building,
  Car
};

const toneConfig = {
  success: {
    bg: 'bg-emerald-100 dark:bg-emerald-500/10',
    text: 'text-emerald-600 dark:text-emerald-400',
    border: 'border-emerald-200 dark:border-emerald-500/20'
  },
  warning: {
    bg: 'bg-amber-100 dark:bg-amber-500/10',
    text: 'text-amber-600 dark:text-amber-400',
    border: 'border-amber-200 dark:border-amber-500/20'
  },
  danger: {
    bg: 'bg-rose-100 dark:bg-rose-500/10',
    text: 'text-rose-600 dark:text-rose-400',
    border: 'border-rose-200 dark:border-rose-500/20'
  },
  info: {
    bg: 'bg-blue-100 dark:bg-blue-500/10',
    text: 'text-blue-600 dark:text-blue-400',
    border: 'border-blue-200 dark:border-blue-500/20'
  },
  neutral: {
    bg: 'bg-slate-100 dark:bg-slate-800',
    text: 'text-slate-600 dark:text-slate-400',
    border: 'border-slate-200 dark:border-slate-700'
  }
};

export default function StatCard({ 
  label, 
  value, 
  detail, 
  icon, 
  tone = 'neutral', 
  trend, 
  className = '' 
}) {
  // Resolve the icon component from the string name, fallback to HelpCircle
  const IconComponent = IconMap[icon] || HelpCircle;

  // Auto-determine tone if not explicitly provided, based on icon or label context
  let activeTone = tone;
  if (tone === 'neutral') {
    if (icon === 'CheckCircle' || icon === 'IndianRupee') activeTone = 'success';
    if (icon === 'AlertTriangle' || icon === 'UserX') activeTone = 'warning';
    if (icon === 'Search' || icon === 'FileText') activeTone = 'info';
  }

  const currentTone = toneConfig[activeTone] || toneConfig.neutral;

  // Parse trend string (e.g., "+14%", "-5%", "0%") to determine direction and color
  let trendDirection = 'neutral';
  let trendValue = trend;
  
  if (trend) {
    if (trend.startsWith('+')) {
      trendDirection = 'up';
    } else if (trend.startsWith('-')) {
      trendDirection = 'down';
    }
  }

  const trendStyles = {
    up: {
      Icon: TrendingUp,
      color: 'text-emerald-600 dark:text-emerald-400',
      bg: 'bg-emerald-50 dark:bg-emerald-500/10'
    },
    down: {
      Icon: TrendingDown,
      color: 'text-rose-600 dark:text-rose-400',
      bg: 'bg-rose-50 dark:bg-rose-500/10'
    },
    neutral: {
      Icon: Minus,
      color: 'text-slate-500 dark:text-slate-400',
      bg: 'bg-slate-50 dark:bg-slate-800'
    }
  };

  const activeTrend = trendStyles[trendDirection];
  const TrendIcon = activeTrend.Icon;

  return (
    <div 
      className={`
        relative overflow-hidden rounded-xl 
        bg-white dark:bg-slate-900 
        border border-slate-200 dark:border-slate-800 
        p-6 shadow-sm hover:shadow-md transition-all duration-200
        ${className}
      `}
    >
      {/* Top decorative border based on tone */}
      <div className={`absolute top-0 left-0 right-0 h-1 ${currentTone.bg} opacity-50`} />

      <div className="flex items-start justify-between">
        <div className="space-y-2">
          <h3 className="text-sm font-medium text-slate-500 dark:text-slate-400 font-body tracking-wide">
            {label}
          </h3>
          <div className="text-3xl font-bold text-slate-900 dark:text-white font-display tracking-tight">
            {value}
          </div>
        </div>
        
        <div className={`p-3 rounded-lg ${currentTone.bg} ${currentTone.border} border`}>
          <IconComponent className={`w-5 h-5 ${currentTone.text}`} strokeWidth={2.5} />
        </div>
      </div>

      {(trend || detail) && (
        <div className="mt-4 flex items-center gap-2 text-sm font-body">
          {trend && (
            <span className={`
              flex items-center gap-1 px-2 py-0.5 rounded-md font-medium
              ${activeTrend.bg} ${activeTrend.color}
            `}>
              <TrendIcon className="w-3.5 h-3.5" strokeWidth={2.5} />
              {trendValue}
            </span>
          )}
          
          {detail && (
            <span className="text-slate-500 dark:text-slate-400 truncate">
              {detail}
            </span>
          )}
        </div>
      )}
    </div>
  );
}