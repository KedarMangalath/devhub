import React, { useMemo, useState } from 'react';
import { 
  Search, MapPin, Calendar, Shield, Filter, ChevronRight, 
  AlertTriangle, CheckCircle, FileText, BarChart3, Eye, Lock,
  X, ArrowRight, Activity, Building, Users, TrendingUp,
  Clock, ShieldCheck, ChevronDown, FileDigit
} from 'lucide-react';
import AppShell from '../components/AppShell';
import { categories, dashboardMetrics } from '../mockData';

// ============================================================================
// INLINE UI PRIMITIVES
// ============================================================================

const Card = ({ className = '', children, onClick }) => (
  <div 
    onClick={onClick}
    className={`bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden ${onClick ? 'cursor-pointer hover:shadow-md transition-shadow' : ''} ${className}`}
  >
    {children}
  </div>
);

const Badge = ({ className = '', variant = "default", children }) => {
  const variants = {
    default: "bg-slate-100 text-slate-800 border-slate-200",
    primary: "bg-emerald-100 text-emerald-800 border-emerald-200",
    success: "bg-emerald-100 text-emerald-800 border-emerald-200",
    warning: "bg-amber-100 text-amber-800 border-amber-200",
    danger: "bg-rose-100 text-rose-800 border-rose-200",
    outline: "bg-transparent text-slate-600 border-slate-300",
  };
  
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${variants[variant]} ${className}`}>
      {children}
    </span>
  );
};

const Button = ({ className = '', variant = "default", size = "default", children, icon: Icon, ...props }) => {
  const variants = {
    default: "bg-[#059669] text-white hover:bg-[#047857] shadow-sm",
    outline: "border border-slate-300 bg-white text-slate-700 hover:bg-slate-50",
    ghost: "bg-transparent text-slate-600 hover:bg-slate-100",
    secondary: "bg-slate-800 text-white hover:bg-slate-700",
  };
  const sizes = {
    default: "h-10 px-4 py-2",
    sm: "h-8 px-3 text-xs",
    lg: "h-12 px-6 text-base",
  };
  
  return (
    <button 
      className={`inline-flex items-center justify-center rounded-lg font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-[#059669] focus:ring-offset-2 disabled:opacity-50 disabled:pointer-events-none ${variants[variant]} ${sizes[size]} ${className}`}
      {...props}
    >
      {Icon && <Icon className={`w-4 h-4 ${children ? 'mr-2' : ''}`} />}
      {children}
    </button>
  );
};

const Input = ({ className = '', icon: Icon, ...props }) => (
  <div className="relative w-full">
    {Icon && (
      <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
        <Icon className="h-5 w-5 text-slate-400" />
      </div>
    )}
    <input
      className={`block w-full rounded-lg border border-slate-300 bg-white py-2.5 text-slate-900 placeholder-slate-400 focus:border-[#059669] focus:outline-none focus:ring-1 focus:ring-[#059669] sm:text-sm ${Icon ? 'pl-10' : 'pl-3'} ${className}`}
      {...props}
    />
  </div>
);

// ============================================================================
// MOCK DATA (Specific to Directory)
// ============================================================================

const districts = [
  { name: 'Thiruvananthapuram', count: 145, risk: 'high' },
  { name: 'Ernakulam', count: 132, risk: 'high' },
  { name: 'Kozhikode', count: 98, risk: 'medium' },
  { name: 'Thrissur', count: 87, risk: 'medium' },
  { name: 'Malappuram', count: 76, risk: 'medium' },
  { name: 'Palakkad', count: 65, risk: 'low' },
  { name: 'Kollam', count: 54, risk: 'low' },
  { name: 'Kannur', count: 43, risk: 'low' },
];

