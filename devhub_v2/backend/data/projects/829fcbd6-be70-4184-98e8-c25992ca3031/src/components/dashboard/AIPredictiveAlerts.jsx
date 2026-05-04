import React, { useState } from 'react';
import { BellRing, AlertTriangle } from 'lucide-react';

const defaultAlerts = [
  { 
    id: 'alt-1', 
    title: 'Anomaly Detected', 
    description: 'Unusual spike in PWD contract approvals in Kozhikode district over the last 48 hours.', 
    severity: 'High', 
    timestamp: '2 hours ago' 
  },
  { 
    id: 'alt-2', 
    title: 'Risk Pattern Identified', 
    description: 'Multiple anonymous reports matching known bribery patterns in MVD checkposts.', 
    severity: 'Medium', 
    timestamp: '5 hours ago' 
  },
  { 
    id: 'alt-3', 
    title: 'Data Discrepancy', 
    description: 'Mismatch in reported vs audited funds for LSGD project #882. Immediate review recommended.', 
    severity: 'High', 
    timestamp: '1 day ago' 
  },
  { 
    id: 'alt-4', 
    title: 'Trend Alert', 
    description: '20% increase in service denial complaints at Revenue offices in Thiruvananthapuram.', 
    severity: 'Medium', 
    timestamp: '2 days ago' 
  },
  { 
    id: 'alt-5', 
    title: 'Credibility Flag', 
    description: 'New evidence uploaded for Case #4419 has a 94% probability of being digitally altered.', 
    severity: 'High', 
    timestamp: '3 days ago' 
  }
];

export default function AIPredictiveAlerts({ alerts = defaultAlerts }) {
  const [activeFilter, setActiveFilter] = useState('All');

  const filteredAlerts = alerts.filter(alert => {
    if (activeFilter === 'All') return true;
    return alert.severity === activeFilter;
  });

  const getSeverityStyles = (severity) => {
    if (severity.toLowerCase() === 'high') {
      return {
        badge: 'bg-red-100 text-red-800 border-red-200',
        icon: 'text-red-600',
        bg: 'bg-red-50/40 border-red-100 hover:bg-red-50/80'
      };
    }
    return {
      badge: 'bg-amber-100 text-amber-800 border-amber-200',
      icon: 'text-amber-600',
      bg: 'bg-amber-50/40 border-amber-100 hover:bg-amber-50/80'
    };
  };

  return (
    <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden flex flex-col h-full">
      <div className="p-5 border-b border-border flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-secondary/20">
        <div className="flex items-center gap-3">
          <div className="p-2.5 bg-primary/10 rounded-lg">
            <BellRing className="w-5 h-5 text-primary" />
          </div>
          <div>
            <h3 className="font-display text-lg font-semibold text-foreground leading-tight">
              Predictive Alerts
            </h3>
            <p className="text-xs text-muted-foreground font-body mt-0.5">
              AI-generated risk indicators
            </p>
          </div>
        </div>
        
        <div className="flex gap-1 bg-secondary/50 p-1 rounded-lg border border-border self-start sm:self-auto">
          {['All', 'High', 'Medium'].map(filter => (
            <button
              key={filter}
              onClick={() => setActiveFilter(filter)}
              className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all duration-200 ${
                activeFilter === filter
                  ? 'bg-card text-foreground shadow-sm border border-border/50'
                  : 'text-muted-foreground hover:text-foreground hover:bg-secondary'
              }`}
            >
              {filter}
            </button>
          ))}
        </div>
      </div>

      <div className="p-5 flex-1 overflow-y-auto space-y-3 custom-scrollbar">
        {filteredAlerts.length > 0 ? (
          filteredAlerts.map((alert) => {
            const styles = getSeverityStyles(alert.severity);
            return (
              <div
                key={alert.id}
                className={`p-4 rounded-xl border transition-all duration-200 ${styles.bg} group cursor-pointer`}
              >
                <div className="flex items-start gap-3.5">
                  <div className={`mt-0.5 p-1.5 rounded-md bg-card shadow-sm border border-border/50 ${styles.icon}`}>
                    <AlertTriangle className="w-4 h-4" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between gap-2 mb-1.5">
                      <h4 className="font-display font-medium text-sm text-foreground truncate pr-2">
                        {alert.title}
                      </h4>
                      <span className={`shrink-0 text-[10px] uppercase tracking-wider font-bold px-2 py-0.5 rounded-full border ${styles.badge}`}>
                        {alert.severity}
                      </span>
                    </div>
                    <p className="text-sm text-muted-foreground line-clamp-2 mb-2.5 font-body leading-relaxed">
                      {alert.description}
                    </p>
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-medium text-muted-foreground/70">
                        {alert.timestamp}
                      </span>
                      <button className="text-xs font-medium text-primary opacity-0 group-hover:opacity-100 transition-opacity">
                        Investigate &rarr;
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            );
          })
        ) : (
          <div className="flex flex-col items-center justify-center h-40 text-center px-4 bg-secondary/10 rounded-xl border border-dashed border-border">
            <BellRing className="w-8 h-8 text-muted-foreground/40 mb-3" />
            <p className="text-sm font-medium text-foreground">No alerts found</p>
            <p className="text-xs text-muted-foreground mt-1">Try changing your filter criteria.</p>
          </div>
        )}
      </div>
    </div>
  );
}