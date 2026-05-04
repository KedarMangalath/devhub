import React, { useMemo, useState, useEffect } from 'react';
import { Link, useParams } from 'react-router-dom';
import {
  MapPin, Calendar, Shield, AlertTriangle, CheckCircle,
  Clock, FileText, Share2, Bookmark, ChevronRight,
  Download, Eye, Lock, Activity, User, Building,
  Hash, Link as LinkIcon, MessageSquare, ThumbsUp,
  Home, ArrowUpRight, ShieldCheck, Server, Cpu,
  FileDigit, Check, X
} from 'lucide-react';

import AppShell from '../components/AppShell';
import TabbedPanel from '../components/TabbedPanel';
import TimelineList from '../components/TimelineList';
import ItemCard from '../components/ItemCard';
import { categories, userProfile } from '../mockData';

// ============================================================================
// INLINE UI PRIMITIVES
// Ensuring the page is 100% self-contained with polished design system elements.
// ============================================================================

const Card = ({ className = '', children, ...props }) => (
  <div 
    className={`rounded-xl border border-slate-200 bg-white text-slate-900 shadow-sm overflow-hidden ${className}`} 
    {...props}
  >
    {children}
  </div>
);

const Badge = ({ className = '', variant = "default", children, ...props }) => {
  const variants = {
    default: "border-transparent bg-slate-100 text-slate-800",
    primary: "border-transparent bg-emerald-100 text-emerald-800",
    secondary: "border-transparent bg-blue-100 text-blue-800",
    outline: "text-slate-600 border-slate-200",
    destructive: "border-transparent bg-rose-100 text-rose-800",
    success: "border-transparent bg-emerald-100 text-emerald-800",
    warning: "border-transparent bg-amber-100 text-amber-800",
  };
  
  return (
    <div 
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors ${variants[variant]} ${className}`} 
      {...props}
    >
      {children}
    </div>
  );
};

const Button = React.forwardRef(({ className = '', variant = "default", size = "default", children, ...props }, ref) => {
  const variants = {
    default: "bg-emerald-600 text-white hover:bg-emerald-700 shadow-sm",
    outline: "border border-slate-200 bg-transparent hover:bg-slate-50 text-slate-700",
    ghost: "hover:bg-slate-100 text-slate-700",
    secondary: "bg-slate-100 text-slate-900 hover:bg-slate-200",
    destructive: "bg-rose-600 text-white hover:bg-rose-700 shadow-sm",
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
      className={`inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 disabled:pointer-events-none disabled:opacity-50 ${variants[variant]} ${sizes[size]} ${className}`} 
      {...props}
    >
      {children}
    </button>
  );
});
Button.displayName = "Button";

const Avatar = ({ src, fallback, className = '' }) => (
  <div className={`relative flex h-10 w-10 shrink-0 overflow-hidden rounded-full bg-slate-100 ${className}`}>
    {src ? (
      <img src={src} alt="Avatar" className="aspect-square h-full w-full object-cover" />
    ) : (
      <span className="flex h-full w-full items-center justify-center font-medium text-slate-600">
        {fallback}
      </span>
    )}
  </div>
);

// ============================================================================
// MOCK DATA SPECIFIC TO DETAIL PAGE
// ============================================================================

const mockComplaintDetail = {
  id: 'CMP-2023-8842',
  title: 'Fraudulent Road Contract Allocation & Substandard Materials in NH-44 Bypass',
  description: `I am writing to report severe irregularities in the recent tender process and ongoing construction of the NH-44 bypass road in District 4. Documents obtained via RTI suggest that the contract was pre-approved for a specific vendor (Apex Infra Ltd) despite them not meeting the minimum technical qualifications outlined in the initial tender notice. 

Furthermore, independent lab tests of the core samples taken from the first 2km stretch indicate the use of substandard bitumen and aggregate mixtures, which violate the IRC (Indian Roads Congress) specifications mandated in the contract. Local officials from the PWD appear to be ignoring these violations despite multiple written complaints from the resident welfare association.

I have attached the RTI responses, the original tender document, and the independent lab test results for your perusal. I request an immediate vigilance inquiry and a stay on further payments to the contractor until a thorough quality audit is conducted.`,
  category: 'Public Works (PWD)',
  departmentId: 'cat-1',
  status: 'Investigating',
  dateSubmitted: '2023-10-24T10:30:00Z',
  location: 'Thiruvananthapuram, District 4',
  estimatedValue: '₹4.5 Crores',
  credibilityScore: 92,
  isAnonymous: true,
  heroImage: 'https://images.unsplash.com/photo-1584467735815-f778f274e296?w=1600&q=80',
  aiAnalysis: {
    riskLevel: 'High',
    confidence: '94%',
    summary: 'NLP analysis detects strong indicators of tender manipulation and material fraud. Cross-referencing with historical data shows the mentioned vendor (Apex Infra) has been flagged in 3 previous anomalies in neighboring districts.',
    flags: [
      'Vendor pre-qualification mismatch',
      'Repeat offender correlation',
      'Documentary evidence provided (RTI)'
    ]
  },
  evidence: [
    { id: 'ev-1', name: 'RTI_Response_Tender_Docs.pdf', type: 'document', size: '2.4 MB', hash: '0x8f2a...9c11', verified: true },
    { id: 'ev-2', name: 'Lab_Test_Results_Core_Sample.pdf', type: 'document', size: '1.1 MB', hash: '0x3a1b...7d22', verified: true },
    { id: 'ev-3', name: 'Site_Photos_Potholes.zip', type: 'archive', size: '14.5 MB', hash: '0x1c4d...5e99', verified: true },
    { id: 'ev-4', name: 'Audio_Recording_Official.mp3', type: 'audio', size: '4.2 MB', hash: '0x9b2f...1a44', verified: false }
  ],
  relatedCases: [
    {
      id: 'cmp-1021',
      title: 'Bridge Construction Delay and Fund Misappropriation',
      description: 'Funds allocated for the river bridge have been exhausted but construction is only 30% complete.',
      category: 'Public Works (PWD)',
      imageUrl: 'https://images.unsplash.com/photo-1541888087525-efb8f5085a14?w=800&q=80',
      date: '2023-09-15T00:00:00Z',
      status: 'Resolved',
      credibilityScore: 88,
      location: 'Kollam',
      evidenceCount: 5,
      isAnonymous: false
    },
    {
      id: 'cmp-1088',
      title: 'Illegal Toll Collection on State Highway',
      description: 'Contractor continues to collect tolls despite the expiration of the concession agreement.',
      category: 'Public Works (PWD)',
      imageUrl: 'https://images.unsplash.com/photo-1515162816999-a0c47dc192f7?w=800&q=80',
      date: '2023-10-10T00:00:00Z',
      status: 'Investigating',
      credibilityScore: 75,
      location: 'Thrissur',
      evidenceCount: 2,
      isAnonymous: true
    }
  ]
};

// ============================================================================
// MAIN PAGE COMPONENT
// ============================================================================

export default function Detail() {
  const { id } = useParams(); // In a real app, fetch data based on ID
  const data = mockComplaintDetail; // Using rich mock data
  
  // Local State for Interactions
  const [isFollowing, setIsFollowing] = useState(false);
  const [showShareToast, setShowShareToast] = useState(false);
  const [activeTab, setActiveTab] = useState('overview');
  const [isEvidenceModalOpen, setIsEvidenceModalOpen] = useState(false);
  const [selectedEvidence, setSelectedEvidence] = useState(null);

  // Handlers
  const handleShare = () => {
    setShowShareToast(true);
    setTimeout(() => setShowShareToast(false), 3000);
  };

  const handleViewEvidence = (item) => {
    setSelectedEvidence(item);
    setIsEvidenceModalOpen(true);
  };

  // Tab Configuration for TabbedPanel
  const tabs = [
    { id: 'overview', label: 'Overview', icon: FileText },
    { id: 'evidence', label: 'Evidence & Blockchain', icon: ShieldCheck, count: data.evidence.length },
    { id: 'activity', label: 'Activity Timeline', icon: Activity },
    { id: 'related', label: 'Related Cases', icon: LinkIcon, count: data.relatedCases.length },
  ];

  return (
    <AppShell>
      <div className="min-h-screen bg-slate-50 font-body pb-20">
        
        {/* --- HERO SECTION --- */}
        <div className="relative isolate overflow-hidden bg-slate-900 pt-16 pb-24 sm:pt-24 sm:pb-32">
          <img
            src={data.heroImage}
            alt="Hero background"
            className="absolute inset-0 -z-20 h-full w-full object-cover opacity-30 mix-blend-luminosity"
          />
          <div className="absolute inset-0 -z-10 bg-gradient-to-t from-slate-950 via-slate-900/80 to-transparent" />
          
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 relative z-10">
            {/* Breadcrumbs */}
            <nav className="flex mb-8" aria-label="Breadcrumb">
              <ol className="flex items-center space-x-2 text-sm text-slate-400">
                <li>
                  <Link to="/" className="hover:text-white transition-colors flex items-center">
                    <Home className="w-4 h-4" />
                    <span className="sr-only">Home</span>
                  </Link>
                </li>
                <li className="flex items-center">
                  <ChevronRight className="w-4 h-4 mx-1" />
                  <Link to="/explore" className="hover:text-white transition-colors">Explore</Link>
                </li>
                <li className="flex items-center">
                  <ChevronRight className="w-4 h-4 mx-1" />
                  <span className="text-slate-300">{data.category}</span>
                </li>
                <li className="flex items-center">
                  <ChevronRight className="w-4 h-4 mx-1" />
                  <span className="text-emerald-400 font-medium">{data.id}</span>
                </li>
              </ol>
            </nav>

            <div className="max-w-4xl">
              <div className="flex flex-wrap items-center gap-3 mb-4">
                <Badge variant="warning" className="bg-amber-500/20 text-amber-300 border border-amber-500/30 px-3 py-1 text-sm">
                  <Clock className="w-4 h-4 mr-1.5" />
                  {data.status}
                </Badge>
                {data.isAnonymous && (
                  <Badge variant="outline" className="text-slate-300 border-slate-600 px-3 py-1 text-sm">
                    <Lock className="w-4 h-4 mr-1.5" />
                    Anonymous Report
                  </Badge>
                )}
                <Badge variant="outline" className="text-slate-300 border-slate-600 px-3 py-1 text-sm">
                  <Building className="w-4 h-4 mr-1.5" />
                  {data.category}
                </Badge>
              </div>
              
              <h1 className="text-3xl sm:text-4xl lg:text-5xl font-bold text-white font-display tracking-tight mb-6 leading-tight">
                {data.title}
              </h1>
              
              <div className="flex flex-wrap items-center gap-6 text-sm text-slate-300">
                <div className="flex items-center">
                  <MapPin className="w-4 h-4 mr-2 text-emerald-400" />
                  {data.location}
                </div>
                <div className="flex items-center">
                  <Calendar className="w-4 h-4 mr-2 text-emerald-400" />
                  {new Date(data.dateSubmitted).toLocaleDateString('en-IN', { year: 'numeric', month: 'long', day: 'numeric' })}
                </div>
                <div className="flex items-center">
                  <Hash className="w-4 h-4 mr-2 text-emerald-400" />
                  ID: {data.id}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* --- MAIN CONTENT GRID --- */}
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 -mt-8 relative z-20">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            
            {/* LEFT COLUMN: Tabbed Content */}
            <div className="lg:col-span-2 space-y-6">
              <Card className="shadow-md border-slate-200/60">
                <TabbedPanel 
                  tabs={tabs} 
                  defaultTab="overview" 
                  onTabChange={setActiveTab}
                  className="border-b border-slate-100"
                >
                  {/* TAB 1: OVERVIEW */}
                  {activeTab === 'overview' && (
                    <div className="p-6 sm:p-8 animate-in fade-in duration-500">
                      
                      {/* AI Analysis Alert Box */}
                      <div className="mb-8 rounded-xl bg-gradient-to-r from-emerald-50 to-teal-50 border border-emerald-100 p-5">
                        <div className="flex items-start gap-4">
                          <div className="p-2 bg-emerald-100 rounded-lg text-emerald-600 shrink-0">
                            <Cpu className="w-6 h-6" />
                          </div>
                          <div>
                            <h3 className="text-sm font-bold text-emerald-900 uppercase tracking-wider mb-1 flex items-center gap-2">
                              C3MS AI Analysis
                              <Badge variant="success" className="bg-emerald-200 text-emerald-800 text-[10px] px-2 py-0">
                                {data.aiAnalysis.confidence} Confidence
                              </Badge>
                            </h3>
                            <p className="text-emerald-800 text-sm leading-relaxed mb-3">
                              {data.aiAnalysis.summary}
                            </p>
                            <div className="flex flex-wrap gap-2">
                              {data.aiAnalysis.flags.map((flag, idx) => (
                                <span key={idx} className="inline-flex items-center text-xs font-medium text-emerald-700 bg-emerald-100/50 px-2.5 py-1 rounded-md border border-emerald-200/50">
                                  <AlertTriangle className="w-3 h-3 mr-1.5" />
                                  {flag}
                                </span>
                              ))}
                            </div>
                          </div>
                        </div>
                      </div>

                      {/* Description */}
                      <div className="prose prose-slate max-w-none mb-10">
                        <h3 className="text-lg font-semibold text-slate-900 font-display mb-4">Complaint Description</h3>
                        {data.description.split('\n\n').map((paragraph, idx) => (
                          <p key={idx} className="text-slate-600 leading-relaxed mb-4">
                            {paragraph}
                          </p>
                        ))}
                      </div>

                      {/* Metadata Grid */}
                      <h3 className="text-lg font-semibold text-slate-900 font-display mb-4">Case Metadata</h3>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div className="p-4 rounded-lg border border-slate-100 bg-slate-50 flex items-start gap-3">
                          <Building className="w-5 h-5 text-slate-400 mt-0.5" />
                          <div>
                            <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">Department</p>
                            <p className="text-sm font-medium text-slate-900">{data.category}</p>
                          </div>
                        </div>
                        <div className="p-4 rounded-lg border border-slate-100 bg-slate-50 flex items-start gap-3">
                          <MapPin className="w-5 h-5 text-slate-400 mt-0.5" />
                          <div>
                            <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">Location</p>
                            <p className="text-sm font-medium text-slate-900">{data.location}</p>
                          </div>
                        </div>
                        <div className="p-4 rounded-lg border border-slate-100 bg-slate-50 flex items-start gap-3">
                          <Calendar className="w-5 h-5 text-slate-400 mt-0.5" />
                          <div>
                            <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">Date Reported</p>
                            <p className="text-sm font-medium text-slate-900">
                              {new Date(data.dateSubmitted).toLocaleDateString('en-IN')}
                            </p>
                          </div>
                        </div>
                        <div className="p-4 rounded-lg border border-slate-100 bg-slate-50 flex items-start gap-3">
                          <AlertTriangle className="w-5 h-5 text-slate-400 mt-0.5" />
                          <div>
                            <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">Estimated Value</p>
                            <p className="text-sm font-medium text-slate-900">{data.estimatedValue}</p>
                          </div>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* TAB 2: EVIDENCE & BLOCKCHAIN */}
                  {activeTab === 'evidence' && (
                    <div className="p-6 sm:p-8 animate-in fade-in duration-500">
                      <div className="flex items-center justify-between mb-6">
                        <h3 className="text-lg font-semibold text-slate-900 font-display">Submitted Evidence</h3>
                        <Badge variant="outline" className="bg-slate-50">
                          <Lock className="w-3 h-3 mr-1.5 text-emerald-600" />
                          Zero-Knowledge Encrypted
                        </Badge>
                      </div>

                      <div className="space-y-4 mb-10">
                        {data.evidence.map((item) => (
                          <div key={item.id} className="flex flex-col sm:flex-row sm:items-center justify-between p-4 rounded-xl border border-slate-200 hover:border-emerald-300 hover:shadow-sm transition-all bg-white group gap-4">
                            <div className="flex items-start gap-4">
                              <div className="p-2.5 bg-slate-100 text-slate-600 rounded-lg group-hover:bg-emerald-50 group-hover:text-emerald-600 transition-colors">
                                {item.type === 'document' ? <FileText className="w-6 h-6" /> : 
                                 item.type === 'archive' ? <FileDigit className="w-6 h-6" /> : 
                                 <Activity className="w-6 h-6" />}
                              </div>
                              <div>
                                <p className="text-sm font-medium text-slate-900 mb-1">{item.name}</p>
                                <div className="flex items-center gap-3 text-xs text-slate-500">
                                  <span>{item.size}</span>
                                  <span className="w-1 h-1 rounded-full bg-slate-300"></span>
                                  <span className="font-mono text-slate-400">{item.hash.substring(0, 10)}...</span>
                                </div>
                              </div>
                            </div>
                            <div className="flex items-center gap-2 self-end sm:self-auto">
                              {item.verified ? (
                                <Badge variant="success" className="bg-emerald-50 text-emerald-700 border-emerald-200">
                                  <CheckCircle className="w-3 h-3 mr-1" /> Verified
                                </Badge>
                              ) : (
                                <Badge variant="warning" className="bg-amber-50 text-amber-700 border-amber-200">
                                  <Clock className="w-3 h-3 mr-1" /> Pending
                                </Badge>
                              )}
                              <Button variant="outline" size="sm" onClick={() => handleViewEvidence(item)}>
                                <Eye className="w-4 h-4 mr-1.5" /> View
                              </Button>
                            </div>
                          </div>
                        ))}
                      </div>

                      {/* Blockchain Ledger Card */}
                      <div className="rounded-xl bg-slate-900 text-slate-300 p-6 overflow-hidden relative">
                        <div className="absolute top-0 right-0 p-4 opacity-10">
                          <Server className="w-32 h-32" />
                        </div>
                        <div className="relative z-10">
                          <h4 className="text-white font-display font-medium mb-4 flex items-center gap-2">
                            <ShieldCheck className="w-5 h-5 text-emerald-400" />
                            Blockchain Ledger Verification
                          </h4>
                          <p className="text-sm text-slate-400 mb-6 max-w-md">
                            All evidence files and complaint metadata have been cryptographically hashed and stored on the immutable C3MS ledger to ensure chain of custody.
                          </p>
                          
                          <div className="space-y-3 font-mono text-xs">
                            <div className="flex justify-between border-b border-slate-800 pb-2">
                              <span className="text-slate-500">Block Height:</span>
                              <span className="text-emerald-400">#14,892,041</span>
                            </div>
                            <div className="flex justify-between border-b border-slate-800 pb-2">
                              <span className="text-slate-500">Timestamp:</span>
                              <span className="text-slate-300">2023-10-24 10:30:15 UTC</span>
                            </div>
                            <div className="flex justify-between border-b border-slate-800 pb-2">
                              <span className="text-slate-500">Root Hash:</span>
                              <span className="text-slate-300 truncate max-w-[200px] sm:max-w-xs">0x9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08</span>
                            </div>
                            <div className="flex justify-between pt-1">
                              <span className="text-slate-500">Network Status:</span>
                              <span className="text-emerald-400 flex items-center gap-1">
                                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                                Synced & Verified
                              </span>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* TAB 3: ACTIVITY TIMELINE */}
                  {activeTab === 'activity' && (
                    <div className="p-6 sm:p-8 animate-in fade-in duration-500">
                      <h3 className="text-lg font-semibold text-slate-900 font-display mb-6">Investigation History</h3>
                      {/* Using the imported TimelineList which has its own rich mock data */}
                      <TimelineList />
                    </div>
                  )}

                  {/* TAB 4: RELATED CASES */}
                  {activeTab === 'related' && (
                    <div className="p-6 sm:p-8 animate-in fade-in duration-500 bg-slate-50/50">
                      <div className="flex items-center justify-between mb-6">
                        <h3 className="text-lg font-semibold text-slate-900 font-display">Similar Reports</h3>
                        <Button variant="ghost" size="sm" className="text-emerald-600">
                          View All <ArrowUpRight className="w-4 h-4 ml-1" />
                        </Button>
                      </div>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                        {data.relatedCases.map(caseItem => (
                          <ItemCard key={caseItem.id} item={caseItem} />
                        ))}
                      </div>
                    </div>
                  )}
                </TabbedPanel>
              </Card>
            </div>

            {/* RIGHT COLUMN: Sticky Sidebar */}
            <div className="lg:col-span-1 space-y-6">
              <div className="sticky top-24 space-y-6">
                
                {/* Status & Action Card */}
                <Card className="p-6 shadow-md border-slate-200/60">
                  <div className="flex flex-col items-center text-center mb-6">
                    {/* Circular Credibility Score */}
                    <div className="relative w-24 h-24 mb-4">
                      <svg className="w-full h-full transform -rotate-90" viewBox="0 0 36 36">
                        <path
                          className="text-slate-100"
                          strokeWidth="3"
                          stroke="currentColor"
                          fill="none"
                          d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                        />
                        <path
                          className="text-emerald-500"
                          strokeWidth="3"
                          strokeDasharray={`${data.credibilityScore}, 100`}
                          strokeLinecap="round"
                          stroke="currentColor"
                          fill="none"
                          d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                        />
                      </svg>
                      <div className="absolute inset-0 flex flex-col items-center justify-center">
                        <span className="text-2xl font-bold text-slate-900 font-display">{data.credibilityScore}</span>
                        <span className="text-[10px] font-medium text-slate-500 uppercase">Score</span>
                      </div>
                    </div>
                    
                    <h3 className="text-lg font-semibold text-slate-900 font-display mb-1">High Credibility</h3>
                    <p className="text-sm text-slate-500">AI verified based on evidence and historical patterns.</p>
                  </div>

                  <div className="space-y-3">
                    <Button 
                      className="w-full justify-center" 
                      variant={isFollowing ? "secondary" : "default"}
                      onClick={() => setIsFollowing(!isFollowing)}
                    >
                      {isFollowing ? (
                        <><Check className="w-4 h-4 mr-2" /> Following Updates</>
                      ) : (
                        <><Bookmark className="w-4 h-4 mr-2" /> Follow Case</>
                      )}
                    </Button>
                    <div className="grid grid-cols-2 gap-3">
                      <Button variant="outline" className="w-full" onClick={handleShare}>
                        <Share2 className="w-4 h-4 mr-2" /> Share
                      </Button>
                      <Button variant="outline" className="w-full">
                        <Download className="w-4 h-4 mr-2" /> Export
                      </Button>
                    </div>
                  </div>
                </Card>

                {/* Assigned Officer Card */}
                <Card className="p-6 shadow-sm border-slate-200/60">
                  <h4 className="text-sm font-bold text-slate-900 uppercase tracking-wider mb-4 flex items-center gap-2">
                    <Shield className="w-4 h-4 text-emerald-600" />
                    Assigned Investigation
                  </h4>
                  
                  <div className="flex items-center gap-4 mb-4">
                    <Avatar src={userProfile.avatar} fallback="RK" className="w-12 h-12" />
                    <div>
                      <p className="text-sm font-semibold text-slate-900">{userProfile.name}</p>
                      <p className="text-xs text-slate-500">{userProfile.role}</p>
                    </div>
                  </div>
                  
                  <div className="bg-slate-50 rounded-lg p-3 text-xs text-slate-600 mb-4 border border-slate-100">
                    <p className="flex justify-between mb-1">
                      <span>Cases Resolved:</span>
                      <span className="font-medium text-slate-900">{userProfile.stats.casesResolved}</span>
                    </p>
                    <p className="flex justify-between">
                      <span>Success Rate:</span>
                      <span className="font-medium text-emerald-600">{userProfile.stats.successRate}</span>
                    </p>
                  </div>

                  <Button variant="secondary" className="w-full text-sm">
                    <MessageSquare className="w-4 h-4 mr-2" /> Contact Officer
                  </Button>
                </Card>

                {/* Info Box */}
                <div className="bg-blue-50 border border-blue-100 rounded-xl p-4 flex items-start gap-3">
                  <ShieldCheck className="w-5 h-5 text-blue-600 shrink-0 mt-0.5" />
                  <p className="text-xs text-blue-800 leading-relaxed">
                    <strong>Whistleblower Protection Act</strong> applies to this case. The identity of the reporter is cryptographically shielded and cannot be accessed by department officials.
                  </p>
                </div>

              </div>
            </div>

          </div>
        </div>
      </div>

      {/* --- TOAST NOTIFICATION (Simulated) --- */}
      {showShareToast && (
        <div className="fixed bottom-4 right-4 bg-slate-900 text-white px-4 py-3 rounded-lg shadow-lg flex items-center gap-3 animate-in slide-in-from-bottom-5 z-50">
          <CheckCircle className="w-5 h-5 text-emerald-400" />
          <span className="text-sm font-medium">Link copied to clipboard!</span>
        </div>
      )}

      {/* --- EVIDENCE MODAL (Simulated) --- */}
      {isEvidenceModalOpen && selectedEvidence && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/80 backdrop-blur-sm animate-in fade-in">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl overflow-hidden flex flex-col max-h-[90vh]">
            <div className="flex items-center justify-between p-4 border-b border-slate-100">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-slate-100 rounded-lg text-slate-600">
                  {selectedEvidence.type === 'document' ? <FileText className="w-5 h-5" /> : <FileDigit className="w-5 h-5" />}
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-slate-900">{selectedEvidence.name}</h3>
                  <p className="text-xs text-slate-500">{selectedEvidence.size} • {selectedEvidence.hash.substring(0, 12)}...</p>
                </div>
              </div>
              <button 
                onClick={() => setIsEvidenceModalOpen(false)}
                className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-full transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-8 flex-1 overflow-y-auto bg-slate-50 flex flex-col items-center justify-center min-h-[300px]">
              <FileText className="w-16 h-16 text-slate-300 mb-4" />
              <p className="text-slate-500 text-sm mb-6 text-center max-w-sm">
                Secure document viewer simulation. In a real environment, this would render the PDF or image securely without allowing downloads if restricted.
              </p>
              <Button>
                <Download className="w-4 h-4 mr-2" /> Download Encrypted File
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* --- SIMPLE FOOTER --- */}
      <footer className="bg-white border-t border-slate-200 py-8 mt-auto">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col md:flex-row justify-between items-center gap-4">
          <div className="flex items-center gap-2">
            <Shield className="h-5 w-5 text-emerald-600" />
            <span className="font-display font-bold text-slate-900">Vigilance C3MS</span>
          </div>
          <p className="text-sm text-slate-500">
            © 2023 Government of Kerala. All rights reserved. Secured by Blockchain.
          </p>
        </div>
      </footer>
    </AppShell>
  );
}
