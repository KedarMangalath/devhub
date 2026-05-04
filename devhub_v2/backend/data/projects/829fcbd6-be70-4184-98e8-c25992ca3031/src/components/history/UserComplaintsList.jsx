import React, { useState, useMemo } from 'react';
import { Clock, CheckCircle, AlertCircle, ChevronRight, Search, Filter } from 'lucide-react';
import { Link } from 'react-router-dom';

// Fallback data to ensure zero empty states if props are missing
const defaultComplaints = [
  {
    id: 'CMP-2023-8912',
    title: 'Bribery Request for Building Permit',
    department: 'Local Self Govt (LSGD)',
    location: 'Kochi Municipal Corporation',
    status: 'Investigating',
    date: '2023-10-15T10:30:00Z',
    lastUpdate: '2023-10-22T14:15:00Z',
    aiConfidence: 92
  },
  {
    id: 'CMP-2023-8845',
    title: 'Service Denial at Village Office',
    department: 'Revenue Department',
    location: 'Thiruvananthapuram Taluk',
    status: 'Resolved',
    date: '2023-09-28T09:15:00Z',
    lastUpdate: '2023-10-10T11:00:00Z',
    aiConfidence: 85
  },
  {
    id: 'CMP-2023-9001',
    title: 'Fraudulent Road Contract Allocation',
    department: 'Public Works (PWD)',
    location: 'Kozhikode District',
    status: 'Pending',
    date: '2023-10-24T08:45:00Z',
    lastUpdate: '2023-10-24T08:45:00Z',
    aiConfidence: 78
  },
  {
    id: 'CMP-2023-8722',
    title: 'Disproportionate Assets in RTO',
    department: 'Motor Vehicles (MVD)',
    location: 'Thrissur RTO',
    status: 'High Risk',
    date: '2023-08-12T14:20:00Z',
    lastUpdate: '2023-10-20T09:30:00Z',
    aiConfidence: 96
  }
];

const getStatusConfig = (status) => {
  const normalizedStatus = status?.toLowerCase() || 'pending';
  switch (normalizedStatus) {
    case 'resolved':
      return { 
        color: 'text-emerald-500 dark:text-emerald-400', 
        bg: 'bg-emerald-50 dark:bg-emerald-400/10', 
        border: 'border-emerald-200 dark:border-emerald-400/20', 
        icon: CheckCircle 
      };
    case 'investigating':
    case 'in progress':
      return { 
        color: 'text-amber-600 dark:text-amber-400', 
        bg: 'bg-amber-50 dark:bg-amber-400/10', 
        border: 'border-amber-200 dark:border-amber-400/20', 
        icon: Clock 
      };
    case 'high risk':
    case 'action required':
      return { 
        color: 'text-rose-600 dark:text-rose-400', 
        bg: 'bg-rose-50 dark:bg-rose-400/10', 
        border: 'border-rose-200 dark:border-rose-400/20', 
        icon: AlertCircle 
      };
    default:
      return { 
        color: 'text-blue-600 dark:text-blue-400', 
        bg: 'bg-blue-50 dark:bg-blue-400/10', 
        border: 'border-blue-200 dark:border-blue-400/20', 
        icon: Clock 
      };
  }
};

