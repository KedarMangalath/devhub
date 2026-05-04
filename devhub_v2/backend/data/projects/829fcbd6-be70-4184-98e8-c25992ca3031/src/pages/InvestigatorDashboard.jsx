import React, { useMemo, useState, useEffect } from 'react';
import { 
  Shield, 
  AlertTriangle, 
  Search, 
  Filter, 
  CheckCircle, 
  Clock, 
  Activity, 
  FileText, 
  User, 
  MapPin, 
  TrendingUp,
  TrendingDown,
  MoreVertical,
  ChevronRight,
  Download,
  Eye,
  MessageSquare,
  Calendar,
  Briefcase,
  BarChart3,
  Zap,
  X
} from 'lucide-react';

// Project Imports
import AppShell from '../components/AppShell';
import StatCard from '../components/StatCard';
import TabbedPanel from '../components/TabbedPanel';
import TimelineList from '../components/TimelineList';
import SearchFilterBar from '../components/SearchFilterBar';
import { dashboardMetrics, userProfile, messages, categories } from '../mockData';

// ============================================================================
// INLINE MOCK DATA (Augmenting imported data for rich dashboard experience)
// ============================================================================

const mockAssignedCases = [
  {
    id: 'CAS-2023-8901',
    title: 'Fraudulent Road Contract Allocation',
    department: 'Public Works (PWD)',
    location: 'Thiruvananthapuram',
    date: '2023-10-24',
    status: 'Investigating',
    riskLevel: 'High',
    evidenceCount: 12,
    aiConfidence: 94,
    description: 'Observed severe irregularities in the recent tender process for the NH-44 bypass. Documents suggest pre-approval of unqualified vendors linked to local officials.'
  },
  {
    id: 'CAS-2023-8892',
    title: 'Bribery Request for Building Permit',
    department: 'Local Self Govt (LSGD)',
    location: 'Kochi',
    date: '2023-10-22',
    status: 'Pending Review',
    riskLevel: 'Medium',
    evidenceCount: 3,
    aiConfidence: 78,
    description: 'Citizen reported a demand for ₹50,000 to clear a residential building permit that has been stalled for 6 months despite all paperwork being complete.'
  },
  {
    id: 'CAS-2023-8875',
    title: 'Disproportionate Assets - RTO Officer',
    department: 'Motor Vehicles (MVD)',
    location: 'Kozhikode',
    date: '2023-10-18',
    status: 'Active Surveillance',
    riskLevel: 'High',
    evidenceCount: 24,
    aiConfidence: 98,
    description: 'Anonymous tip regarding massive real estate purchases by a mid-level RTO officer, far exceeding known sources of income. AI flagged multiple shell company transactions.'
  },
  {
    id: 'CAS-2023-8850',
    title: 'Medical Supply Procurement Scam',
    department: 'Health Services',
    location: 'Thrissur',
    date: '2023-10-15',
    status: 'Resolved',
    riskLevel: 'Critical',
    evidenceCount: 45,
    aiConfidence: 99,
    description: 'Systemic overpricing of basic medical supplies during the last quarter. Audit revealed a 300% markup from a newly registered vendor.'
  },
  {
    id: 'CAS-2023-8841',
    title: 'Illegal Sand Mining Collusion',
    department: 'Revenue Department',
    location: 'Palakkad',
    date: '2023-10-10',
    status: 'Investigating',
    riskLevel: 'High',
    evidenceCount: 8,
    aiConfidence: 85,
    description: 'Reports of revenue officials turning a blind eye to illegal sand mining operations along the Bharathappuzha river in exchange for monthly payoffs.'
  },
  {
    id: 'CAS-2023-8822',
    title: 'Ration Card Distribution Anomalies',
    department: 'Civil Supplies',
    location: 'Kollam',
    date: '2023-10-05',
    status: 'Pending Review',
    riskLevel: 'Low',
    evidenceCount: 2,
    aiConfidence: 62,
    description: 'Multiple complaints regarding delays in issuing priority ration cards, with allegations of queue jumping for favored individuals.'
  }
];

