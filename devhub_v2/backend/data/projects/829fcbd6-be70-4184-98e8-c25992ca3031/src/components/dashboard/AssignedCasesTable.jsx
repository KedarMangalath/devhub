import { useState, useMemo } from 'react'
import { ArrowUpDown, Eye, Edit, Search, Filter } from 'lucide-react'
import { Link } from 'react-router-dom'

// Fallback mock data to ensure zero empty states if props are not provided
const defaultCases = [
  { id: 'VIG-2023-089', title: 'Bribery Request for Building Permit', department: 'Local Self Govt (LSGD)', riskLevel: 'High', status: 'Investigating', date: '2023-10-24' },
  { id: 'VIG-2023-092', title: 'Disproportionate Assets in RTO', department: 'Motor Vehicles (MVD)', riskLevel: 'High', status: 'Pending Review', date: '2023-10-22' },
  { id: 'VIG-2023-104', title: 'Service Denial at Village Office', department: 'Revenue Department', riskLevel: 'Medium', status: 'Investigating', date: '2023-10-20' },
  { id: 'VIG-2023-115', title: 'Fraudulent Road Contract Allocation', department: 'Public Works (PWD)', riskLevel: 'High', status: 'Resolved', date: '2023-10-15' },
  { id: 'VIG-2023-128', title: 'Medicine Shortage in Govt Hospital', department: 'Health Services', riskLevel: 'Low', status: 'Investigating', date: '2023-10-10' },
  { id: 'VIG-2023-133', title: 'Illegal Sand Mining Nexus', department: 'Kerala Police', riskLevel: 'High', status: 'Investigating', date: '2023-10-08' },
  { id: 'VIG-2023-142', title: 'Ration Card Issuance Delay', department: 'Civil Supplies', riskLevel: 'Low', status: 'Pending Review', date: '2023-10-05' },
];

