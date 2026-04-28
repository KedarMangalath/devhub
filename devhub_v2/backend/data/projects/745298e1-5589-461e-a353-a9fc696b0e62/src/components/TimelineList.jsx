import React from 'react';
import { 
  Calendar, 
  Sparkles, 
  Pill, 
  Activity, 
  FileText, 
  Stethoscope,
  CheckCircle2,
  AlertCircle
} from 'lucide-react';

const getTypeConfig = (type) => {
  const normalizedType = (type || '').toLowerCase();
  
  if (normalizedType.includes('appointment') || normalizedType.includes('book')) {
    return { 
      Icon: Calendar, 
      colorClass: 'text-sky-600', 
      bgClass: 'bg-sky-50', 
      borderClass: 'border-sky-200' 
    };
  }
  if (normalizedType.includes('insight') || normalizedType.includes('ai')) {
    return { 
      Icon: Sparkles, 
      colorClass: 'text-emerald-600', 
      bgClass: 'bg-emerald-50', 
      borderClass: 'border-emerald-200' 
    };
  }
  if (normalizedType.includes('medication') || normalizedType.includes('prescription')) {
    return { 
      Icon: Pill, 
      colorClass: 'text-purple-600', 
      bgClass: 'bg-purple-50', 
      borderClass: 'border-purple-200' 
    };
  }
  if (normalizedType.includes('test') || normalizedType.includes('report')) {
    return { 
      Icon: FileText, 
      colorClass: 'text-amber-600', 
      bgClass: 'bg-amber-50', 
      borderClass: 'border-amber-200' 
    };
  }
  if (normalizedType.includes('consultation') || normalizedType.includes('visit')) {
    return { 
      Icon: Stethoscope, 
      colorClass: 'text-indigo-600', 
      bgClass: 'bg-indigo-50', 
      borderClass: 'border-indigo-200' 
    };
  }
  if (normalizedType.includes('alert') || normalizedType.includes('warning')) {
    return { 
      Icon: AlertCircle, 
      colorClass: 'text-rose-600', 
      bgClass: 'bg-rose-50', 
      borderClass: 'border-rose-200' 
    };
  }

  return { 
    Icon: Activity, 
    colorClass: 'text-slate-500', 
    bgClass: 'bg-slate-50', 
    borderClass: 'border-slate-200' 
  };
};

const formatTime = (dateStr) => {
  if (!dateStr) return '';
  try {
    const d = new Date(dateStr);
    return d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
  } catch (e) {
    return '';
  }
};

const formatDate = (dateStr) => {
  if (!dateStr) return '';
  try {
    const d = new Date(dateStr);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  } catch (e) {
    return '';
  }
};

export default function TimelineList({ items = [], className = '' }) {
  if (!items || items.length === 0) {
    return (
      <div className={`flex flex-col items-center justify-center py-12 px-4 text-center bg-white rounded-2xl border border-slate-200 shadow-sm ${className}`}>
        <div className="w-12 h-12 bg-slate-50 rounded-full flex items-center justify-center mb-4 border border-slate-100">
          <Activity className="w-6 h-6 text-slate-400" />
        </div>
        <h3 className="text-slate-900 font-display font-semibold mb-1">No recent activity</h3>
        <p className="text-sm text-slate-500 max-w-sm">
          Your history and upcoming events will appear here once you start using the platform.
        </p>
      </div>
    );
  }

  return (
    <div className={`relative ${className}`}>
      {/* Continuous vertical line */}
      <div 
        className="absolute left-5 top-5 bottom-5 w-px bg-slate-200 z-0" 
        aria-hidden="true" 
      />

      <div className="space-y-6">
        {items.map((item, index) => {
          const { Icon, colorClass, bgClass, borderClass } = getTypeConfig(item.type);
          const title = item.title || item.text || 'Activity Update';

          return (
            <div key={item.id || index} className="relative pl-14 group">
              {/* Timeline Node */}
              <div className={`absolute left-0 top-0 w-10 h-10 rounded-full border-2 flex items-center justify-center z-10 transition-colors duration-300 ${bgClass} ${borderClass} ${colorClass} group-hover:border-current group-hover:shadow-sm`}>
                <Icon className="w-4 h-4" />
              </div>

              {/* Content Card */}
              <div className="bg-white rounded-2xl border border-slate-100 p-4 sm:p-5 shadow-sm hover:shadow-md transition-all duration-300 group-hover:border-slate-200">
                <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3 mb-2">
                  <div className="flex-1">
                    <h4 className="text-sm sm:text-base font-semibold text-slate-900 font-display leading-tight">
                      {title}
                    </h4>
                    {item.description && (
                      <p className="text-sm text-slate-500 mt-1.5 leading-relaxed">
                        {item.description}
                      </p>
                    )}
                  </div>
                  
                  <div className="flex flex-row sm:flex-col items-center sm:items-end shrink-0 gap-2 sm:gap-1">
                    <span className="text-xs font-medium text-slate-600 bg-slate-50 px-2.5 py-1 rounded-full border border-slate-200 whitespace-nowrap">
                      {formatDate(item.date)}
                    </span>
                    <span className="text-xs text-slate-400 font-medium">
                      {formatTime(item.date)}
                    </span>
                  </div>
                </div>

                {item.status && (
                  <div className="mt-3 flex items-center gap-1.5">
                    {item.status.toLowerCase() === 'completed' && <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />}
                    <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium tracking-wide ${
                      item.status.toLowerCase() === 'completed' ? 'bg-emerald-50 text-emerald-700 border border-emerald-100' :
                      item.status.toLowerCase() === 'pending' ? 'bg-amber-50 text-amber-700 border border-amber-100' :
                      item.status.toLowerCase() === 'cancelled' ? 'bg-rose-50 text-rose-700 border border-rose-100' :
                      'bg-slate-50 text-slate-700 border border-slate-200'
                    }`}>
                      {item.status.charAt(0).toUpperCase() + item.status.slice(1)}
                    </span>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}