const mockAIAlerts = [
  {
    id: 'ALT-001',
    type: 'Syndicate Activity Detected',
    target: 'PWD - Kochi Division',
    severity: 'Critical',
    timestamp: '10 mins ago',
    details: 'Pattern analysis indicates 4 recent complaints share identical vendor IP addresses and financial routing. High probability of organized bid-rigging.',
    actionRequired: 'Authorize deep financial audit'
  },
  {
    id: 'ALT-002',
    type: 'Evidence Tampering Attempt',
    target: 'Case CAS-2023-8875',
    severity: 'High',
    timestamp: '2 hours ago',
    details: 'Blockchain ledger detected an unauthorized attempt to modify uploaded audio evidence by an internal IP address.',
    actionRequired: 'Review access logs immediately'
  },
  {
    id: 'ALT-003',
    type: 'Anomalous Approval Spike',
    target: 'LSGD - Thrissur Corp',
    severity: 'Medium',
    timestamp: '1 day ago',
    details: 'Building permit approvals spiked by 400% in the last 48 hours compared to the 6-month average. Potential bulk clearance anomaly.',
    actionRequired: 'Schedule random sampling review'
  }
];

const departmentRiskData = categories.map((cat, index) => ({
  ...cat,
  riskScore: Math.floor(Math.random() * 60) + 40, // 40-100
  activeInvestigations: Math.floor(Math.random() * 20) + 1,
  trend: index % 2 === 0 ? 'up' : 'down'
})).sort((a, b) => b.riskScore - a.riskScore);

// ============================================================================
// INLINE UI COMPONENTS
// ============================================================================