const publicComplaints = [
  {
    id: 'C3MS-2023-8842',
    title: 'Bribery Request for Building Permit Approval',
    description: 'An official at the local panchayat office demanded ₹25,000 to process a standard residential building permit. Audio evidence has been submitted securely.',
    category: 'Local Self Govt (LSGD)',
    district: 'Ernakulam',
    status: 'Investigating',
    date: '2023-10-24',
    evidenceCount: 2,
    views: 342,
    aiConfidence: 94,
    timeline: [
      { date: '2023-10-24', event: 'Complaint filed anonymously via C3MS Portal.' },
      { date: '2023-10-25', event: 'AI Credibility Check passed. Assigned to Ernakulam Vigilance Unit.' },
      { date: '2023-10-26', event: 'Preliminary investigation initiated. Officer under surveillance.' }
    ]
  },
  {
    id: 'C3MS-2023-8810',
    title: 'Substandard Materials Used in PWD Road Construction',
    description: 'The newly laid bypass road in Ward 4 has already developed potholes within 2 weeks of completion. Contractor allegedly colluded with inspecting engineers.',
    category: 'Public Works (PWD)',
    district: 'Thiruvananthapuram',
    status: 'Resolved',
    date: '2023-09-15',
    evidenceCount: 5,
    views: 1205,
    aiConfidence: 88,
    timeline: [
      { date: '2023-09-15', event: 'Complaint filed with photographic evidence.' },
      { date: '2023-09-20', event: 'Vigilance technical team collected core samples.' },
      { date: '2023-10-10', event: 'Lab results confirmed substandard mix. Contractor blacklisted.' },
      { date: '2023-10-15', event: 'Recovery of ₹1.2Cr initiated. Case closed.' }
    ]
  },
  {
    id: 'C3MS-2023-8901',
    title: 'Disproportionate Assets - Motor Vehicle Inspector',
    description: 'Observed an MVI acquiring multiple luxury properties in the last two years, far exceeding known sources of income. Details of benami transactions attached.',
    category: 'Motor Vehicles (MVD)',
    district: 'Kozhikode',
    status: 'Investigating',
    date: '2023-10-28',
    evidenceCount: 8,
    views: 512,
    aiConfidence: 97,
    timeline: [
      { date: '2023-10-28', event: 'Detailed dossier submitted by whistleblower.' },
      { date: '2023-10-29', event: 'Financial Intelligence Unit (FIU) cross-referencing data.' }
    ]
  },
  {
    id: 'C3MS-2023-8755',
    title: 'Illegal Tree Felling in Protected Forest Area',
    description: 'Timber mafia operating with the alleged support of local forest guards. GPS coordinates and drone footage of the cleared area provided.',
    category: 'Forest Department',
    district: 'Palakkad',
    status: 'Resolved',
    date: '2023-08-10',
    evidenceCount: 4,
    views: 890,
    aiConfidence: 92,
    timeline: [
      { date: '2023-08-10', event: 'Drone footage uploaded to secure vault.' },
      { date: '2023-08-15', event: 'Surprise raid conducted by Special Task Force.' },
      { date: '2023-09-05', event: '3 officials suspended. Timber worth ₹45 Lakhs seized.' }
    ]
  },
  {
    id: 'C3MS-2023-8922',
    title: 'Delay in Issuing Heirship Certificate',
    description: 'Village officer intentionally delaying the issuance of a legal heirship certificate for over 3 months, hinting at a bribe for faster processing.',
    category: 'Revenue Department',
    district: 'Thrissur',
    status: 'Pending',
    date: '2023-10-30',
    evidenceCount: 1,
    views: 124,
    aiConfidence: 75,
    timeline: [
      { date: '2023-10-30', event: 'Complaint registered. Awaiting initial review.' }
    ]
  },
  {
    id: 'C3MS-2023-8640',
    title: 'Misappropriation of School Mid-Day Meal Funds',
    description: 'Audit records show inflated student attendance to claim excess funds for the mid-day meal scheme at a government UP school.',
    category: 'Education Dept',
    district: 'Malappuram',
    status: 'Investigating',
    date: '2023-07-22',
    evidenceCount: 3,
    views: 670,
    aiConfidence: 89,
    timeline: [
      { date: '2023-07-22', event: 'Discrepancy reported by internal auditor.' },
      { date: '2023-08-10', event: 'Departmental inquiry initiated.' },
      { date: '2023-09-15', event: 'Forensic audit of school accounts underway.' }
    ]
  }
];

// ============================================================================
// MAIN PAGE COMPONENT
// ============================================================================

