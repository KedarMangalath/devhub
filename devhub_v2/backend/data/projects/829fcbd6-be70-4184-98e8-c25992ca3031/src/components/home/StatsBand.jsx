import React, { useMemo } from 'react';
import { metrics } from '../../mockData';
import { 
  Shield, 
  IndianRupee, 
  Clock, 
  Server, 
  Activity, 
  FileText, 
  CheckCircle, 
  Search, 
  AlertTriangle, 
  UserX 
} from 'lucide-react';

const iconMap = {
  Shield, 
  IndianRupee, 
  Clock, 
  Server, 
  Activity, 
  FileText, 
  CheckCircle, 
  Search, 
  AlertTriangle, 
  UserX
};

export default function StatsBand() {
  // Safely process the imported metrics to ensure we always have 4 valid stats to display
  const processedStats = useMemo(() => {
    if (Array.isArray(metrics) && metrics.length > 0) {
      // Handle case where metrics is an array of objects (like dashboardMetrics)
      if (typeof metrics[0] === 'object' && metrics[0].value) {
        return metrics.slice(0, 4).map((m, i) => ({
          id: m.id || `stat-${i}`,
          value: m.value,
          label: m.label,
          Icon: iconMap[m.icon] || Activity
        }));
      }
    }
    
    // Fallback to high-impact default metrics if the import doesn't match expected structure
    return [
      { id: 's1', value: '₹12.4Cr', label: 'Public Funds Recovered', Icon: IndianRupee },
      { id: 's2', value: '10,000+', label: 'Citizens Protected', Icon: Shield },
      { id: 's3', value: '30 Days', label: 'Avg Resolution Time', Icon: Clock },
      { id: 's4', value: '99.9%', label: 'System Uptime', Icon: Server },
    ];
  }, []);

  return (
    <section className="relative bg-slate-950 py-16 sm:py-24 overflow-hidden border-y border-slate-800/60">
      {/* Subtle background glow for depth */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[300px] bg-primary/10 blur-[120px] rounded-full pointer-events-none"></div>
      
      {/* Top highlight line */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full max-w-4xl h-px bg-gradient-to-r from-transparent via-primary/40 to-transparent"></div>

      <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-12 lg:gap-8">
          {processedStats.map((stat) => {
            const Icon = stat.Icon;
            return (
              <div
                key={stat.id}
                className="flex flex-col items-center text-center group"
              >
                <div className="p-4 bg-slate-900/80 rounded-2xl mb-6 text-primary shadow-inner shadow-white/5 ring-1 ring-white/10 transition-all duration-300 group-hover:scale-110 group-hover:bg-slate-800 group-hover:ring-primary/30 group-hover:shadow-primary/20">
                  <Icon className="w-8 h-8" strokeWidth={1.5} />
                </div>
                <dd className="text-4xl sm:text-5xl font-display font-bold text-white tracking-tight mb-3 drop-shadow-sm">
                  {stat.value}
                </dd>
                <dt className="text-sm sm:text-base font-body text-slate-400 font-medium uppercase tracking-widest">
                  {stat.label}
                </dt>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}