export default function UserComplaintsList({ complaints = [] }) {
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');

  // Ensure we always have data to render
  const activeData = complaints && complaints.length > 0 ? complaints : defaultComplaints;

  const filteredComplaints = useMemo(() => {
    return activeData.filter(complaint => {
      const matchesSearch = 
        (complaint.title || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
        (complaint.id || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
        (complaint.department || '').toLowerCase().includes(searchTerm.toLowerCase());
      
      const matchesStatus = 
        statusFilter === 'all' || 
        (complaint.status || '').toLowerCase() === statusFilter.toLowerCase();
      
      return matchesSearch && matchesStatus;
    });
  }, [activeData, searchTerm, statusFilter]);

  const formatDate = (dateString) => {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleDateString('en-IN', {
      day: 'numeric',
      month: 'short',
      year: 'numeric'
    });
  };

  return (
    <div className="w-full space-y-6">
      {/* Controls Section */}
      <div className="flex flex-col sm:flex-row gap-4 bg-card p-4 rounded-xl border border-border shadow-sm">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search by ID, title, or department..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-4 py-2.5 bg-background border border-border rounded-lg text-foreground focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary transition-all font-body"
          />
        </div>
        <div className="relative min-w-[200px]">
          <Filter className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground pointer-events-none" />
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="w-full pl-10 pr-8 py-2.5 bg-background border border-border rounded-lg text-foreground appearance-none focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary transition-all font-body cursor-pointer"
          >
            <option value="all">All Statuses</option>
            <option value="pending">Pending</option>
            <option value="investigating">Investigating</option>
            <option value="resolved">Resolved</option>
            <option value="high risk">High Risk</option>
          </select>
          <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none">
            <ChevronRight className="w-4 h-4 text-muted-foreground rotate-90" />
          </div>
        </div>
      </div>

      {/* List Section */}
      <div className="space-y-4">
        {filteredComplaints.map((complaint) => {
          const statusStyle = getStatusConfig(complaint.status);
          const StatusIcon = statusStyle.icon;

          return (
            <div 
              key={complaint.id} 
              className="group bg-card border border-border rounded-xl p-5 sm:p-6 hover:border-primary/50 transition-all duration-300 shadow-sm hover:shadow-md relative overflow-hidden"
            >
              {/* Subtle gradient accent on hover */}
              <div className="absolute inset-y-0 left-0 w-1 bg-gradient-to-b from-primary to-accent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />

              <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-6">
                
                {/* Left side: Main Info */}
                <div className="space-y-4 flex-1">
                  <div className="flex flex-wrap items-center gap-3">
                    <span className="text-xs font-mono font-medium text-muted-foreground bg-secondary px-2.5 py-1 rounded-md border border-border">
                      {complaint.id}
                    </span>
                    <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold border ${statusStyle.bg} ${statusStyle.color} ${statusStyle.border}`}>
                      <StatusIcon className="w-3.5 h-3.5" />
                      {complaint.status}
                    </span>
                    <span className="text-sm text-muted-foreground font-body flex items-center gap-1.5">
                      <Clock className="w-4 h-4" />
                      Submitted: {formatDate(complaint.date)}
                    </span>
                  </div>

                  <div>
                    <h3 className="text-xl font-display font-semibold text-foreground group-hover:text-primary transition-colors">
                      {complaint.title}
                    </h3>
                    <div className="flex flex-wrap items-center gap-x-6 gap-y-2 mt-2 text-sm font-body">
                      <p className="text-muted-foreground">
                        Department: <span className="text-foreground font-medium">{complaint.department}</span>
                      </p>
                      <p className="text-muted-foreground">
                        Location: <span className="text-foreground font-medium">{complaint.location}</span>
                      </p>
                    </div>
                  </div>
                </div>

                {/* Right side: Actions & Meta */}
                <div className="flex flex-row lg:flex-col items-center lg:items-end justify-between lg:justify-center gap-4 border-t lg:border-t-0 lg:border-l border-border pt-4 lg:pt-0 lg:pl-6 min-w-[200px]">
                  <div className="text-left lg:text-right w-full">
                    <p className="text-xs text-muted-foreground font-body mb-1 uppercase tracking-wider font-semibold">Last Updated</p>
                    <p className="text-sm font-medium text-foreground font-body">
                      {formatDate(complaint.lastUpdate)}
                    </p>
                  </div>
                  
                  <Link
                    to={`/complaint/${complaint.id}`}
                    className="inline-flex items-center justify-center gap-2 w-full lg:w-auto px-5 py-2.5 bg-primary/10 text-primary hover:bg-primary hover:text-primary-foreground rounded-lg font-medium transition-colors text-sm whitespace-nowrap"
                  >
                    View Updates
                    <ChevronRight className="w-4 h-4" />
                  </Link>
                </div>

              </div>
            </div>
          );
        })}

        {/* Empty State (only shows if filters yield 0 results) */}
        {filteredComplaints.length === 0 && (
          <div className="text-center py-16 bg-card border border-border rounded-xl shadow-sm">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-secondary mb-4">
              <AlertCircle className="w-8 h-8 text-muted-foreground" />
            </div>
            <h3 className="text-xl font-display font-semibold text-foreground mb-2">No complaints found</h3>
            <p className="text-muted-foreground font-body max-w-md mx-auto">
              We couldn't find any complaints matching your current search and filter criteria. Try adjusting them to see more results.
            </p>
            <button 
              onClick={() => { setSearchTerm(''); setStatusFilter('all'); }}
              className="mt-6 px-4 py-2 bg-secondary text-foreground hover:bg-border rounded-lg font-medium transition-colors text-sm"
            >
              Clear Filters
            </button>
          </div>
        )}
      </div>
    </div>
  );
}