export default function AssignedCasesTable({ cases = defaultCases }) {
  const [sortConfig, setSortConfig] = useState({ key: 'date', direction: 'desc' });
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('All');

  const handleSort = (key) => {
    let direction = 'asc';
    if (sortConfig.key === key && sortConfig.direction === 'asc') {
      direction = 'desc';
    }
    setSortConfig({ key, direction });
  };

  const processedCases = useMemo(() => {
    if (!cases) return [];
    
    let filtered = cases.filter(c => {
      const searchLower = searchTerm.toLowerCase();
      const matchesSearch = 
        (c.title && c.title.toLowerCase().includes(searchLower)) ||
        (c.id && c.id.toLowerCase().includes(searchLower)) ||
        (c.department && c.department.toLowerCase().includes(searchLower));
      
      const matchesStatus = statusFilter === 'All' || c.status === statusFilter;
      
      return matchesSearch && matchesStatus;
    });

    filtered.sort((a, b) => {
      if (a[sortConfig.key] < b[sortConfig.key]) {
        return sortConfig.direction === 'asc' ? -1 : 1;
      }
      if (a[sortConfig.key] > b[sortConfig.key]) {
        return sortConfig.direction === 'asc' ? 1 : -1;
      }
      return 0;
    });

    return filtered;
  }, [cases, searchTerm, statusFilter, sortConfig]);

  const getRiskBadge = (risk) => {
    const styles = {
      'High': 'bg-red-500/10 text-red-500 border-red-500/20',
      'Medium': 'bg-amber-500/10 text-amber-500 border-amber-500/20',
      'Low': 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20'
    };
    const style = styles[risk] || 'bg-secondary text-muted-foreground border-border';
    return (
      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${style}`}>
        {risk}
      </span>
    );
  };

  const getStatusBadge = (status) => {
    const styles = {
      'Investigating': 'bg-blue-500/10 text-blue-500 border-blue-500/20',
      'Resolved': 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20',
      'Pending Review': 'bg-amber-500/10 text-amber-500 border-amber-500/20'
    };
    const style = styles[status] || 'bg-secondary text-muted-foreground border-border';
    return (
      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${style}`}>
        {status}
      </span>
    );
  };

  const SortIcon = ({ columnKey }) => {
    if (sortConfig.key !== columnKey) {
      return <ArrowUpDown size={14} className="text-muted-foreground/50 opacity-0 group-hover:opacity-100 transition-opacity" />;
    }
    return <ArrowUpDown size={14} className="text-primary" />;
  };

  return (
    <div className="bg-card border border-border rounded-xl shadow-sm overflow-hidden flex flex-col font-body">
      {/* Table Header Controls */}
      <div className="p-5 border-b border-border flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 bg-card/50">
        <div>
          <h3 className="font-display text-lg font-semibold text-foreground">Assigned Cases</h3>
          <p className="text-sm text-muted-foreground mt-1">Manage and track your active investigations.</p>
        </div>
        
        <div className="flex flex-col sm:flex-row items-center gap-3 w-full sm:w-auto">
          <div className="relative w-full sm:w-64">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <Search size={16} className="text-muted-foreground" />
            </div>
            <input
              type="text"
              placeholder="Search ID, title, dept..."
              className="block w-full pl-10 pr-3 py-2 border border-border rounded-lg leading-5 bg-background text-foreground placeholder-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary sm:text-sm transition-colors"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>
          
          <div className="relative w-full sm:w-auto">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <Filter size={16} className="text-muted-foreground" />
            </div>
            <select
              className="block w-full pl-10 pr-8 py-2 border border-border rounded-lg leading-5 bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary sm:text-sm transition-colors appearance-none cursor-pointer"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            >
              <option value="All">All Statuses</option>
              <option value="Investigating">Investigating</option>
              <option value="Pending Review">Pending Review</option>
              <option value="Resolved">Resolved</option>
            </select>
          </div>
        </div>
      </div>

      {/* Data Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse whitespace-nowrap">
          <thead>
            <tr className="bg-secondary/30 border-b border-border">
              <th 
                className="p-4 font-medium text-xs uppercase tracking-wider text-muted-foreground cursor-pointer group hover:bg-secondary/50 transition-colors"
                onClick={() => handleSort('id')}
              >
                <div className="flex items-center gap-2">
                  Case ID <SortIcon columnKey="id" />
                </div>
              </th>
              <th 
                className="p-4 font-medium text-xs uppercase tracking-wider text-muted-foreground cursor-pointer group hover:bg-secondary/50 transition-colors"
                onClick={() => handleSort('title')}
              >
                <div className="flex items-center gap-2">
                  Title <SortIcon columnKey="title" />
                </div>
              </th>
              <th 
                className="p-4 font-medium text-xs uppercase tracking-wider text-muted-foreground cursor-pointer group hover:bg-secondary/50 transition-colors"
                onClick={() => handleSort('department')}
              >
                <div className="flex items-center gap-2">
                  Department <SortIcon columnKey="department" />
                </div>
              </th>
              <th 
                className="p-4 font-medium text-xs uppercase tracking-wider text-muted-foreground cursor-pointer group hover:bg-secondary/50 transition-colors"
                onClick={() => handleSort('riskLevel')}
              >
                <div className="flex items-center gap-2">
                  Risk Level <SortIcon columnKey="riskLevel" />
                </div>
              </th>
              <th 
                className="p-4 font-medium text-xs uppercase tracking-wider text-muted-foreground cursor-pointer group hover:bg-secondary/50 transition-colors"
                onClick={() => handleSort('status')}
              >
                <div className="flex items-center gap-2">
                  Status <SortIcon columnKey="status" />
                </div>
              </th>
              <th 
                className="p-4 font-medium text-xs uppercase tracking-wider text-muted-foreground cursor-pointer group hover:bg-secondary/50 transition-colors"
                onClick={() => handleSort('date')}
              >
                <div className="flex items-center gap-2">
                  Date <SortIcon columnKey="date" />
                </div>
              </th>
              <th className="p-4 font-medium text-xs uppercase tracking-wider text-muted-foreground text-right">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {processedCases.length > 0 ? (
              processedCases.map((c) => (
                <tr key={c.id} className="hover:bg-secondary/20 transition-colors group">
                  <td className="p-4 text-sm font-medium text-foreground">
                    <Link to={`/complaint/${c.id}`} className="hover:text-primary transition-colors">
                      {c.id}
                    </Link>
                  </td>
                  <td className="p-4 text-sm text-foreground max-w-[250px] truncate" title={c.title}>
                    {c.title}
                  </td>
                  <td className="p-4 text-sm text-muted-foreground">
                    {c.department}
                  </td>
                  <td className="p-4">
                    {getRiskBadge(c.riskLevel)}
                  </td>
                  <td className="p-4">
                    {getStatusBadge(c.status)}
                  </td>
                  <td className="p-4 text-sm text-muted-foreground">
                    {new Date(c.date).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })}
                  </td>
                  <td className="p-4 text-right">
                    <div className="flex items-center justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                      <Link 
                        to={`/complaint/${c.id}`} 
                        className="p-1.5 text-muted-foreground hover:text-primary hover:bg-primary/10 rounded-md transition-colors"
                        title="View Details"
                      >
                        <Eye size={18} />
                      </Link>
                      <button 
                        className="p-1.5 text-muted-foreground hover:text-accent hover:bg-accent/10 rounded-md transition-colors"
                        title="Update Status"
                      >
                        <Edit size={18} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={7} className="p-8 text-center text-muted-foreground">
                  <div className="flex flex-col items-center justify-center gap-2">
                    <Search size={32} className="text-muted-foreground/50 mb-2" />
                    <p className="text-base font-medium text-foreground">No cases found</p>
                    <p className="text-sm">Try adjusting your search or filter criteria.</p>
                    <button 
                      onClick={() => { setSearchTerm(''); setStatusFilter('All'); }}
                      className="mt-4 px-4 py-2 bg-secondary text-foreground rounded-md text-sm font-medium hover:bg-secondary/80 transition-colors"
                    >
                      Clear Filters
                    </button>
                  </div>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      
      {/* Pagination Footer (Mocked) */}
      <div className="p-4 border-t border-border bg-card/50 flex items-center justify-between text-sm text-muted-foreground">
        <div>
          Showing <span className="font-medium text-foreground">{processedCases.length > 0 ? 1 : 0}</span> to <span className="font-medium text-foreground">{processedCases.length}</span> of <span className="font-medium text-foreground">{cases.length}</span> results
        </div>
        <div className="flex gap-1">
          <button className="px-3 py-1 border border-border rounded-md hover:bg-secondary transition-colors disabled:opacity-50 disabled:cursor-not-allowed" disabled>
            Previous
          </button>
          <button className="px-3 py-1 border border-border rounded-md hover:bg-secondary transition-colors disabled:opacity-50 disabled:cursor-not-allowed" disabled>
            Next
          </button>
        </div>
      </div>
    </div>
  );
}