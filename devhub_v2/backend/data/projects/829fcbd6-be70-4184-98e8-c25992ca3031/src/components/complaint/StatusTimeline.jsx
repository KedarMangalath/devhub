import React from 'react';
import { CheckCircle2, Clock, AlertCircle } from 'lucide-react';

const defaultLogs = [
  {
    id: 'log-1',
    status: 'Complaint Resolved',
    timestamp: '2023-10-25T14:30:00Z',
    description: 'Investigation concluded. Officer suspended and funds recovered.',
    type: 'success'
  },
  {
    id: 'log-2',
    status: 'Investigation Active',
    timestamp: '2023-10-20T09:15:00Z',
    description: 'Assigned to Inspector Priya. Field visit scheduled.',
    type: 'pending'
  },
  {
    id: 'log-3',
    status: 'AI Credibility Flag',
    timestamp: '2023-10-18T11:05:00Z',
    description: 'High confidence match with previous MVD bribery patterns.',
    type: 'alert'
  },
  {
    id: 'log-4',
    status: 'Complaint Submitted',
    timestamp: '2023-10-18T10:00:00Z',
    description: 'Encrypted payload received via secure portal.',
    type: 'success'
  }
];

const getIconConfig = (type) => {
  switch (type) {
    case 'success':
      return {
        Icon: CheckCircle2,
        colorClass: 'text-primary',
        bgClass: 'bg-primary/10',
        borderClass: 'border-primary/20'
      };
    case 'alert':
      return {
        Icon: AlertCircle,
        colorClass: 'text-accent',
        bgClass: 'bg-accent/10',
        borderClass: 'border-accent/20'
      };
    case 'pending':
    default:
      return {
        Icon: Clock,
        colorClass: 'text-blue-500',
        bgClass: 'bg-blue-500/10',
        borderClass: 'border-blue-500/20'
      };
  }
};

const formatDate = (dateString) => {
  const date = new Date(dateString);
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true
  }).format(date);
};

export default function StatusTimeline({ logs = defaultLogs }) {
  if (!logs || logs.length === 0) {
    logs = defaultLogs;
  }

  return (
    <div className="w-full">
      <div className="relative space-y-8 before:absolute before:inset-0 before:ml-5 before:-translate-x-px md:before:mx-auto md:before:translate-x-0 before:h-full before:w-0.5 before:bg-gradient-to-b before:from-border before:via-border before:to-transparent">
        {logs.map((log, index) => {
          const { Icon, colorClass, bgClass, borderClass } = getIconConfig(log.type);
          const isLatest = index === 0;

          return (
            <div key={log.id} className="relative flex items-center justify-between md:justify-normal md:odd:flex-row-reverse group is-active">
              {/* Icon Marker */}
              <div className={`flex items-center justify-center w-10 h-10 rounded-full border-4 border-background shrink-0 md:order-1 md:group-odd:-translate-x-1/2 md:group-even:translate-x-1/2 shadow-sm z-10 ${bgClass} ${colorClass}`}>
                <Icon className="w-5 h-5" />
                {isLatest && (
                  <span className={`absolute inset-0 rounded-full animate-ping opacity-20 ${bgClass}`}></span>
                )}
              </div>

              {/* Content Card */}
              <div className="w-[calc(100%-4rem)] md:w-[calc(50%-2.5rem)] p-4 rounded-xl border border-border bg-card shadow-sm transition-all duration-200 hover:shadow-md hover:border-muted">
                <div className="flex flex-col space-y-1.5">
                  <div className="flex items-center justify-between mb-1">
                    <span className={`text-xs font-semibold uppercase tracking-wider ${colorClass}`}>
                      {log.type === 'success' ? 'Completed' : log.type === 'alert' ? 'Attention' : 'In Progress'}
                    </span>
                    <time className="text-xs font-body text-muted-foreground">
                      {formatDate(log.timestamp)}
                    </time>
                  </div>
                  <h4 className="text-base font-display font-semibold text-foreground">
                    {log.status}
                  </h4>
                  <p className="text-sm font-body text-muted-foreground leading-relaxed">
                    {log.description}
                  </p>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}