export default function PublicDirectory() {
  // State
  const [searchTerm, setSearchTerm] = useState('');
  const [activeCategory, setActiveCategory] = useState('All');
  const [activeStatus, setActiveStatus] = useState('All');
  const [selectedComplaint, setSelectedComplaint] = useState(null);

  // Derived Data
  const filteredComplaints = useMemo(() => {
    return publicComplaints.filter(c => {
      const matchesSearch = c.title.toLowerCase().includes(searchTerm.toLowerCase()) || 
                            c.description.toLowerCase().includes(searchTerm.toLowerCase()) ||
                            c.id.toLowerCase().includes(searchTerm.toLowerCase());
      const matchesCategory = activeCategory === 'All' || c.category === activeCategory;
      const matchesStatus = activeStatus === 'All' || c.status === activeStatus;
      return matchesSearch && matchesCategory && matchesStatus;
    });
  }, [searchTerm, activeCategory, activeStatus]);

  const resolvedCount = publicComplaints.filter(c => c.status === 'Resolved').length;
  const investigatingCount = publicComplaints.filter(c => c.status === 'Investigating').length;

  // Handlers
  const handleCardClick = (complaint) => {
    setSelectedComplaint(complaint);
    document.body.style.overflow = 'hidden'; // Prevent background scrolling
  };

  const closeModal = () => {
    setSelectedComplaint(null);
    document.body.style.overflow = 'auto';
  };

  return (
    <AppShell>
      <div className="min-h-screen bg-[#F8FAFC] font-body pb-20">
        
        {/* SECTION 1: HERO */}
        <section className="relative bg-slate-900 text-white py-20 overflow-hidden">
          {/* Background Pattern */}
          <div className="absolute inset-0 opacity-10 bg-[linear-gradient(to_right,#80808012_1px,transparent_1px),linear-gradient(to_bottom,#80808012_1px,transparent_1px)] bg-[size:24px_24px]"></div>
          <div className="absolute top-0 right-0 -translate-y-12 translate-x-1/3 w-96 h-96 bg-[#059669] rounded-full blur-[120px] opacity-20"></div>
          
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
            <div className="max-w-3xl">
              <Badge variant="outline" className="mb-6 border-emerald-500/30 text-emerald-400 bg-emerald-500/10">
                <Eye className="w-3 h-3 mr-2" />
                Public Transparency Portal
              </Badge>
              <h1 className="text-4xl md:text-5xl font-display font-bold tracking-tight mb-6">
                Anonymized Public <span className="text-transparent bg-clip-text bg-gradient-to-r from-emerald-400 to-teal-400">Directory</span>
              </h1>
              <p className="text-lg text-slate-300 mb-8 leading-relaxed">
                Explore verified, anonymized reports of corruption across Kerala. Track the progress of investigations, view state-wide heatmaps, and see how public vigilance is driving real change.
              </p>
              
              <div className="flex flex-wrap gap-4">
                <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4 flex items-center gap-4 backdrop-blur-sm">
                  <div className="p-3 bg-emerald-500/20 rounded-full text-emerald-400">
                    <ShieldCheck className="w-6 h-6" />
                  </div>
                  <div>
                    <p className="text-sm text-slate-400">Resolved Cases</p>
                    <p className="text-2xl font-display font-bold">{dashboardMetrics.find(m => m.id === 'm-2')?.value || '8,234'}</p>
                  </div>
                </div>
                <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4 flex items-center gap-4 backdrop-blur-sm">
                  <div className="p-3 bg-amber-500/20 rounded-full text-amber-400">
                    <Activity className="w-6 h-6" />
                  </div>
                  <div>
                    <p className="text-sm text-slate-400">Active Investigations</p>
                    <p className="text-2xl font-display font-bold">{dashboardMetrics.find(m => m.id === 'm-3')?.value || '3,102'}</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* SECTION 2: STATE HEATMAP WIDGET */}
        <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 -mt-8 relative z-20 mb-16">
          <Card className="p-6 shadow-lg">
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-6 gap-4">
              <div>
                <h2 className="text-xl font-display font-bold text-slate-900 flex items-center gap-2">
                  <MapPin className="w-5 h-5 text-[#059669]" />
                  District Risk Matrix
                </h2>
                <p className="text-sm text-slate-500 mt-1">Real-time volume of active reports by district</p>
              </div>
              <div className="flex items-center gap-3 text-sm">
                <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-full bg-rose-500"></span> High</span>
                <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-full bg-amber-500"></span> Medium</span>
                <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-full bg-emerald-500"></span> Low</span>
              </div>
            </div>
            
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-3">
              {districts.map((dist) => (
                <div 
                  key={dist.name} 
                  className={`p-3 rounded-lg border flex flex-col items-center justify-center text-center transition-all hover:-translate-y-1
                    ${dist.risk === 'high' ? 'bg-rose-50 border-rose-100' : 
                      dist.risk === 'medium' ? 'bg-amber-50 border-amber-100' : 
                      'bg-emerald-50 border-emerald-100'}
                  `}
                >
                  <span className="text-xs font-medium text-slate-600 mb-1 truncate w-full">{dist.name}</span>
                  <span className={`text-lg font-bold font-display
                    ${dist.risk === 'high' ? 'text-rose-700' : 
                      dist.risk === 'medium' ? 'text-amber-700' : 
                      'text-emerald-700'}
                  `}>
                    {dist.count}
                  </span>
                </div>
              ))}
            </div>
          </Card>
        </section>

        {/* SECTION 3: SEARCH & FILTERS */}
        <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 mb-8">
          <div className="flex flex-col md:flex-row gap-4 items-center justify-between bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
            <div className="w-full md:w-96">
              <Input 
                icon={Search} 
                placeholder="Search by ID, keyword, or department..." 
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
            </div>
            
            <div className="flex w-full md:w-auto gap-3 overflow-x-auto pb-2 md:pb-0 hide-scrollbar">
              <div className="flex items-center gap-2 border-r border-slate-200 pr-3">
                <Filter className="w-4 h-4 text-slate-400" />
                <span className="text-sm font-medium text-slate-600">Status:</span>
                <select 
                  className="text-sm border-none bg-slate-50 rounded-md py-1.5 px-2 focus:ring-0 cursor-pointer"
                  value={activeStatus}
                  onChange={(e) => setActiveStatus(e.target.value)}
                >
                  <option value="All">All Statuses</option>
                  <option value="Resolved">Resolved</option>
                  <option value="Investigating">Investigating</option>
                  <option value="Pending">Pending</option>
                </select>
              </div>
              
              <div className="flex items-center gap-2">
                {['All', 'Public Works (PWD)', 'Revenue Department', 'Local Self Govt (LSGD)'].map(cat => (
                  <button
                    key={cat}
                    onClick={() => setActiveCategory(cat)}
                    className={`whitespace-nowrap px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
                      activeCategory === cat 
                        ? 'bg-[#059669] text-white' 
                        : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                    }`}
                  >
                    {cat === 'All' ? 'All Departments' : cat.replace(/ \([^)]*\)/, '')}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </section>

        {/* SECTION 4: COMPLAINT GRID */}
        <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 mb-16">
          <div className="flex justify-between items-end mb-6">
            <div>
              <h2 className="text-2xl font-display font-bold text-slate-900">Public Directory</h2>
              <p className="text-slate-500 mt-1">Showing {filteredComplaints.length} anonymized records</p>
            </div>
          </div>

          {filteredComplaints.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {filteredComplaints.map((complaint) => (
                <Card key={complaint.id} onClick={() => handleCardClick(complaint)} className="flex flex-col h-full group">
                  <div className="p-5 flex-grow">
                    <div className="flex justify-between items-start mb-4">
                      <Badge variant={
                        complaint.status === 'Resolved' ? 'success' : 
                        complaint.status === 'Investigating' ? 'warning' : 'default'
                      }>
                        {complaint.status}
                      </Badge>
                      <span className="text-xs font-medium text-slate-400 flex items-center gap-1">
                        <FileDigit className="w-3 h-3" />
                        {complaint.id}
                      </span>
                    </div>
                    
                    <h3 className="text-lg font-bold text-slate-900 mb-2 line-clamp-2 group-hover:text-[#059669] transition-colors">
                      {complaint.title}
                    </h3>
                    <p className="text-sm text-slate-600 mb-4 line-clamp-3">
                      {complaint.description}
                    </p>
                    
                    <div className="flex flex-wrap gap-2 mt-auto">
                      <span className="inline-flex items-center text-xs text-slate-500 bg-slate-50 px-2 py-1 rounded border border-slate-100">
                        <Building className="w-3 h-3 mr-1" />
                        {complaint.category.replace(/ \([^)]*\)/, '')}
                      </span>
                      <span className="inline-flex items-center text-xs text-slate-500 bg-slate-50 px-2 py-1 rounded border border-slate-100">
                        <MapPin className="w-3 h-3 mr-1" />
                        {complaint.district}
                      </span>
                    </div>
                  </div>
                  
                  <div className="px-5 py-3 bg-slate-50 border-t border-slate-100 flex justify-between items-center text-xs text-slate-500">
                    <div className="flex items-center gap-3">
                      <span className="flex items-center gap-1" title="Evidence Files">
                        <FileText className="w-3.5 h-3.5" /> {complaint.evidenceCount}
                      </span>
                      <span className="flex items-center gap-1" title="AI Confidence Score">
                        <BarChart3 className="w-3.5 h-3.5 text-emerald-600" /> {complaint.aiConfidence}%
                      </span>
                    </div>
                    <span className="flex items-center gap-1">
                      <Calendar className="w-3.5 h-3.5" />
                      {new Date(complaint.date).toLocaleDateString('en-IN', { month: 'short', day: 'numeric', year: 'numeric' })}
                    </span>
                  </div>
                </Card>
              ))}
            </div>
          ) : (
            <div className="text-center py-20 bg-white rounded-xl border border-slate-200 border-dashed">
              <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-slate-100 mb-4">
                <Search className="w-8 h-8 text-slate-400" />
              </div>
              <h3 className="text-lg font-bold text-slate-900 mb-2">No records found</h3>
              <p className="text-slate-500 max-w-md mx-auto">
                We couldn't find any public complaints matching your current filters. Try adjusting your search terms or category selection.
              </p>
              <Button 
                variant="outline" 
                className="mt-6"
                onClick={() => { setSearchTerm(''); setActiveCategory('All'); setActiveStatus('All'); }}
              >
                Clear Filters
              </Button>
            </div>
          )}
        </section>

        {/* SECTION 5: SUCCESS STORIES (Resolved Cases Highlight) */}
        <section className="bg-white border-y border-slate-200 py-16 mb-16">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex items-center justify-between mb-8">
              <div>
                <h2 className="text-2xl font-display font-bold text-slate-900 flex items-center gap-2">
                  <CheckCircle className="w-6 h-6 text-emerald-600" />
                  Recent Success Stories
                </h2>
                <p className="text-slate-500 mt-1">Real impact driven by citizen reports and AI analysis.</p>
              </div>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {publicComplaints.filter(c => c.status === 'Resolved').slice(0, 2).map(story => (
                <div key={`story-${story.id}`} className="bg-emerald-50/50 border border-emerald-100 rounded-xl p-6 flex gap-4">
                  <div className="flex-shrink-0">
                    <div className="w-12 h-12 bg-emerald-100 rounded-full flex items-center justify-center text-emerald-600">
                      <TrendingUp className="w-6 h-6" />
                    </div>
                  </div>
                  <div>
                    <h3 className="text-lg font-bold text-slate-900 mb-2">{story.title}</h3>
                    <p className="text-sm text-slate-600 mb-4">{story.description}</p>
                    <div className="flex items-center gap-4 text-xs font-medium text-emerald-700">
                      <span className="flex items-center gap-1"><MapPin className="w-3.5 h-3.5" /> {story.district}</span>
                      <span className="flex items-center gap-1"><Calendar className="w-3.5 h-3.5" /> Resolved in {Math.floor(Math.random() * 30) + 15} days</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* SECTION 6: CTA */}
        <section className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center mb-20">
          <div className="bg-slate-900 rounded-2xl p-10 relative overflow-hidden shadow-xl">
            <div className="absolute top-0 right-0 -translate-y-1/2 translate-x-1/4 w-64 h-64 bg-[#059669] rounded-full blur-[80px] opacity-30"></div>
            <div className="relative z-10">
              <Shield className="w-12 h-12 text-emerald-400 mx-auto mb-4" />
              <h2 className="text-3xl font-display font-bold text-white mb-4">Have something to report?</h2>
              <p className="text-slate-300 mb-8 max-w-2xl mx-auto">
                Your identity is protected by zero-knowledge proofs. Submit evidence securely and let our AI-driven system ensure it reaches the right authorities without tampering.
              </p>
              <div className="flex flex-col sm:flex-row justify-center gap-4">
                <Button size="lg" icon={Lock}>File Anonymous Report</Button>
                <Button variant="outline" size="lg" className="border-slate-600 text-slate-300 hover:bg-slate-800 hover:text-white">Learn How It Works</Button>
              </div>
            </div>
          </div>
        </section>

      </div>

      {/* MODAL: COMPLAINT DETAILS */}
      {selectedComplaint && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6">
          <div className="absolute inset-0 bg-slate-900/60 backdrop-blur-sm" onClick={closeModal}></div>
          
          <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-3xl max-h-[90vh] overflow-hidden flex flex-col animate-in fade-in zoom-in-95 duration-200">
            {/* Modal Header */}
            <div className="px-6 py-4 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">
              <div className="flex items-center gap-3">
                <Badge variant={
                  selectedComplaint.status === 'Resolved' ? 'success' : 
                  selectedComplaint.status === 'Investigating' ? 'warning' : 'default'
                }>
                  {selectedComplaint.status}
                </Badge>
                <span className="text-sm font-medium text-slate-500 font-mono">{selectedComplaint.id}</span>
              </div>
              <button onClick={closeModal} className="text-slate-400 hover:text-slate-600 p-1 rounded-full hover:bg-slate-100 transition-colors">
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-6 overflow-y-auto flex-grow">
              <h2 className="text-2xl font-display font-bold text-slate-900 mb-4">{selectedComplaint.title}</h2>
              
              <div className="flex flex-wrap gap-4 mb-6 text-sm">
                <div className="flex items-center gap-1.5 text-slate-600 bg-slate-50 px-3 py-1.5 rounded-lg border border-slate-100">
                  <Building className="w-4 h-4 text-slate-400" />
                  {selectedComplaint.category}
                </div>
                <div className="flex items-center gap-1.5 text-slate-600 bg-slate-50 px-3 py-1.5 rounded-lg border border-slate-100">
                  <MapPin className="w-4 h-4 text-slate-400" />
                  {selectedComplaint.district}
                </div>
                <div className="flex items-center gap-1.5 text-slate-600 bg-slate-50 px-3 py-1.5 rounded-lg border border-slate-100">
                  <Calendar className="w-4 h-4 text-slate-400" />
                  {new Date(selectedComplaint.date).toLocaleDateString('en-IN', { month: 'long', day: 'numeric', year: 'numeric' })}
                </div>
              </div>

              <div className="mb-8">
                <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider mb-2">Description</h3>
                <p className="text-slate-700 leading-relaxed bg-slate-50 p-4 rounded-xl border border-slate-100">
                  {selectedComplaint.description}
                </p>
              </div>

              <div className="grid grid-cols-2 gap-4 mb-8">
                <div className="border border-slate-200 rounded-xl p-4 flex items-start gap-3">
                  <div className="p-2 bg-emerald-50 rounded-lg text-emerald-600">
                    <BarChart3 className="w-5 h-5" />
                  </div>
                  <div>
                    <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">AI Credibility</p>
                    <p className="text-xl font-bold text-slate-900">{selectedComplaint.aiConfidence}%</p>
                  </div>
                </div>
                <div className="border border-slate-200 rounded-xl p-4 flex items-start gap-3">
                  <div className="p-2 bg-blue-50 rounded-lg text-blue-600">
                    <FileText className="w-5 h-5" />
                  </div>
                  <div>
                    <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">Evidence Files</p>
                    <p className="text-xl font-bold text-slate-900">{selectedComplaint.evidenceCount} Verified</p>
                  </div>
                </div>
              </div>

              <div>
                <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider mb-4">Investigation Timeline</h3>
                <div className="space-y-4 relative before:absolute before:inset-0 before:ml-5 before:-translate-x-px md:before:mx-auto md:before:translate-x-0 before:h-full before:w-0.5 before:bg-gradient-to-b before:from-transparent before:via-slate-200 before:to-transparent">
                  {selectedComplaint.timeline.map((item, index) => (
                    <div key={index} className="relative flex items-center justify-between md:justify-normal md:odd:flex-row-reverse group is-active">
                      <div className="flex items-center justify-center w-10 h-10 rounded-full border-4 border-white bg-slate-100 text-slate-500 shadow shrink-0 md:order-1 md:group-odd:-translate-x-1/2 md:group-even:translate-x-1/2 z-10">
                        {index === selectedComplaint.timeline.length - 1 && selectedComplaint.status === 'Resolved' ? (
                          <CheckCircle className="w-4 h-4 text-emerald-600" />
                        ) : index === 0 ? (
                          <FileText className="w-4 h-4" />
                        ) : (
                          <Clock className="w-4 h-4" />
                        )}
                      </div>
                      <div className="w-[calc(100%-4rem)] md:w-[calc(50%-2.5rem)] p-4 rounded-xl border border-slate-100 bg-white shadow-sm">
                        <div className="flex items-center justify-between mb-1">
                          <time className="text-xs font-medium text-emerald-600">
                            {new Date(item.date).toLocaleDateString('en-IN', { month: 'short', day: 'numeric' })}
                          </time>
                        </div>
                        <div className="text-sm text-slate-700">{item.event}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Modal Footer */}
            <div className="px-6 py-4 border-t border-slate-100 bg-slate-50 flex justify-between items-center">
              <div className="flex items-center gap-2 text-xs text-slate-500">
                <Lock className="w-3 h-3" />
                Data anonymized for public viewing
              </div>
              <Button variant="outline" onClick={closeModal}>Close</Button>
            </div>
          </div>
        </div>
      )}
    </AppShell>
  );
}