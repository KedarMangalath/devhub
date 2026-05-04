import React from 'react'
import { 
  CheckCircle, 
  FileText, 
  User, 
  ShieldCheck, 
  Clock, 
  AlertCircle, 
  Link as LinkIcon,
  FileDigit
} from 'lucide-react'

const defaultEvents = [
  {
    id: "EVT-001",
    action: "Complaint Filed",
    actor: "Citizen (Anonymous)",
    timestamp: "2023-10-25T10:15:00Z",
    description: "Initial complaint details and evidence uploaded securely.",
    blockchain_hash: "0x8f...3a9b"
  },
  {
    id: "EVT-002",
    action: "AI Triage Completed",
    actor: "System AI",
    timestamp: "2023-10-25T10:16:30Z",
    description: "Assigned High severity. Credibility score calculated at 92/100.",
    blockchain_hash: "0x2c...1f4e"
  },
  {
    id: "EVT-003",
    action: "Assigned to Officer",
    actor: "System Routing",
    timestamp: "2023-10-25T10:20:00Z",
    description: "Routed to Rajesh Kumar (Anti-Corruption Bureau).",
    blockchain_hash: "0x9a...7b2c"
  },
  {
    id: "EVT-004",
    action: "Investigation Initiated",
    actor: "Rajesh Kumar",
    timestamp: "2023-10-26T09:00:00Z",
    description: "Officer reviewed initial evidence and requested departmental records.",
    blockchain_hash: "0x4d...8e1a"
  }
];

const getIconForAction = (action) => {
  const lower = action.toLowerCase();
  if (lower.includes('filed') || lower.includes('submitted')) {
    return <FileText className="w-4 h-4 text-blue-600" />;
  }
  if (lower.includes('review') || lower.includes('investigat') || lower.includes('triage')) {
    return <Clock className="w-4 h-4 text-amber-600" />;
  }
  if (lower.includes('verif') || lower.includes('approv') || lower.includes('resolv')) {
    return <ShieldCheck className="w-4 h-4 text-blue-600" />;
  }
  if (lower.includes('assign') || lower.includes('rout')) {
    return <User className="w-4 h-4 text-indigo-600" />;
  }
  if (lower.includes('alert') || lower.includes('warn') || lower.includes('escalat')) {
    return <AlertCircle className="w-4 h-4 text-red-600" />;
  }
  return <CheckCircle className="w-4 h-4 text-slate-500" />;
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

export default function TimelineList({ events = defaultEvents, className = "" }) {
  const displayEvents = events && events.length > 0 ? events : defaultEvents;

  return (
    <div className={`flow-root ${className}`}>
      <ul role="list" className="-mb-8">
        {displayEvents.map((event, eventIdx) => (
          <li key={event.id}>
            <div className="relative pb-8">
              {eventIdx !== displayEvents.length - 1 ? (
                <span
                  className="absolute left-4 top-4 -ml-px h-full w-0.5 bg-slate-200"
                  aria-hidden="true"
                />
              ) : null}
              <div className="relative flex space-x-4">
                <div>
                  <span className="h-8 w-8 rounded-full bg-slate-50 border border-slate-200 flex items-center justify-center ring-4 ring-white shadow-sm">
                    {getIconForAction(event.action)}
                  </span>
                </div>
                <div className="flex min-w-0 flex-1 justify-between space-x-4 pt-1.5">
                  <div className="flex flex-col gap-1.5 w-full">
                    <div className="flex items-center justify-between">
                      <p className="text-sm font-medium text-slate-900">
                        {event.action}
                      </p>
                      <div className="whitespace-nowrap text-right text-xs text-slate-500">
                        {formatDate(event.timestamp)}
                      </div>
                    </div>
                    
                    <div className="flex items-center gap-2 text-xs text-slate-600">
                      <span className="font-medium text-slate-700">{event.actor}</span>
                      {event.blockchain_hash && (
                        <>
                          <span className="text-slate-300">&bull;</span>
                          <span className="inline-flex items-center gap-1 text-blue-700 bg-blue-50 px-1.5 py-0.5 rounded font-mono text-[10px] border border-blue-100">
                            <LinkIcon className="w-3 h-3" />
                            {event.blockchain_hash}
                          </span>
                        </>
                      )}
                    </div>

                    {event.description && (
                      <p className="text-sm text-slate-600 mt-1 bg-slate-50 p-3 rounded-md border border-slate-100">
                        {event.description}
                      </p>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}