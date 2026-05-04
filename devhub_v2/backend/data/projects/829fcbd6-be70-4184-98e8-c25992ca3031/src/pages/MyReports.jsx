import React, { useMemo, useState, useEffect } from 'react';
import { 
  Search, 
  Filter, 
  FileText, 
  CheckCircle, 
  Clock, 
  AlertTriangle, 
  Shield, 
  ChevronRight, 
  MapPin, 
  Calendar, 
  Lock, 
  Cpu, 
  Download, 
  ExternalLink,
  X,
  Activity,
  Eye,
  MessageSquare
} from 'lucide-react';

// Project Components
import AppShell from '../components/AppShell.jsx';
import PageHero from '../components/PageHero.jsx';
import StatCard from '../components/StatCard.jsx';
import TimelineList from '../components/TimelineList.jsx';
import { categories } from '../mockData.js';

// ============================================================================
// INLINE UI PRIMITIVES
// Defined here to ensure the page is 100% self-contained and functional
// without relying on external UI folders not explicitly listed in the plan.
// ============================================================================

const Card = ({ className = '', children, ...props }) => (
  <div 
    className={`rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden ${className}`} 
    {...props}
  >
    {children}
  </div>
);

const Badge = ({ className = '', variant = "default", children, ...props }) => {
  const variants = {
    default: "bg-slate-100 text-slate-800 border-slate-200",
    primary: "bg-emerald-100 text-emerald-800 border-emerald-200",
    success: "bg-emerald-100 text-emerald-800 border-emerald-200",
    warning: "bg-amber-100 text-amber-800 border-amber-200",
    danger: "bg-rose-100 text-rose-800 border-rose-200",
    info: "bg-blue-100 text-blue-800 border-blue-200",
  };
  
  return (
    <span 
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${variants[variant]} ${className}`} 
      {...props}
    >
      {children}
    </span>
  );
};

const Button = React.forwardRef(({ className = '', variant = "default", size = "default", children, ...props }, ref) => {
  const variants = {
    default: "bg-emerald-600 text-white hover:bg-emerald-700 shadow-sm",
    outline: "border border-slate-300 bg-transparent hover:bg-slate-50 text-slate-700",
    ghost: "hover:bg-slate-100 text-slate-700",
    secondary: "bg-slate-100 text-slate-900 hover:bg-slate-200",
  };
  const sizes = {
    default: "h-10 px-4 py-2",
    sm: "h-9 rounded-md px-3 text-xs",
    lg: "h-11 rounded-md px-8",
    icon: "h-10 w-10",
  };
  
  return (
    <button 
      ref={ref} 
      className={`inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 disabled:opacity-50 disabled:pointer-events-none ${variants[variant]} ${sizes[size]} ${className}`} 
      {...props}
    >
      {children}
    </button>
  );
});
Button.displayName = "Button";

const Input = React.forwardRef(({ className = '', icon: Icon, ...props }, ref) => (
  <div className="relative w-full">
    {Icon && (
      <Icon className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
    )}
    <input
      ref={ref}
      className={`flex h-10 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent disabled:cursor-not-allowed disabled:opacity-50 ${Icon ? 'pl-9' : ''} ${className}`}
      {...props}
    />
  </div>
));
Input.displayName = "Input";

// ============================================================================
// MOCK DATA (Specific to User's Reports)
// ============================================================================

const myReportsData = [
  {
    id: 'REP-2023-8842',
    title: 'Bribery Request for Building Permit Approval',
    description: 'The assistant engineer at the local LSGD office demanded ₹50,000 to clear the file for my residential building permit, despite all documents being in order. I have attached the audio recording of the conversation.',
    category: 'Local Self Govt (LSGD)',
    dateSubmitted: '2023-10-20T10:30:00Z',
    status: 'investigating',
    location: 'Thiruvananthapuram Corporation',
    isAnonymous: true,
    aiScore: 94,
    blockchainTx: '0x7f9a...4b21',
    evidence: [
      { name: 'audio_recording_oct19.mp3', type: 'audio', size: '2.4 MB' },
      { name: 'permit_application_copy.pdf', type: 'document', size: '1.1 MB' }
    ],
    timeline: [
      {
        id: 't1',
        status: 'investigating',
        title: 'Field Investigation Initiated',
        description: 'Case assigned to Inspector Rajeev. Covert verification of the audio sample is underway.',
        timestamp: '2023-10-22T09:15:00Z',
        icon: Search,
        details: { actor: 'Vigilance HQ', actionTaken: 'Officer Assigned' }
      },
      {
        id: 't2',
        status: 'resolved', // Using resolved color for completed past steps
        title: 'AI Credibility Check Passed',
        description: 'Audio analysis confirms high probability of voice match with the accused official. No tampering detected.',
        timestamp: '2023-10-20T11:00:00Z',
        icon: Cpu,
        details: { actor: 'C3MS AI Engine', actionTaken: 'Voice Biometric Scan' }
      },
      {
        id: 't3',
        status: 'resolved',
        title: 'Complaint Secured on Blockchain',
        description: 'Zero-knowledge proof generated. Identity masked. Payload encrypted and hashed.',
        timestamp: '2023-10-20T10:35:00Z',
        icon: Lock,
        details: { actor: 'System', actionTaken: 'SHA-256 Hash Generated' }
      }
    ]
  },
  {
    id: 'REP-2023-7105',
    title: 'Disproportionate Assets - RTO Official',
    description: 'Observed a Motor Vehicles Inspector acquiring multiple luxury properties in the last 6 months, far exceeding known sources of income. Properties are registered under benami names.',
    category: 'Motor Vehicles (MVD)',
    dateSubmitted: '2023-09-15T14:20:00Z',
    status: 'resolved',
    location: 'Kochi RTO',
    isAnonymous: true,
    aiScore: 88,
    blockchainTx: '0x3c2d...9e44',
    evidence: [
      { name: 'property_registry_extracts.pdf', type: 'document', size: '4.5 MB' },
      { name: 'vehicle_photos.jpg', type: 'image', size: '3.2 MB' }
    ],
    timeline: [
      {
        id: 't1',
        status: 'resolved',
        title: 'Case Closed - Action Taken',
        description: 'Following the raid, the officer has been suspended pending departmental inquiry. Assets worth ₹3.2Cr attached.',
        timestamp: '2023-10-28T16:00:00Z',
        icon: CheckCircle,
        details: { actor: 'Director General', actionTaken: 'Suspension Order Issued' }
      },
      {
        id: 't2',
        status: 'investigating',
        title: 'Search Warrant Executed',
        description: 'Simultaneous raids conducted at 3 locations linked to the accused.',
        timestamp: '2023-10-10T06:30:00Z',
        icon: Shield,
        details: { actor: 'Special Investigation Team', actionTaken: 'Raid Conducted' }
      },
      {
        id: 't3',
        status: 'resolved',
        title: 'Complaint Secured on Blockchain',
        description: 'Evidence hashed and stored immutably.',
        timestamp: '2023-09-15T14:25:00Z',
        icon: Lock,
        details: { actor: 'System', actionTaken: 'Data Secured' }
      }
    ]
  },
  {
    id: 'REP-2023-9021',
    title: 'Irregularities in PWD Road Tender',
    description: 'The recent tender for the bypass road repair was awarded to a blacklisted contractor using a shell company. The tender requirements were altered at the last minute to favor this specific vendor.',
    category: 'Public Works (PWD)',
    dateSubmitted: '2023-10-25T08:45:00Z',
    status: 'pending',
    location: 'Kozhikode District',
    isAnonymous: false,
    aiScore: 75,
    blockchainTx: '0x1a2b...3c4d',
    evidence: [
      { name: 'tender_document_v1.pdf', type: 'document', size: '2.1 MB' },
      { name: 'tender_document_v2_altered.pdf', type: 'document', size: '2.2 MB' }
    ],
    timeline: [
      {
        id: 't1',
        status: 'pending',
        title: 'Initial Review Pending',
        description: 'The complaint is currently queued for review by the preliminary assessment committee.',
        timestamp: '2023-10-25T09:00:00Z',
        icon: Clock,
        details: { actor: 'Assessment Desk', actionTaken: 'Queued' }
      },
      {
        id: 't2',
        status: 'resolved',
        title: 'Complaint Secured on Blockchain',
        description: 'Documents hashed and timestamped.',
        timestamp: '2023-10-25T08:50:00Z',
        icon: Lock,
        details: { actor: 'System', actionTaken: 'Data Secured' }
      }
    ]
  },
  {
    id: 'REP-2023-6543',
    title: 'Ration Shop Diversion of Subsidized Goods',
    description: 'The licensee of Ration Shop #442 is regularly diverting subsidized rice to the open market at night. I have recorded video evidence of the truck loading the sacks at 2 AM.',
    category: 'Civil Supplies',
    dateSubmitted: '2023-08-12T09:10:00Z',
    status: 'resolved',
    location: 'Thrissur',
    isAnonymous: true,
    aiScore: 91,
    blockchainTx: '0x9f8e...7d6c',
    evidence: [
      { name: 'night_loading_video.mp4', type: 'video', size: '18.5 MB' }
    ],
    timeline: [
      {
        id: 't1',
        status: 'resolved',
        title: 'License Cancelled',
        description: 'The ration shop license has been permanently revoked and a criminal case registered against the licensee.',
        timestamp: '2023-09-05T11:30:00Z',
        icon: CheckCircle,
        details: { actor: 'Civil Supplies Officer', actionTaken: 'License Revoked' }
      },
      {
        id: 't2',
        status: 'investigating',
        title: 'Surprise Inspection',
        description: 'Stock mismatch found during surprise audit based on the video evidence.',
        timestamp: '2023-08-15T10:00:00Z',
        icon: Search,
        details: { actor: 'Vigilance Squad', actionTaken: 'Audit Conducted' }
      }
    ]
  },
  {
    id: 'REP-2023-9155',
    title: 'Demand for Bribe - Forest Clearance',
    description: 'Forest range officer is demanding a bribe to issue a transit pass for legally cut timber from my private property.',
    category: 'Forest Department',
    dateSubmitted: '2023-10-28T11:20:00Z',
    status: 'high-risk',
    location: 'Wayanad',
    isAnonymous: true,
    aiScore: 96,
    blockchainTx: '0x5e4d...3c2b',
    evidence: [
      { name: 'whatsapp_screenshots.pdf', type: 'document', size: '1.5 MB' }
    ],
    timeline: [
      {
        id: 't1',
        status: 'high-risk',
        title: 'Trap Authorized',
        description: 'Based on the digital evidence, a trap has been authorized to catch the official red-handed.',
        timestamp: '2023-10-29T09:00:00Z',
        icon: AlertTriangle,
        details: { actor: 'Vigilance Director', actionTaken: 'Trap Sanctioned' }
      },
      {
        id: 't2',
        status: 'resolved',
        title: 'Complaint Secured on Blockchain',
        description: 'Screenshots verified for metadata tampering and hashed.',
        timestamp: '2023-10-28T11:25:00Z',
        icon: Lock,
        details: { actor: 'System', actionTaken: 'Data Secured' }
      }
    ]
  }
];

const getStatusConfig = (status) => {
  switch (status.toLowerCase()) {
    case 'resolved':
      return { label: 'Resolved', variant: 'success', icon: CheckCircle, color: 'text-emerald-600' };
    case 'investigating':
      return { label: 'Investigating', variant: 'warning', icon: Search, color: 'text-amber-600' };
    case 'pending':
      return { label: 'Pending Review', variant: 'info', icon: Clock, color: 'text-blue-600' };
    case 'high-risk':
      return { label: 'Action Initiated', variant: 'danger', icon: AlertTriangle, color: 'text-rose-600' };
    default:
      return { label: 'Unknown', variant: 'default', icon: FileText, color: 'text-slate-600' };
  }
};

const formatDate = (dateString) => {
  const options = { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' };
  return new Date(dateString).toLocaleDateString('en-IN', options);
};

// ============================================================================
// MAIN PAGE COMPONENT
// ============================================================================

export default function MyReports() {
  const [searchTerm, setSearchTerm] = useState('');
  const [activeFilter, setActiveFilter] = useState('all');
  const [selectedReport, setSelectedReport] = useState(null);
  const [modalTab, setModalTab] = useState('overview');

  // Prevent body scroll when modal is open
  useEffect(() => {
    if (selectedReport) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = 'unset';
    }
    return () => { document.body.style.overflow = 'unset'; };
  }, [selectedReport]);

  // Filter logic
  const filteredReports = useMemo(() => {
    return myReportsData.filter(report => {
      const matchesSearch = 
        report.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
        report.id.toLowerCase().includes(searchTerm.toLowerCase()) ||
        report.location.toLowerCase().includes(searchTerm.toLowerCase());
      
      const matchesFilter = 
        activeFilter === 'all' || 
        (activeFilter === 'active' && ['investigating', 'pending', 'high-risk'].includes(report.status)) ||
        (activeFilter === 'resolved' && report.status === 'resolved');

      return matchesSearch && matchesFilter;
    });
  }, [searchTerm, activeFilter]);

  // Stats calculation
  const stats = useMemo(() => {
    const total = myReportsData.length;
    const resolved = myReportsData.filter(r => r.status === 'resolved').length;
    const active = total - resolved;
    const anonymous = myReportsData.filter(r => r.isAnonymous).length;
    return { total, resolved, active, anonymous };
  }, []);

  return (
    <AppShell>
      {/* Hero Section */}
      <PageHero 
        title="My Reports"
        sub="Track the status of your submitted complaints, view AI analysis, and verify blockchain audit trails securely."
        breadcrumbs={[
          { label: 'Dashboard', href: '/dashboard' },
          { label: 'My Reports', href: '/history' }
        ]}
        badge={{ text: "Secure Citizen Portal", icon: Lock }}
      />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 space-y-12">
        
        {/* Stats Row */}
        <section>
          <h2 className="text-xl font-display font-semibold text-slate-900 mb-6">Overview</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <StatCard 
              label="Total Submitted" 
              value={stats.total} 
              icon="FileText" 
              tone="neutral" 
            />
            <StatCard 
              label="Active Investigations" 
              value={stats.active} 
              icon="Search" 
              tone="warning" 
            />
            <StatCard 
              label="Resolved Cases" 
              value={stats.resolved} 
              icon="CheckCircle" 
              tone="success" 
            />
            <StatCard 
              label="Anonymous Reports" 
              value={stats.anonymous} 
              icon="UserX" 
              tone="info" 
              detail="Identity Protected"
            />
          </div>
        </section>

        {/* Controls & List Section */}
        <section className="space-y-6">
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
            
            {/* Tabs */}
            <div className="flex space-x-2">
              {['all', 'active', 'resolved'].map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveFilter(tab)}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors capitalize ${
                    activeFilter === tab 
                      ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' 
                      : 'text-slate-600 hover:bg-slate-50 border border-transparent'
                  }`}
                >
                  {tab}
                </button>
              ))}
            </div>

            {/* Search */}
            <div className="w-full sm:w-72">
              <Input 
                icon={Search} 
                placeholder="Search by ID, title, or location..." 
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
            </div>
          </div>

          {/* Reports Grid */}
          {filteredReports.length > 0 ? (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {filteredReports.map((report) => {
                const statusConfig = getStatusConfig(report.status);
                const StatusIcon = statusConfig.icon;

                return (
                  <Card key={report.id} className="flex flex-col hover:shadow-md transition-shadow duration-200">
                    <div className="p-6 flex-grow">
                      <div className="flex justify-between items-start mb-4">
                        <Badge variant={statusConfig.variant} className="mb-2">
                          <StatusIcon className="w-3 h-3 mr-1.5" />
                          {statusConfig.label}
                        </Badge>
                        <span className="text-xs font-medium text-slate-500 font-mono bg-slate-100 px-2 py-1 rounded">
                          {report.id}
                        </span>
                      </div>
                      
                      <h3 className="text-lg font-display font-semibold text-slate-900 mb-2 line-clamp-2">
                        {report.title}
                      </h3>
                      
                      <p className="text-sm text-slate-600 mb-6 line-clamp-2 font-body">
                        {report.description}
                      </p>

                      <div className="grid grid-cols-2 gap-y-3 text-sm text-slate-500">
                        <div className="flex items-center">
                          <Calendar className="w-4 h-4 mr-2 text-slate-400" />
                          {new Date(report.dateSubmitted).toLocaleDateString()}
                        </div>
                        <div className="flex items-center">
                          <MapPin className="w-4 h-4 mr-2 text-slate-400" />
                          <span className="truncate">{report.location}</span>
                        </div>
                        <div className="flex items-center col-span-2">
                          <Shield className="w-4 h-4 mr-2 text-emerald-500" />
                          <span className="text-slate-700 font-medium">{report.category}</span>
                        </div>
                      </div>
                    </div>
                    
                    <div className="bg-slate-50 px-6 py-4 border-t border-slate-100 flex justify-between items-center">
                      <div className="flex items-center text-xs text-slate-500">
                        <Lock className="w-3 h-3 mr-1" />
                        {report.isAnonymous ? 'Anonymous Submission' : 'Standard Submission'}
                      </div>
                      <Button 
                        variant="outline" 
                        size="sm" 
                        onClick={() => {
                          setSelectedReport(report);
                          setModalTab('overview');
                        }}
                        className="group"
                      >
                        View Details
                        <ChevronRight className="w-4 h-4 ml-1 group-hover:translate-x-1 transition-transform" />
                      </Button>
                    </div>
                  </Card>
                );
              })}
            </div>
          ) : (
            <div className="text-center py-20 bg-white rounded-xl border border-slate-200 border-dashed">
              <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-slate-100 mb-4">
                <Search className="w-8 h-8 text-slate-400" />
              </div>
              <h3 className="text-lg font-medium text-slate-900 mb-1">No reports found</h3>
              <p className="text-slate-500">Try adjusting your search or filters.</p>
              {(searchTerm || activeFilter !== 'all') && (
                <Button 
                  variant="ghost" 
                  className="mt-4"
                  onClick={() => { setSearchTerm(''); setActiveFilter('all'); }}
                >
                  Clear all filters
                </Button>
              )}
            </div>
          )}
        </section>

        {/* Help Banner */}
        <section className="bg-slate-900 rounded-2xl p-8 sm:p-10 relative overflow-hidden shadow-lg">
          <div className="absolute top-0 right-0 -mt-4 -mr-4 w-32 h-32 bg-emerald-500 rounded-full opacity-20 blur-3xl"></div>
          <div className="absolute bottom-0 left-0 -mb-4 -ml-4 w-32 h-32 bg-blue-500 rounded-full opacity-20 blur-3xl"></div>
          
          <div className="relative z-10 flex flex-col md:flex-row items-center justify-between gap-8">
            <div className="text-left">
              <h3 className="text-2xl font-display font-bold text-white mb-2">Need assistance with your report?</h3>
              <p className="text-slate-300 max-w-2xl">
                Our support team is available 24/7. If you face any threats or require immediate protection under the Whistleblower Protection Act, contact the emergency hotline immediately.
              </p>
            </div>
            <div className="flex flex-col sm:flex-row gap-4 w-full md:w-auto">
              <Button className="bg-white text-slate-900 hover:bg-slate-100 w-full sm:w-auto">
                <MessageSquare className="w-4 h-4 mr-2" />
                Contact Support
              </Button>
              <Button variant="outline" className="border-slate-600 text-white hover:bg-slate-800 w-full sm:w-auto">
                View FAQ
              </Button>
            </div>
          </div>
        </section>

      </main>

      {/* ============================================================================
          DETAIL MODAL
          ============================================================================ */}
      {selectedReport && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6">
          {/* Backdrop */}
          <div 
            className="absolute inset-0 bg-slate-900/60 backdrop-blur-sm transition-opacity"
            onClick={() => setSelectedReport(null)}
          ></div>
          
          {/* Modal Content */}
          <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-4xl max-h-[90vh] flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-200">
            
            {/* Modal Header */}
            <div className="px-6 py-4 border-b border-slate-200 flex justify-between items-start bg-slate-50">
              <div>
                <div className="flex items-center gap-3 mb-1">
                  <span className="text-sm font-mono text-slate-500 bg-white px-2 py-0.5 rounded border border-slate-200">
                    {selectedReport.id}
                  </span>
                  <Badge variant={getStatusConfig(selectedReport.status).variant}>
                    {getStatusConfig(selectedReport.status).label}
                  </Badge>
                </div>
                <h2 className="text-xl font-display font-bold text-slate-900 pr-8">
                  {selectedReport.title}
                </h2>
              </div>
              <button 
                onClick={() => setSelectedReport(null)}
                className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-200 rounded-full transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Tabs */}
            <div className="flex border-b border-slate-200 px-6 bg-white">
              {[
                { id: 'overview', label: 'Overview', icon: FileText },
                { id: 'timeline', label: 'Investigation Timeline', icon: Activity },
                { id: 'security', label: 'Security & Evidence', icon: Shield }
              ].map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setModalTab(tab.id)}
                  className={`flex items-center px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                    modalTab === tab.id 
                      ? 'border-emerald-500 text-emerald-600' 
                      : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
                  }`}
                >
                  <tab.icon className="w-4 h-4 mr-2" />
                  {tab.label}
                </button>
              ))}
            </div>

            {/* Modal Body (Scrollable) */}
            <div className="flex-1 overflow-y-auto p-6 bg-white">
              
              {/* TAB: OVERVIEW */}
              {modalTab === 'overview' && (
                <div className="space-y-8">
                  <div>
                    <h3 className="text-sm font-semibold text-slate-900 uppercase tracking-wider mb-3">Description</h3>
                    <p className="text-slate-700 leading-relaxed font-body whitespace-pre-wrap bg-slate-50 p-4 rounded-xl border border-slate-100">
                      {selectedReport.description}
                    </p>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div>
                      <h3 className="text-sm font-semibold text-slate-900 uppercase tracking-wider mb-3">Details</h3>
                      <dl className="space-y-3 text-sm">
                        <div className="flex justify-between py-2 border-b border-slate-100">
                          <dt className="text-slate-500">Category</dt>
                          <dd className="font-medium text-slate-900">{selectedReport.category}</dd>
                        </div>
                        <div className="flex justify-between py-2 border-b border-slate-100">
                          <dt className="text-slate-500">Location</dt>
                          <dd className="font-medium text-slate-900">{selectedReport.location}</dd>
                        </div>
                        <div className="flex justify-between py-2 border-b border-slate-100">
                          <dt className="text-slate-500">Submitted On</dt>
                          <dd className="font-medium text-slate-900">{formatDate(selectedReport.dateSubmitted)}</dd>
                        </div>
                        <div className="flex justify-between py-2 border-b border-slate-100">
                          <dt className="text-slate-500">Identity Mode</dt>
                          <dd className="font-medium text-slate-900 flex items-center">
                            {selectedReport.isAnonymous ? (
                              <><Lock className="w-3 h-3 mr-1 text-emerald-500" /> Anonymous</>
                            ) : 'Standard'}
                          </dd>
                        </div>
                      </dl>
                    </div>
                    
                    <div>
                      <h3 className="text-sm font-semibold text-slate-900 uppercase tracking-wider mb-3">Attached Evidence</h3>
                      {selectedReport.evidence.length > 0 ? (
                        <ul className="space-y-2">
                          {selectedReport.evidence.map((file, idx) => (
                            <li key={idx} className="flex items-center justify-between p-3 bg-slate-50 border border-slate-200 rounded-lg">
                              <div className="flex items-center overflow-hidden">
                                <FileText className="w-5 h-5 text-slate-400 mr-3 flex-shrink-0" />
                                <div className="truncate">
                                  <p className="text-sm font-medium text-slate-900 truncate">{file.name}</p>
                                  <p className="text-xs text-slate-500">{file.size} • {file.type}</p>
                                </div>
                              </div>
                              <Button variant="ghost" size="icon" className="flex-shrink-0 ml-2">
                                <Download className="w-4 h-4" />
                              </Button>
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className="text-sm text-slate-500 italic">No evidence attached.</p>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* TAB: TIMELINE */}
              {modalTab === 'timeline' && (
                <div className="max-w-2xl mx-auto py-4">
                  <TimelineList events={selectedReport.timeline} />
                </div>
              )}

              {/* TAB: SECURITY */}
              {modalTab === 'security' && (
                <div className="space-y-8">
                  {/* AI Analysis */}
                  <div className="bg-slate-50 rounded-xl p-6 border border-slate-200">
                    <div className="flex items-center justify-between mb-4">
                      <div className="flex items-center">
                        <div className="bg-blue-100 p-2 rounded-lg mr-3">
                          <Cpu className="w-6 h-6 text-blue-600" />
                        </div>
                        <div>
                          <h3 className="text-lg font-display font-semibold text-slate-900">AI Credibility Analysis</h3>
                          <p className="text-sm text-slate-500">Automated initial assessment by C3MS Engine</p>
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-3xl font-display font-bold text-slate-900">{selectedReport.aiScore}%</div>
                        <div className="text-xs font-medium text-emerald-600 uppercase tracking-wider">High Confidence</div>
                      </div>
                    </div>
                    
                    <div className="w-full bg-slate-200 rounded-full h-2.5 mb-4">
                      <div className="bg-blue-600 h-2.5 rounded-full" style={{ width: `${selectedReport.aiScore}%` }}></div>
                    </div>
                    
                    <p className="text-sm text-slate-600">
                      The AI engine has cross-referenced the provided details, location data, and evidence metadata against historical patterns. The high score indicates a strong probability of factual accuracy, prioritizing this case for human review.
                    </p>
                  </div>

                  {/* Blockchain Verification */}
                  <div className="bg-slate-900 rounded-xl p-6 border border-slate-800 text-white">
                    <div className="flex items-center mb-6">
                      <div className="bg-emerald-500/20 p-2 rounded-lg mr-3 border border-emerald-500/30">
                        <Lock className="w-6 h-6 text-emerald-400" />
                      </div>
                      <div>
                        <h3 className="text-lg font-display font-semibold text-white">Blockchain Audit Trail</h3>
                        <p className="text-sm text-slate-400">Immutable record of submission</p>
                      </div>
                    </div>

                    <div className="space-y-4">
                      <div>
                        <label className="text-xs text-slate-400 uppercase tracking-wider mb-1 block">Transaction Hash</label>
                        <div className="flex items-center bg-slate-950 rounded-lg border border-slate-800 p-3">
                          <code className="text-emerald-400 text-sm font-mono break-all flex-1">
                            {selectedReport.blockchainTx}8f92a1b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9
                          </code>
                          <Button variant="ghost" size="icon" className="text-slate-400 hover:text-white ml-2">
                            <ExternalLink className="w-4 h-4" />
                          </Button>
                        </div>
                      </div>
                      
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <label className="text-xs text-slate-400 uppercase tracking-wider mb-1 block">Network</label>
                          <div className="text-sm font-medium">Kerala Govt Private Ledger</div>
                        </div>
                        <div>
                          <label className="text-xs text-slate-400 uppercase tracking-wider mb-1 block">Timestamp</label>
                          <div className="text-sm font-medium">{formatDate(selectedReport.dateSubmitted)}</div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
            
            {/* Modal Footer */}
            <div className="px-6 py-4 border-t border-slate-200 bg-slate-50 flex justify-end">
              <Button variant="outline" onClick={() => setSelectedReport(null)}>
                Close
              </Button>
            </div>

          </div>
        </div>
      )}

    </AppShell>
  );
}
