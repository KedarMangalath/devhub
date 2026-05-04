import React, { useMemo } from 'react';
import { timelineEvents } from '../../mockData';
import { Link as LinkIcon, Clock, User } from 'lucide-react';

export default function BlockchainTimeline({ complaintId }) {
  // Filter and sort events: newest first
  const events = useMemo(() => {
    if (!complaintId) return [];
    return timelineEvents
      .filter((event) => event.complaint_id === complaintId)
      .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
  }, [complaintId]);

  const formatDate = (dateString) => {
    const options = { 
      year: 'numeric', 
      month: 'short', 
      day: 'numeric', 
      hour: '2-digit', 
      minute: '2-digit' 
    };
    return new Date(dateString).toLocaleDateString('en-IN', options);
  };

  if (events.length === 0) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-8 text-center">
        <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-slate-50 mb-4">
          <LinkIcon className="w-6 h-6 text-slate-400" />
        </div>
        <h3 className="text-sm font-medium text-slate-900 mb-1">No Audit Trail Found</h3>
        <p className="text-sm text-slate-500">
          Timeline events will appear here once actions are taken on this complaint.
        </p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
      <div className="px-6 py-5 border-b border-slate-200 bg-slate-50/50 flex items-center justify-between">
        <div>
          <h3 className="text-base font-semibold text-slate-900">Immutable Audit Trail</h3>
          <p className="text-xs text-slate-500 mt-1">Cryptographically secured timeline of all actions</p>
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 bg-[#1d4ed8]/10 text-[#1d4ed8] rounded-full text-xs font-medium">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#1d4ed8] opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-[#1d4ed8]"></span>
          </span>
          Network Synced
        </div>
      </div>

      <div className="p-6">
        <div className="relative border-l-2 border-slate-100 ml-3 space-y-8">
          {events.map((event, index) => {
            const isLatest = index === 0;
            
            return (
              <div key={event.id} className="relative pl-8 group">
                {/* Timeline Dot */}
                <div className={`absolute -left-[9px] top-1.5 h-4 w-4 rounded-full border-2 bg-white transition-colors duration-200 ${
                  isLatest 
                    ? 'border-[#1d4ed8] shadow-[0_0_0_4px_rgba(4,120,87,0.1)]' 
                    : 'border-slate-300 group-hover:border-[#1d4ed8]'
                }`} />

                <div className="flex flex-col gap-2.5">
                  {/* Action Header */}
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <h4 className={`text-sm font-medium ${isLatest ? 'text-slate-900' : 'text-slate-700'}`}>
                      {event.action}
                    </h4>
                    <div className="flex items-center gap-1.5 text-xs text-slate-500 whitespace-nowrap">
                      <Clock className="w-3.5 h-3.5" />
                      <time dateTime={event.timestamp}>{formatDate(event.timestamp)}</time>
                    </div>
                  </div>

                  {/* Actor Info */}
                  <div className="flex items-center gap-2 text-xs text-slate-600">
                    <User className="w-3.5 h-3.5 text-slate-400" />
                    <span>{event.actor}</span>
                  </div>

                  {/* Notes (if any) */}
                  {event.notes && (
                    <p className="text-sm text-slate-600 bg-slate-50 p-3 rounded-md border border-slate-100">
                      {event.notes}
                    </p>
                  )}

                  {/* Blockchain Hash Badge */}
                  <div className="mt-1 inline-flex items-center gap-2 px-2.5 py-1.5 rounded-md bg-slate-50 border border-slate-200 w-fit group-hover:bg-white group-hover:border-slate-300 transition-colors">
                    <LinkIcon className="w-3.5 h-3.5 text-[#1d4ed8]" />
                    <span className="text-[11px] font-mono text-slate-500 tracking-tight">
                      Tx: {event.blockchain_hash}
                    </span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}