const Badge = ({ children, variant = 'default', className = '' }) => {
  const variants = {
    default: 'bg-slate-100 text-slate-800 border-slate-200',
    success: 'bg-emerald-100 text-emerald-800 border-emerald-200',
    warning: 'bg-amber-100 text-amber-800 border-amber-200',
    danger: 'bg-rose-100 text-rose-800 border-rose-200',
    info: 'bg-blue-100 text-blue-800 border-blue-200',
    critical: 'bg-red-600 text-white border-red-700 animate-pulse',
  };
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${variants[variant]} ${className}`}>
      {children}
    </span>
  );
};

const Button = ({ children, variant = 'primary', size = 'md', className = '', onClick, icon: Icon }) => {
  const variants = {
    primary: 'bg-emerald-600 text-white hover:bg-emerald-700 shadow-sm',
    secondary: 'bg-white text-slate-700 border border-slate-300 hover:bg-slate-50',
    danger: 'bg-rose-600 text-white hover:bg-rose-700 shadow-sm',
    ghost: 'bg-transparent text-slate-600 hover:bg-slate-100',
  };
  const sizes = {
    sm: 'px-3 py-1.5 text-sm',
    md: 'px-4 py-2 text-sm',
    lg: 'px-6 py-3 text-base',
  };
  return (
    <button 
      onClick={onClick}
      className={`inline-flex items-center justify-center rounded-lg font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 ${variants[variant]} ${sizes[size]} ${className}`}
    >
      {Icon && <Icon className={`w-4 h-4 ${children ? 'mr-2' : ''}`} />}
      {children}
    </button>
  );
};

// ============================================================================
// MAIN PAGE COMPONENT
// ============================================================================

export default function InvestigatorDashboard() {
  // State
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [selectedCase, setSelectedCase] = useState(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [activeTab, setActiveTab] = useState('cases');

  // Derived Data: Filtered Cases
  const filteredCases = useMemo(() => {
    return mockAssignedCases.filter(c => {
      const matchesSearch = c.title.toLowerCase().includes(searchQuery.toLowerCase()) || 
                            c.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
                            c.department.toLowerCase().includes(searchQuery.toLowerCase());
      const matchesStatus = statusFilter === 'all' || c.status.toLowerCase().replace(' ', '-') === statusFilter;
      return matchesSearch && matchesStatus;
    });
  }, [searchQuery, statusFilter]);

  // Handlers
  const handleOpenModal = (caseData) => {
    setSelectedCase(caseData);
    setIsModalOpen(true);
    document.body.style.overflow = 'hidden';
  };

  const handleCloseModal = () => {
    setIsModalOpen(false);
    setTimeout(() => setSelectedCase(null), 300); // Wait for animation
    document.body.style.overflow = 'unset';
  };

  // Helper for status badges
  const getStatusVariant = (status) => {
    switch(status) {
      case 'Resolved': return 'success';
      case 'Investigating': return 'warning';
      case 'Active Surveillance': return 'danger';
      case 'Pending Review': return 'info';
      default: return 'default';
    }
  };

  const getRiskVariant = (risk) => {
    switch(risk) {
      case 'Critical': return 'critical';
      case 'High': return 'danger';
      case 'Medium': return 'warning';
      case 'Low': return 'success';
      default: return 'default';
    }
  };

  return (
    <AppShell>
      <div className="min-h-screen bg-slate-50 font-body pb-12">
        
        {/* ================= HEADER SECTION ================= */}
        <div className="bg-slate-900 text-white pt-12 pb-20 px-4 sm:px-6 lg:px-8 border-b border-slate-800">
          <div className="max-w-7xl mx-auto">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
              <div className="flex items-center gap-5">
                <img 
                  src={userProfile.avatar} 
                  alt={userProfile.name} 
                  className="w-16 h-16 rounded-full border-2 border-emerald-500 object-cover"
                />
                <div>
                  <h1 className="text-3xl font-display font-bold tracking-tight">
                    Welcome back, {userProfile.name}
                  </h1>
                  <p className="text-slate-400 mt-1 flex items-center gap-2">
                    <Briefcase className="w-4 h-4" />
                    {userProfile.role} • {userProfile.location}
                  </p>
                </div>
              </div>
              <div className="flex gap-3">
                <Button variant="secondary" icon={Download}>Export Report</Button>
                <Button variant="primary" icon={Zap}>New Investigation</Button>
              </div>
            </div>
          </div>
        </div>

        {/* ================= MAIN CONTENT AREA ================= */}
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 -mt-10">
          
          {/* KPI Cards Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
            {dashboardMetrics.slice(0, 4).map((metric) => (
              <StatCard 
                key={metric.id}
                label={metric.label}
                value={metric.value}
                trend={metric.trend}
                detail={metric.detail}
                icon={metric.icon}
                className="shadow-md"
              />
            ))}
          </div>

          {/* AI Predictive Alerts Section */}
          <div className="mb-8">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-display font-semibold text-slate-900 flex items-center gap-2">
                <Zap className="w-5 h-5 text-amber-500" />
                AI Predictive Alerts
              </h2>
              <button className="text-sm text-emerald-600 font-medium hover:text-emerald-700">View All Alerts</button>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {mockAIAlerts.map((alert) => (
                <div key={alert.id} className={`bg-white rounded-xl p-5 border-l-4 shadow-sm hover:shadow-md transition-shadow ${alert.severity === 'Critical' ? 'border-l-red-600' : alert.severity === 'High' ? 'border-l-rose-500' : 'border-l-amber-500'}`}>
                  <div className="flex justify-between items-start mb-2">
                    <Badge variant={alert.severity === 'Critical' ? 'critical' : alert.severity === 'High' ? 'danger' : 'warning'}>
                      {alert.severity} Risk
                    </Badge>
                    <span className="text-xs text-slate-400 flex items-center gap-1">
                      <Clock className="w-3 h-3" /> {alert.timestamp}
                    </span>
                  </div>
                  <h3 className="font-semibold text-slate-900 mb-1">{alert.type}</h3>
                  <p className="text-sm text-slate-600 mb-3 line-clamp-2">{alert.details}</p>
                  <div className="pt-3 border-t border-slate-100 flex justify-between items-center">
                    <span className="text-xs font-medium text-slate-500">{alert.target}</span>
                    <button className="text-xs font-semibold text-emerald-600 hover:text-emerald-700 flex items-center gap-1">
                      Review <ChevronRight className="w-3 h-3" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Complex Workspace Layout */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            
            {/* Left Column: Main Workspace (Tabs) */}
            <div className="lg:col-span-2 space-y-6">
              <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
                
                {/* Custom Tab Header */}
                <div className="border-b border-slate-200 bg-slate-50/50 px-4 pt-4">
                  <div className="flex space-x-6">
                    {[
                      { id: 'cases', label: 'Assigned Cases', icon: Briefcase, count: mockAssignedCases.length },
                      { id: 'risk', label: 'Department Risk Matrix', icon: BarChart3 },
                      { id: 'comms', label: 'Secure Comms', icon: MessageSquare, count: 3 }
                    ].map((tab) => (
                      <button
                        key={tab.id}
                        onClick={() => setActiveTab(tab.id)}
                        className={`pb-3 text-sm font-medium flex items-center gap-2 border-b-2 transition-colors ${
                          activeTab === tab.id 
                            ? 'border-emerald-600 text-emerald-700' 
                            : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
                        }`}
                      >
                        <tab.icon className="w-4 h-4" />
                        {tab.label}
                        {tab.count !== undefined && (
                          <span className={`px-2 py-0.5 rounded-full text-xs ${activeTab === tab.id ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-200 text-slate-600'}`}>
                            {tab.count}
                          </span>
                        )}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Tab Content Area */}
                <div className="p-0">
                  
                  {/* TAB 1: ASSIGNED CASES */}
                  {activeTab === 'cases' && (
                    <div className="animate-in fade-in duration-300">
                      <div className="p-4 border-b border-slate-100 bg-white">
                        <SearchFilterBar 
                          searchTerm={searchQuery}
                          onSearchChange={(e) => setSearchQuery(e.target.value)}
                          activeFilter={statusFilter}
                          onFilterChange={setStatusFilter}
                          filters={[
                            { id: 'all', label: 'All Cases' },
                            { id: 'investigating', label: 'Investigating' },
                            { id: 'pending-review', label: 'Pending Review' },
                            { id: 'active-surveillance', label: 'Surveillance' },
                          ]}
                          resultCount={filteredCases.length}
                        />
                      </div>
                      
                      <div className="overflow-x-auto">
                        <table className="w-full text-left border-collapse">
                          <thead>
                            <tr className="bg-slate-50 border-b border-slate-200 text-xs uppercase tracking-wider text-slate-500 font-semibold">
                              <th className="p-4">Case ID & Title</th>
                              <th className="p-4">Department</th>
                              <th className="p-4">Risk / AI Score</th>
                              <th className="p-4">Status</th>
                              <th className="p-4 text-right">Action</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-100">
                            {filteredCases.length > 0 ? (
                              filteredCases.map((c) => (
                                <tr key={c.id} className="hover:bg-slate-50/80 transition-colors group cursor-pointer" onClick={() => handleOpenModal(c)}>
                                  <td className="p-4">
                                    <div className="font-medium text-slate-900">{c.id}</div>
                                    <div className="text-sm text-slate-500 truncate max-w-[200px]">{c.title}</div>
                                  </td>
                                  <td className="p-4">
                                    <div className="text-sm text-slate-700 flex items-center gap-1">
                                      <MapPin className="w-3 h-3 text-slate-400" />
                                      {c.department}
                                    </div>
                                    <div className="text-xs text-slate-400">{c.location}</div>
                                  </td>
                                  <td className="p-4">
                                    <div className="flex items-center gap-2">
                                      <Badge variant={getRiskVariant(c.riskLevel)}>{c.riskLevel}</Badge>
                                      <span className="text-xs font-medium text-emerald-600 bg-emerald-50 px-1.5 py-0.5 rounded flex items-center gap-1">
                                        <Zap className="w-3 h-3" /> {c.aiConfidence}%
                                      </span>
                                    </div>
                                  </td>
                                  <td className="p-4">
                                    <Badge variant={getStatusVariant(c.status)}>{c.status}</Badge>
                                  </td>
                                  <td className="p-4 text-right">
                                    <Button variant="ghost" size="sm" icon={Eye} onClick={(e) => { e.stopPropagation(); handleOpenModal(c); }}>
                                      View
                                    </Button>
                                  </td>
                                </tr>
                              ))
                            ) : (
                              <tr>
                                <td colSpan="5" className="p-8 text-center text-slate-500">
                                  <Search className="w-8 h-8 mx-auto text-slate-300 mb-3" />
                                  <p>No cases found matching your criteria.</p>
                                </td>
                              </tr>
                            )}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}

                  {/* TAB 2: RISK MATRIX */}
                  {activeTab === 'risk' && (
                    <div className="p-6 animate-in fade-in duration-300">
                      <div className="mb-6 flex justify-between items-end">
                        <div>
                          <h3 className="text-lg font-display font-semibold text-slate-900">Departmental Risk Analysis</h3>
                          <p className="text-sm text-slate-500">AI-generated risk scores based on complaint volume, severity, and historical data.</p>
                        </div>
                        <Button variant="secondary" size="sm" icon={Filter}>Filter Matrix</Button>
                      </div>
                      
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        {departmentRiskData.map((dept) => (
                          <div key={dept.id} className="border border-slate-200 rounded-lg p-4 flex items-center justify-between hover:border-emerald-300 transition-colors">
                            <div className="flex items-center gap-3">
                              <div className="w-10 h-10 rounded-lg bg-slate-100 flex items-center justify-center text-slate-600">
                                <Activity className="w-5 h-5" />
                              </div>
                              <div>
                                <h4 className="font-medium text-slate-900 text-sm">{dept.name}</h4>
                                <p className="text-xs text-slate-500">{dept.activeInvestigations} Active Investigations</p>
                              </div>
                            </div>
                            <div className="text-right">
                              <div className={`text-xl font-bold font-display ${dept.riskScore > 80 ? 'text-red-600' : dept.riskScore > 60 ? 'text-amber-500' : 'text-emerald-600'}`}>
                                {dept.riskScore}
                              </div>
                              <div className="text-xs text-slate-400 flex items-center justify-end gap-1">
                                {dept.trend === 'up' ? <TrendingUp className="w-3 h-3 text-red-500" /> : <TrendingDown className="w-3 h-3 text-emerald-500" />}
                                vs last month
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* TAB 3: SECURE COMMS */}
                  {activeTab === 'comms' && (
                    <div className="animate-in fade-in duration-300">
                      <div className="divide-y divide-slate-100">
                        {messages.slice(0, 6).map((msg) => (
                          <div key={msg.id} className={`p-4 flex gap-4 hover:bg-slate-50 transition-colors cursor-pointer ${msg.unread ? 'bg-emerald-50/30' : ''}`}>
                            <div className="relative">
                              <div className="w-10 h-10 rounded-full bg-slate-200 flex items-center justify-center text-slate-600 font-bold">
                                {msg.sender.charAt(0)}
                              </div>
                              {msg.unread && <div className="absolute top-0 right-0 w-3 h-3 bg-emerald-500 border-2 border-white rounded-full"></div>}
                            </div>
                            <div className="flex-1 min-w-0">
                              <div className="flex justify-between items-baseline mb-1">
                                <h4 className={`text-sm font-medium truncate ${msg.unread ? 'text-slate-900' : 'text-slate-700'}`}>{msg.sender}</h4>
                                <span className="text-xs text-slate-400 whitespace-nowrap ml-2">
                                  {new Date(msg.timestamp).toLocaleDateString()}
                                </span>
                              </div>
                              <p className={`text-sm truncate ${msg.unread ? 'text-slate-800 font-medium' : 'text-slate-500'}`}>
                                {msg.preview}
                              </p>
                            </div>
                          </div>
                        ))}
                      </div>
                      <div className="p-4 border-t border-slate-100 text-center">
                        <Button variant="ghost" size="sm">View All Messages</Button>
                      </div>
                    </div>
                  )}

                </div>
              </div>
            </div>

            {/* Right Column: Sidebar */}
            <div className="space-y-6">
              
              {/* Quick Actions */}
              <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
                <h3 className="text-sm font-display font-semibold text-slate-900 uppercase tracking-wider mb-4">Quick Actions</h3>
                <div className="space-y-2">
                  <button className="w-full flex items-center justify-between p-3 rounded-lg border border-slate-200 hover:border-emerald-500 hover:bg-emerald-50 transition-all group">
                    <div className="flex items-center gap-3 text-slate-700 group-hover:text-emerald-700">
                      <FileText className="w-5 h-5" />
                      <span className="font-medium text-sm">Draft Warrant Request</span>
                    </div>
                    <ChevronRight className="w-4 h-4 text-slate-400 group-hover:text-emerald-600" />
                  </button>
                  <button className="w-full flex items-center justify-between p-3 rounded-lg border border-slate-200 hover:border-emerald-500 hover:bg-emerald-50 transition-all group">
                    <div className="flex items-center gap-3 text-slate-700 group-hover:text-emerald-700">
                      <Shield className="w-5 h-5" />
                      <span className="font-medium text-sm">Verify Blockchain Evidence</span>
                    </div>
                    <ChevronRight className="w-4 h-4 text-slate-400 group-hover:text-emerald-600" />
                  </button>
                  <button className="w-full flex items-center justify-between p-3 rounded-lg border border-slate-200 hover:border-emerald-500 hover:bg-emerald-50 transition-all group">
                    <div className="flex items-center gap-3 text-slate-700 group-hover:text-emerald-700">
                      <User className="w-5 h-5" />
                      <span className="font-medium text-sm">Manage Informants</span>
                    </div>
                    <ChevronRight className="w-4 h-4 text-slate-400 group-hover:text-emerald-600" />
                  </button>
                </div>
              </div>

              {/* Activity Timeline */}
              <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
                <div className="flex justify-between items-center mb-6">
                  <h3 className="text-sm font-display font-semibold text-slate-900 uppercase tracking-wider">Recent Activity</h3>
                  <button className="text-xs text-emerald-600 hover:underline">View Log</button>
                </div>
                <TimelineList />
              </div>

            </div>
          </div>
        </div>
      </div>

      {/* ================= CASE DETAIL MODAL ================= */}
      {isModalOpen && selectedCase && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6">
          {/* Backdrop */}
          <div 
            className="absolute inset-0 bg-slate-900/60 backdrop-blur-sm transition-opacity"
            onClick={handleCloseModal}
          ></div>
          
          {/* Modal Content */}
          <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-3xl max-h-[90vh] overflow-hidden flex flex-col animate-in zoom-in-95 duration-200">
            
            {/* Modal Header */}
            <div className="px-6 py-4 border-b border-slate-100 flex justify-between items-start bg-slate-50">
              <div>
                <div className="flex items-center gap-3 mb-1">
                  <span className="text-sm font-mono text-slate-500">{selectedCase.id}</span>
                  <Badge variant={getStatusVariant(selectedCase.status)}>{selectedCase.status}</Badge>
                  <Badge variant={getRiskVariant(selectedCase.riskLevel)}>{selectedCase.riskLevel} Risk</Badge>
                </div>
                <h2 className="text-xl font-display font-bold text-slate-900">{selectedCase.title}</h2>
              </div>
              <button 
                onClick={handleCloseModal}
                className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-200 rounded-full transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Body (Scrollable) */}
            <div className="p-6 overflow-y-auto flex-1">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                <div className="col-span-2 space-y-6">
                  <div>
                    <h3 className="text-sm font-semibold text-slate-900 uppercase tracking-wider mb-2">Description</h3>
                    <p className="text-slate-600 leading-relaxed">{selectedCase.description}</p>
                  </div>
                  
                  <div>
                    <h3 className="text-sm font-semibold text-slate-900 uppercase tracking-wider mb-3">AI Analysis Summary</h3>
                    <div className="bg-emerald-50 border border-emerald-100 rounded-lg p-4">
                      <div className="flex items-center gap-2 mb-2">
                        <Zap className="w-5 h-5 text-emerald-600" />
                        <span className="font-semibold text-emerald-900">Credibility Score: {selectedCase.aiConfidence}%</span>
                      </div>
                      <p className="text-sm text-emerald-800">
                        Natural language processing indicates high consistency in the report. Cross-referencing with department databases shows matching vendor IDs and anomalous approval timestamps. Recommended action: Immediate financial audit.
                      </p>
                    </div>
                  </div>
                </div>
                
                <div className="space-y-4">
                  <div className="bg-slate-50 rounded-lg p-4 border border-slate-100">
                    <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">Case Metadata</h3>
                    <dl className="space-y-3 text-sm">
                      <div>
                        <dt className="text-slate-500 flex items-center gap-2"><Briefcase className="w-4 h-4"/> Department</dt>
                        <dd className="font-medium text-slate-900 mt-1">{selectedCase.department}</dd>
                      </div>
                      <div>
                        <dt className="text-slate-500 flex items-center gap-2"><MapPin className="w-4 h-4"/> Location</dt>
                        <dd className="font-medium text-slate-900 mt-1">{selectedCase.location}</dd>
                      </div>
                      <div>
                        <dt className="text-slate-500 flex items-center gap-2"><Calendar className="w-4 h-4"/> Filed On</dt>
                        <dd className="font-medium text-slate-900 mt-1">{new Date(selectedCase.date).toLocaleDateString()}</dd>
                      </div>
                      <div>
                        <dt className="text-slate-500 flex items-center gap-2"><FileText className="w-4 h-4"/> Evidence Items</dt>
                        <dd className="font-medium text-slate-900 mt-1">{selectedCase.evidenceCount} Files (Blockchain Verified)</dd>
                      </div>
                    </dl>
                  </div>
                </div>
              </div>
            </div>

            {/* Modal Footer */}
            <div className="px-6 py-4 border-t border-slate-100 bg-slate-50 flex justify-between items-center">
              <Button variant="ghost" icon={MessageSquare}>Contact Informant</Button>
              <div className="flex gap-3">
                <Button variant="secondary" onClick={handleCloseModal}>Close</Button>
                <Button variant="primary" icon={Shield}>Update Status</Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </AppShell>
  );
}