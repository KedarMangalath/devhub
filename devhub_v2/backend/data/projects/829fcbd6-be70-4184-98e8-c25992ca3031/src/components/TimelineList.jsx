import React, { useState } from 'react';
import { 
  CheckCircle, 
  AlertTriangle, 
  Search, 
  FileText, 
  ShieldCheck, 
  Clock, 
  ChevronDown, 
  ChevronUp,
  User,
  Link as LinkIcon,
  Database
} from 'lucide-react';

// Fallback inline Badge component in case components/ui/badge is missing from the environment
const Badge = ({ children, variant = 'default', className = '' }) => {
  const variants = {
    default: 'bg-slate-100 text-slate-800 border-slate-200',
    success: 'bg-emerald-100 text-emerald-800 border-emerald-200',
    warning: 'bg-amber-100 text-amber-800 border-amber-200',
    danger: 'bg-rose-100 text-rose-800 border-rose-200',
    info: 'bg-blue-100 text-blue-800 border-blue-200',
  };
  
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${variants[variant]} ${className}`}>
      {children}
    </span>
  );
};

const defaultTimelineEvents = [
  {
    id: 'evt-1',
    status: 'resolved',
    title: 'Case Closed & Funds Recovered',
    description: 'The investigation has been concluded. The accused officer has been suspended, and ₹2.4 Lakhs in misappropriated funds have been recovered and returned to the state treasury.',
    timestamp: '2023-10-28T14:30:00Z',
    icon: CheckCircle,
    details: {
      actor: 'Director General, Vigilance',
      actionTaken: 'Final report submitted to court. Suspension order issued.',
      blockchainTx: '0x8f2a...9c11',
      attachments: ['final_report.pdf', 'recovery_receipt.pdf']
    }
  },
  {
    id: 'evt-2',
    status: 'investigating',
    title: 'Blockchain Evidence Verification',
    description: 'Audio recordings and document scans submitted by the citizen have been cryptographically hashed and verified on the immutable ledger. Chain of custody established.',
    timestamp: '2023-10-25T09:15:00Z',
    icon: ShieldCheck,
    details: {
      actor: 'System AI & Forensics Team',
      actionTaken: 'SHA-256 hashes generated for 4 media files.',
      blockchainTx: '0x3a1b...7d22',
      attachments: ['hash_log.txt']
    }
  },
  {
    id: 'evt-3',
    status: 'investigating',
    title: 'Field Investigation Initiated',
    description: 'Inspector Priya has been assigned to the case. Initial covert surveillance of the Revenue Office in Kochi has commenced to verify the claims of systemic bribery.',
    timestamp: '2023-10-22T11:00:00Z',
    icon: Search,
    details: {
      actor: 'Inspector Priya, Kochi Unit',
      actionTaken: 'Surveillance authorized. Informants contacted.',
      blockchainTx: null,
      attachments: []
    }
  },
  {
    id: 'evt-4',
    status: 'high-risk',
    title: 'AI Credibility Flag: High Risk',
    description: 'The C3MS Predictive AI has analyzed the complaint text and cross-referenced it with historical data. High probability of organized syndicate activity detected in this department.',
    timestamp: '2023-10-20T16:45:00Z',
    icon: AlertTriangle,
    details: {
      actor: 'C3MS Predictive Engine',
      actionTaken: 'Priority escalated to Level 1. Alert sent to HQ.',
      blockchainTx: '0x1c4d...5e99',
      attachments: ['ai_risk_assessment.json']
    }
  },
  {
    id: 'evt-5',
    status: 'pending',
    title: 'Anonymous Complaint Submitted',
    description: 'A citizen submitted a detailed report regarding a bribe request for a building permit. Identity protected via zero-knowledge proof authentication.',
    timestamp: '2023-10-20T16:30:00Z',
    icon: FileText,
    details: {
      actor: 'Anonymous Citizen #8842',
      actionTaken: 'Complaint encrypted and stored in secure vault.',
      blockchainTx: '0x9b2f...1a44',
      attachments: ['encrypted_payload.dat']
    }
  }
];

const getStatusConfig = (status) => {
  switch (status) {
    case 'resolved':
      return { color: 'bg-emerald-500', badge: 'success', label: 'Resolved' };
    case 'investigating':
      return { color: 'bg-amber-500', badge: 'warning', label: 'Investigating' };
    case 'high-risk':
      return { color: 'bg-rose-500', badge: 'danger', label: 'High Risk' };
    case 'pending':
      return { color: 'bg-blue-500', badge: 'info', label: 'Pending' };
    default:
      return { color: 'bg-slate-500', badge: 'default', label: 'Update' };
  }
};

const formatDate = (dateString) => {
  const options = { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' };
  return new Date(dateString).toLocaleDateString('en-IN', options);
};

export default function TimelineList({ events = defaultTimelineEvents }) {
  const [expandedId, setExpandedId] = useState(null);

  const toggleExpand = (id) => {
    setExpandedId(expandedId === id ? null : id);
  };

  if (!events || events.length === 0) {
    return (
      <div className="p-8 text-center bg-card border border-border rounded-xl">
        <Clock className="w-12 h-12 text-muted-foreground mx-auto mb-4 opacity-50" />
        <h3 className="text-lg font-display font-medium text-foreground">No timeline events</h3>
        <p className="text-muted-foreground font-body mt-1">There is no history available for this item yet.</p>
      </div>
    );
  }

  return (
    <div className="w-full max-w-3xl mx-auto py-6">
      <div className="relative border-l-2 border-slate-200 dark:border-slate-800 ml-4 md:ml-6 space-y-8">
        {events.map((event, index) => {
          const isExpanded = expandedId === event.id;
          const statusConfig = getStatusConfig(event.status);
          const Icon = event.icon || Clock;
          const isLast = index === events.length - 1;

          return (
            <div key={event.id} className="relative pl-8 md:pl-10">
              {/* Timeline Dot */}
              <div className={`absolute -left-[9px] top-1.5 w-4 h-4 rounded-full border-2 border-white dark:border-slate-950 shadow-sm ${statusConfig.color} z-10`} />
              
              {/* Connector Line Extension (fixes gap at bottom if needed, though border-l handles most of it) */}
              {isLast && (
                <div className="absolute -left-[2px] top-4 bottom-0 w-1 bg-background z-0" />
              )}

              {/* Content Card */}
              <div 
                onClick={() => toggleExpand(event.id)}
                className={`
                  bg-card border border-border rounded-xl p-5 shadow-sm 
                  transition-all duration-200 cursor-pointer
                  hover:shadow-md hover:border-slate-300 dark:hover:border-slate-700
                  ${isExpanded ? 'ring-1 ring-primary/20' : ''}
                `}
              >
                {/* Header Row */}
                <div className="flex flex-col md:flex-row md:items-start justify-between gap-3 mb-3">
                  <div className="flex items-start gap-3">
                    <div className={`p-2 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 shrink-0 mt-0.5`}>
                      <Icon className="w-5 h-5" />
                    </div>
                    <div>
                      <h4 className="text-base font-display font-semibold text-foreground leading-tight">
                        {event.title}
                      </h4>
                      <div className="flex items-center gap-2 mt-1.5 text-xs font-body text-muted-foreground">
                        <Clock className="w-3.5 h-3.5" />
                        <span>{formatDate(event.timestamp)}</span>
                      </div>
                    </div>
                  </div>
                  
                  <div className="flex items-center justify-between md:justify-end w-full md:w-auto gap-3 pl-11 md:pl-0">
                    <Badge variant={statusConfig.badge}>
                      {statusConfig.label}
                    </Badge>
                    <button 
                      className="p-1 rounded-md hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400 transition-colors"
                      aria-label={isExpanded ? "Collapse details" : "Expand details"}
                    >
                      {isExpanded ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
                    </button>
                  </div>
                </div>

                {/* Body Text */}
                <p className={`text-sm font-body text-slate-600 dark:text-slate-400 leading-relaxed pl-11 md:pl-14 ${!isExpanded ? 'line-clamp-2' : ''}`}>
                  {event.description}
                </p>

                {/* Expanded Details */}
                {isExpanded && event.details && (
                  <div className="mt-5 pl-11 md:pl-14 pt-4 border-t border-slate-100 dark:border-slate-800 animate-in slide-in-from-top-2 fade-in duration-200">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      
                      {/* Actor / Action */}
                      <div className="space-y-3">
                        <div>
                          <span className="flex items-center gap-1.5 text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">
                            <User className="w-3.5 h-3.5" /> Logged By
                          </span>
                          <p className="text-sm font-medium text-foreground">{event.details.actor}</p>
                        </div>
                        <div>
                          <span className="flex items-center gap-1.5 text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">
                            <Database className="w-3.5 h-3.5" /> System Action
                          </span>
                          <p className="text-sm text-slate-600 dark:text-slate-400">{event.details.actionTaken}</p>
                        </div>
                      </div>

                      {/* Metadata / Attachments */}
                      <div className="space-y-3">
                        {event.details.blockchainTx && (
                          <div>
                            <span className="flex items-center gap-1.5 text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">
                              <LinkIcon className="w-3.5 h-3.5" /> Blockchain Tx Hash
                            </span>
                            <code className="text-xs bg-slate-100 dark:bg-slate-900 px-2 py-1 rounded text-primary font-mono">
                              {event.details.blockchainTx}
                            </code>
                          </div>
                        )}
                        
                        {event.details.attachments && event.details.attachments.length > 0 && (
                          <div>
                            <span className="flex items-center gap-1.5 text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">
                              <FileText className="w-3.5 h-3.5" /> Attachments
                            </span>
                            <div className="flex flex-wrap gap-2">
                              {event.details.attachments.map((file, i) => (
                                <span key={i} className="inline-flex items-center gap-1 text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 px-2 py-1 rounded-md text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors cursor-pointer">
                                  <FileText className="w-3 h-3" />
                                  {file}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>

                    </div>
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