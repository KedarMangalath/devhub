import React from 'react';
import { Link } from 'react-router-dom';
import { MapPin, Calendar, ShieldAlert } from 'lucide-react';

const StatusBadge = ({ status }) => {
  const getStatusStyles = (status) => {
    const normalizedStatus = (status || '').toLowerCase();
    
    if (normalizedStatus.includes('resolved') || normalizedStatus.includes('closed')) {
      return 'bg-emerald-100 text-emerald-800 border-emerald-200';
    }
    if (normalizedStatus.includes('investigating') || normalizedStatus.includes('progress')) {
      return 'bg-amber-100 text-amber-800 border-amber-200';
    }
    if (normalizedStatus.includes('pending') || normalizedStatus.includes('new')) {
      return 'bg-blue-100 text-blue-800 border-blue-200';
    }
    if (normalizedStatus.includes('rejected') || normalizedStatus.includes('dismissed')) {
      return 'bg-slate-100 text-slate-800 border-slate-200';
    }
    
    // Default fallback
    return 'bg-gray-100 text-gray-800 border-gray-200';
  };

  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${getStatusStyles(status)}`}>
      {status || 'Unknown'}
    </span>
  );
};

const formatDate = (dateString) => {
  if (!dateString) return 'Date unknown';
  try {
    const date = new Date(dateString);
    return new Intl.DateTimeFormat('en-IN', {
      day: 'numeric',
      month: 'short',
      year: 'numeric'
    }).format(date);
  } catch (e) {
    return dateString;
  }
};

export default function ComplaintGrid({ complaints = [] }) {
  if (!complaints || complaints.length === 0) {
    return (
      <div className="w-full py-12 bg-white rounded-xl border border-slate-200 border-dashed flex flex-col items-center justify-center text-center px-4">
        <div className="w-16 h-16 bg-slate-50 rounded-full flex items-center justify-center mb-4">
          <ShieldAlert className="w-8 h-8 text-slate-400" />
        </div>
        <h3 className="font-display text-lg font-medium text-slate-900 mb-1">No complaints found</h3>
        <p className="font-body text-slate-500 max-w-sm">
          We couldn't find any complaints matching your current filters. Try adjusting your search criteria.
        </p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      {complaints.map((complaint) => (
        <div 
          key={complaint.id} 
          className="bg-white rounded-xl border border-slate-200 shadow-[0_4px_6px_-1px_rgba(0,0,0,0.05)] hover:shadow-lg hover:border-[#059669]/30 transition-all duration-300 flex flex-col overflow-hidden group"
        >
          {/* Card Header */}
          <div className="p-5 flex-grow">
            <div className="flex justify-between items-start gap-4 mb-4">
              <h3 className="font-display font-semibold text-lg text-slate-900 line-clamp-2 group-hover:text-[#059669] transition-colors">
                {complaint.title || complaint.subject || 'Untitled Complaint'}
              </h3>
              <div className="flex-shrink-0 mt-1">
                <StatusBadge status={complaint.status} />
              </div>
            </div>

            {/* Card Body */}
            <div className="space-y-3 font-body text-sm text-slate-600">
              <div className="flex items-start gap-2.5">
                <MapPin className="w-4 h-4 text-slate-400 mt-0.5 flex-shrink-0" />
                <span className="line-clamp-1">
                  {complaint.district || complaint.location || complaint.department || 'Location not specified'}
                </span>
              </div>
              
              <div className="flex items-center gap-2.5">
                <Calendar className="w-4 h-4 text-slate-400 flex-shrink-0" />
                <span>{formatDate(complaint.date || complaint.createdAt || complaint.timestamp)}</span>
              </div>

              {/* Optional AI Risk Flag */}
              {(complaint.riskLevel === 'High' || complaint.aiFlagged) && (
                <div className="inline-flex items-center gap-1.5 mt-2 bg-rose-50 text-rose-700 px-2.5 py-1 rounded-md text-xs font-medium border border-rose-100">
                  <ShieldAlert className="w-3.5 h-3.5" />
                  High Priority Alert
                </div>
              )}
              
              {/* Optional Tracking ID */}
              {complaint.trackingId && (
                <div className="pt-2 mt-2 border-t border-slate-100">
                  <span className="text-xs text-slate-400 uppercase tracking-wider font-semibold">Tracking ID:</span>
                  <span className="ml-2 text-xs font-mono text-slate-700 bg-slate-100 px-1.5 py-0.5 rounded">
                    {complaint.trackingId}
                  </span>
                </div>
              )}
            </div>
          </div>

          {/* Card Footer */}
          <div className="bg-slate-50/80 px-5 py-3.5 border-t border-slate-100 mt-auto flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500">
              {complaint.category || 'General'}
            </span>
            <Link 
              to={`/complaint/${complaint.id}`} 
              className="text-[#059669] hover:text-[#047857] font-medium text-sm flex items-center gap-1 transition-colors"
            >
              View Details
              <span className="text-lg leading-none ml-0.5 group-hover:translate-x-1 transition-transform duration-200">&rsaquo;</span>
            </Link>
          </div>
        </div>
      ))}
    </div>
  );
}