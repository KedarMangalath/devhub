import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { complaints, auditLogs } from '../mockData';
import Navbar from '../components/layout/Navbar';
import StatusTimeline from '../components/complaint/StatusTimeline';
import AIAnalysisPanel from '../components/complaint/AIAnalysisPanel';
import BlockchainVerification from '../components/complaint/BlockchainVerification';
import Footer from '../components/layout/Footer';
import { 
  ArrowLeft, 
  MapPin, 
  Calendar, 
  Shield, 
  FileText, 
  AlertTriangle, 
  CheckCircle, 
  Clock, 
  Share2, 
  Printer, 
  Download, 
  MessageSquare, 
  User, 
  Building, 
  Hash, 
  Eye, 
  Lock, 
  ChevronRight, 
  Paperclip, 
  Send, 
  Plus,
  Image as ImageIcon,
  FileDigit
} from 'lucide-react';

// ============================================================================
// INLINE UI PRIMITIVES
// ============================================================================

const Badge = ({ children, variant = 'default', className = '' }) => {
  const variants = {
    default: 'bg-secondary text-secondary-foreground border-border',
    success: 'bg-emerald-500/10 text-emerald-700 border-emerald-500/20 dark:text-emerald-400',
    warning: 'bg-amber-500/10 text-amber-700 border-amber-500/20 dark:text-amber-400',
    danger: 'bg-rose-500/10 text-rose-700 border-rose-500/20 dark:text-rose-400',
    primary: 'bg-primary/10 text-primary border-primary/20',
  };
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border ${variants[variant]} ${className}`}>
      {children}
    </span>
  );
};

const Button = ({ children, variant = 'primary', size = 'md', className = '', icon: Icon, ...props }) => {
  const variants = {
    primary: 'bg-primary text-white hover:bg-primary/90 shadow-sm',
    secondary: 'bg-secondary text-secondary-foreground hover:bg-secondary/80 border border-border',
    outline: 'bg-transparent text-foreground border border-border hover:bg-secondary',
    ghost: 'bg-transparent text-muted-foreground hover:text-foreground hover:bg-secondary',
    danger: 'bg-rose-600 text-white hover:bg-rose-700 shadow-sm',
  };
  const sizes = {
    sm: 'px-3 py-1.5 text-xs',
    md: 'px-4 py-2 text-sm',
    lg: 'px-6 py-3 text-base',
    icon: 'p-2',
  };
  return (
    <button 
      className={`inline-flex items-center justify-center rounded-lg font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-primary/50 disabled:opacity-50 disabled:pointer-events-none ${variants[variant]} ${sizes[size]} ${className}`}
      {...props}
    >
      {Icon && <Icon className={`w-4 h-4 ${children ? 'mr-2' : ''}`} />}
      {children}
    </button>
  );
};

// ============================================================================
// MAIN PAGE COMPONENT
// ============================================================================

export default function ComplaintDetail() {
  const { id } = useParams();
  
  // 1. State Management
  const [activeTab, setActiveTab] = useState('overview');
  const [isShareModalOpen, setIsShareModalOpen] = useState(false);
  const [noteText, setNoteText] = useState('');
  const [notes, setNotes] = useState([
    { id: 1, author: 'Inspector Priya', role: 'Lead Investigator', text: 'Initial review complete. The attached audio file has been sent to the forensics lab for voice matching.', date: '2023-10-25T10:00:00Z' },
    { id: 2, author: 'System AI', role: 'Automated Analysis', text: 'Cross-referenced location data with 3 other recent complaints. High probability of systemic issue at this specific node.', date: '2023-10-24T14:30:00Z' }
  ]);

  // 2. Data Resolution & Fallbacks
  // Find the complaint or fallback to a rich mock object to ensure zero blank UI
  const rawComplaint = complaints?.find(c => c.id === id) || complaints?.[0];
  
  const complaint = {
    id: rawComplaint?.id || id || 'CMP-2023-8842',
    title: rawComplaint?.title || 'Fraudulent Road Contract Allocation in District 4',
    description: rawComplaint?.description || 'Observed severe irregularities in the recent tender process for the NH-44 bypass. Documents suggest pre-approval of unqualified vendors linked to local officials. The attached files contain the original tender requirements alongside the modified version that was ultimately approved. I request an immediate audit of the financial trails.',
    category: rawComplaint?.category || 'Public Works (PWD)',
    location: rawComplaint?.location || 'Thiruvananthapuram, Kerala',
    date: rawComplaint?.date || '2023-10-24T10:30:00Z',
    status: rawComplaint?.status || 'Investigating',
    credibilityScore: rawComplaint?.credibilityScore || 92,
    isAnonymous: rawComplaint?.isAnonymous !== undefined ? rawComplaint.isAnonymous : true,
    evidenceCount: rawComplaint?.evidenceCount || 3,
    evidenceFiles: [
      { id: 'ev-1', type: 'image', name: 'site_inspection_photo_1.jpg', size: '2.4 MB', url: 'https://images.unsplash.com/photo-1584467735815-f778f274e296?w=800&q=80' },
      { id: 'ev-2', type: 'document', name: 'tender_document_forged.pdf', size: '4.1 MB', url: '#' },
      { id: 'ev-3', type: 'audio', name: 'recorded_conversation.mp3', size: '1.2 MB', url: '#' }
    ],
    department: {
      name: 'Public Works Department (PWD)',
      head: 'Chief Engineer R. Menon',
      riskLevel: 'High',
      activeCases: 14
    }
  };

  // Filter logs for this specific complaint, or use defaults
  const timelineLogs = auditLogs?.filter(log => log.complaintId === complaint.id) || [
    { id: 'log-1', status: 'Investigation Active', timestamp: '2023-10-25T09:15:00Z', description: 'Assigned to Inspector Priya. Field visit scheduled.', type: 'pending' },
    { id: 'log-2', status: 'AI Credibility Flag', timestamp: '2023-10-24T11:05:00Z', description: 'High confidence match with previous PWD bribery patterns.', type: 'alert' },
    { id: 'log-3', status: 'Complaint Submitted', timestamp: '2023-10-24T10:30:00Z', description: 'Encrypted payload received via secure portal.', type: 'success' }
  ];

  // 3. Handlers
  const handleAddNote = (e) => {
    e.preventDefault();
    if (!noteText.trim()) return;
    
    const newNoteObj = {
      id: Date.now(),
      author: 'Current User',
      role: 'Investigator',
      text: noteText,
      date: new Date().toISOString()
    };
    
    setNotes([newNoteObj, ...notes]);
    setNoteText('');
  };

  const formatDate = (dateString) => {
    return new Intl.DateTimeFormat('en-IN', {
      year: 'numeric', month: 'long', day: 'numeric',
      hour: '2-digit', minute: '2-digit'
    }).format(new Date(dateString));
  };

  const getStatusBadge = (status) => {
    switch(status.toLowerCase()) {
      case 'resolved': return <Badge variant="success"><CheckCircle className="w-3 h-3 mr-1"/> Resolved</Badge>;
      case 'investigating': return <Badge variant="warning"><Clock className="w-3 h-3 mr-1"/> Investigating</Badge>;
      case 'high-risk': return <Badge variant="danger"><AlertTriangle className="w-3 h-3 mr-1"/> High Risk</Badge>;
      default: return <Badge variant="default">{status}</Badge>;
    }
  };

  // 4. Render 404 State if somehow data is completely missing (though fallback prevents this usually)
  if (!complaint) {
    return (
      <div className="min-h-screen flex flex-col bg-background font-body">
        <Navbar />
        <main className="flex-grow flex items-center justify-center p-6">
          <div className="text-center max-w-md">
            <div className="bg-secondary w-20 h-20 rounded-full flex items-center justify-center mx-auto mb-6">
              <FileDigit className="w-10 h-10 text-muted-foreground" />
            </div>
            <h1 className="font-display text-3xl font-bold text-foreground mb-4">Complaint Not Found</h1>
            <p className="text-muted-foreground mb-8">The record you are looking for does not exist or you do not have permission to view it.</p>
            <Link to="/explore">
              <Button icon={ArrowLeft}>Back to Directory</Button>
            </Link>
          </div>
        </main>
        <Footer />
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col bg-background font-body text-foreground selection:bg-primary/20">
      {/* SECTION 1: Navbar */}
      <Navbar />

      <main className="flex-grow pb-20">
        {/* SECTION 2: Breadcrumbs & Action Bar */}
        <div className="bg-card border-b border-border sticky top-16 z-30 shadow-sm">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-14 flex items-center justify-between">
            <nav className="flex items-center space-x-2 text-sm text-muted-foreground">
              <Link to="/explore" className="hover:text-primary transition-colors flex items-center">
                <ArrowLeft className="w-4 h-4 mr-1" />
                Directory
              </Link>
              <ChevronRight className="w-4 h-4" />
              <span className="truncate max-w-[200px] sm:max-w-xs">{complaint.category}</span>
              <ChevronRight className="w-4 h-4" />
              <span className="font-medium text-foreground truncate max-w-[100px] sm:max-w-[200px]">{complaint.id}</span>
            </nav>
            
            <div className="flex items-center space-x-2">
              <Button variant="ghost" size="icon" onClick={() => setIsShareModalOpen(true)} title="Share">
                <Share2 className="w-4 h-4" />
              </Button>
              <Button variant="ghost" size="icon" title="Print Record">
                <Printer className="w-4 h-4" />
              </Button>
              <Button variant="outline" size="sm" icon={Download} className="hidden sm:flex">
                Export PDF
              </Button>
            </div>
          </div>
        </div>

        {/* SECTION 3: Page Header */}
        <header className="bg-card border-b border-border pt-10 pb-12">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex flex-col md:flex-row md:items-start justify-between gap-6">
              <div className="flex-1">
                <div className="flex items-center gap-3 mb-4">
                  {getStatusBadge(complaint.status)}
                  <Badge variant="primary">{complaint.category}</Badge>
                  {complaint.isAnonymous && (
                    <Badge variant="default" className="bg-slate-800 text-slate-200 border-slate-700">
                      <Lock className="w-3 h-3 mr-1" /> Anonymous
                    </Badge>
                  )}
                </div>
                
                <h1 className="font-display text-3xl sm:text-4xl font-bold text-foreground tracking-tight mb-4 leading-tight">
                  {complaint.title}
                </h1>
                
                <div className="flex flex-wrap items-center gap-y-3 gap-x-6 text-sm text-muted-foreground">
                  <div className="flex items-center">
                    <Hash className="w-4 h-4 mr-1.5 text-primary" />
                    <span className="font-mono">{complaint.id}</span>
                  </div>
                  <div className="flex items-center">
                    <Calendar className="w-4 h-4 mr-1.5 text-primary" />
                    {formatDate(complaint.date)}
                  </div>
                  <div className="flex items-center">
                    <MapPin className="w-4 h-4 mr-1.5 text-primary" />
                    {complaint.location}
                  </div>
                  <div className="flex items-center">
                    <Eye className="w-4 h-4 mr-1.5 text-primary" />
                    Public Record
                  </div>
                </div>
              </div>
              
              {/* Quick Stats Block */}
              <div className="flex gap-4 md:flex-col lg:flex-row shrink-0">
                <div className="bg-secondary/50 border border-border rounded-xl p-4 flex flex-col items-center justify-center min-w-[120px]">
                  <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1">AI Score</span>
                  <div className="flex items-baseline gap-1">
                    <span className={`font-display text-3xl font-bold ${complaint.credibilityScore >= 80 ? 'text-emerald-600' : 'text-amber-600'}`}>
                      {complaint.credibilityScore}
                    </span>
                    <span className="text-sm text-muted-foreground">/100</span>
                  </div>
                </div>
                <div className="bg-secondary/50 border border-border rounded-xl p-4 flex flex-col items-center justify-center min-w-[120px]">
                  <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1">Evidence</span>
                  <div className="flex items-baseline gap-1">
                    <span className="font-display text-3xl font-bold text-foreground">
                      {complaint.evidenceCount}
                    </span>
                    <span className="text-sm text-muted-foreground">Files</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </header>

        {/* SECTION 4: Main Content Grid */}
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            
            {/* LEFT COLUMN (Main Content) */}
            <div className="lg:col-span-2 space-y-8">
              
              {/* SECTION 5: Custom Tabs Navigation */}
              <div className="bg-card border border-border rounded-xl p-1 shadow-sm flex overflow-x-auto hide-scrollbar">
                {['overview', 'evidence', 'timeline'].map((tab) => (
                  <button
                    key={tab}
                    onClick={() => setActiveTab(tab)}
                    className={`flex-1 min-w-[120px] py-2.5 px-4 text-sm font-medium rounded-lg transition-all capitalize ${
                      activeTab === tab 
                        ? 'bg-primary text-white shadow-md' 
                        : 'text-muted-foreground hover:text-foreground hover:bg-secondary'
                    }`}
                  >
                    {tab}
                  </button>
                ))}
              </div>

              {/* TAB CONTENT: OVERVIEW */}
              {activeTab === 'overview' && (
                <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
                  
                  {/* Narrative Section */}
                  <section className="bg-card border border-border rounded-xl p-6 shadow-sm">
                    <h3 className="font-display text-lg font-semibold text-foreground mb-4 flex items-center">
                      <FileText className="w-5 h-5 mr-2 text-primary" />
                      Complaint Narrative
                    </h3>
                    <div className="prose prose-slate dark:prose-invert max-w-none">
                      <p className="text-foreground leading-relaxed whitespace-pre-wrap font-body text-base">
                        {complaint.description}
                      </p>
                    </div>
                    
                    {/* AI Extracted Entities (Mock) */}
                    <div className="mt-8 pt-6 border-t border-border">
                      <h4 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-4">
                        AI Extracted Entities
                      </h4>
                      <div className="flex flex-wrap gap-2">
                        <Badge variant="secondary"><User className="w-3 h-3 mr-1"/> R. Menon (Mentioned)</Badge>
                        <Badge variant="secondary"><Building className="w-3 h-3 mr-1"/> NH-44 Bypass Project</Badge>
                        <Badge variant="secondary"><MapPin className="w-3 h-3 mr-1"/> District 4 PWD Office</Badge>
                      </div>
                    </div>
                  </section>

                  {/* SECTION 6: Investigator Notes (Interactive) */}
                  <section className="bg-card border border-border rounded-xl p-6 shadow-sm">
                    <h3 className="font-display text-lg font-semibold text-foreground mb-6 flex items-center justify-between">
                      <div className="flex items-center">
                        <MessageSquare className="w-5 h-5 mr-2 text-primary" />
                        Investigator Notes
                      </div>
                      <Badge variant="secondary">{notes.length} Notes</Badge>
                    </h3>
                    
                    {/* Add Note Form */}
                    <form onSubmit={handleAddNote} className="mb-8">
                      <div className="relative">
                        <textarea
                          value={noteText}
                          onChange={(e) => setNoteText(e.target.value)}
                          placeholder="Add a secure internal note or update..."
                          className="w-full bg-secondary/50 border border-border rounded-xl p-4 pr-12 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary resize-none min-h-[100px]"
                        />
                        <div className="absolute bottom-3 right-3">
                          <Button type="submit" size="icon" variant="primary" disabled={!noteText.trim()}>
                            <Send className="w-4 h-4" />
                          </Button>
                        </div>
                      </div>
                    </form>

                    {/* Notes List */}
                    <div className="space-y-4">
                      {notes.map((note) => (
                        <div key={note.id} className="bg-secondary/30 border border-border rounded-lg p-4">
                          <div className="flex justify-between items-start mb-2">
                            <div className="flex items-center gap-2">
                              <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center text-primary font-bold text-xs">
                                {note.author.charAt(0)}
                              </div>
                              <div>
                                <p className="text-sm font-semibold text-foreground">{note.author}</p>
                                <p className="text-xs text-muted-foreground">{note.role}</p>
                              </div>
                            </div>
                            <span className="text-xs text-muted-foreground">
                              {new Date(note.date).toLocaleDateString()}
                            </span>
                          </div>
                          <p className="text-sm text-foreground mt-2 pl-10">
                            {note.text}
                          </p>
                        </div>
                      ))}
                    </div>
                  </section>
                </div>
              )}

              {/* TAB CONTENT: EVIDENCE */}
              {activeTab === 'evidence' && (
                <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
                  <section className="bg-card border border-border rounded-xl p-6 shadow-sm">
                    <div className="flex items-center justify-between mb-6">
                      <h3 className="font-display text-lg font-semibold text-foreground flex items-center">
                        <Paperclip className="w-5 h-5 mr-2 text-primary" />
                        Attached Evidence ({complaint.evidenceFiles.length})
                      </h3>
                      <Button variant="outline" size="sm" icon={Download}>Download All</Button>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      {complaint.evidenceFiles.map((file) => (
                        <div key={file.id} className="group relative border border-border rounded-xl overflow-hidden bg-secondary/20 hover:border-primary/50 transition-colors">
                          {file.type === 'image' ? (
                            <div className="aspect-video w-full overflow-hidden bg-slate-900">
                              <img src={file.url} alt={file.name} className="w-full h-full object-cover opacity-80 group-hover:opacity-100 transition-opacity" />
                            </div>
                          ) : (
                            <div className="aspect-video w-full flex flex-col items-center justify-center bg-secondary/50">
                              <FileText className="w-10 h-10 text-muted-foreground mb-2" />
                              <span className="text-xs font-medium text-muted-foreground uppercase">{file.type}</span>
                            </div>
                          )}
                          <div className="p-3 border-t border-border bg-card flex items-center justify-between">
                            <div className="truncate pr-4">
                              <p className="text-sm font-medium text-foreground truncate">{file.name}</p>
                              <p className="text-xs text-muted-foreground">{file.size}</p>
                            </div>
                            <Button variant="ghost" size="icon" className="shrink-0">
                              <Eye className="w-4 h-4" />
                            </Button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </section>
                </div>
              )}

              {/* TAB CONTENT: TIMELINE */}
              {activeTab === 'timeline' && (
                <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
                  <section className="bg-card border border-border rounded-xl p-6 shadow-sm">
                    <h3 className="font-display text-lg font-semibold text-foreground mb-8 flex items-center">
                      <Clock className="w-5 h-5 mr-2 text-primary" />
                      Audit Trail & Timeline
                    </h3>
                    {/* SECTION 7: Status Timeline Component */}
                    <StatusTimeline logs={timelineLogs} />
                  </section>
                </div>
              )}

            </div>

            {/* RIGHT COLUMN (Sidebar) */}
            <div className="lg:col-span-1 space-y-6">
              
              {/* SECTION 8: Action Panel */}
              <div className="bg-card border border-border rounded-xl p-6 shadow-sm">
                <h3 className="font-display text-base font-semibold text-foreground mb-4">Investigator Actions</h3>
                <div className="space-y-3">
                  <Button variant="primary" className="w-full justify-start" icon={CheckCircle}>
                    Mark as Resolved
                  </Button>
                  <Button variant="outline" className="w-full justify-start" icon={User}>
                    Assign Investigator
                  </Button>
                  <Button variant="outline" className="w-full justify-start text-rose-600 hover:bg-rose-50 hover:text-rose-700 dark:hover:bg-rose-950/30 border-rose-200 dark:border-rose-900" icon={AlertTriangle}>
                    Escalate to HQ
                  </Button>
                </div>
              </div>

              {/* SECTION 9: AI Analysis Panel */}
              <div className="sticky top-32 space-y-6">
                <AIAnalysisPanel score={complaint.credibilityScore} />
                
                {/* SECTION 10: Blockchain Verification */}
                <BlockchainVerification 
                  hash={`0x${Math.random().toString(16).slice(2, 10)}${complaint.id.replace(/\D/g,'')}a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1`}
                  timestamp={complaint.date}
                />

                {/* SECTION 11: Department Context Card */}
                <div className="bg-card border border-border rounded-xl p-5 shadow-sm">
                  <h3 className="font-display text-sm font-semibold text-foreground mb-3 uppercase tracking-wider flex items-center">
                    <Building className="w-4 h-4 mr-2 text-muted-foreground" />
                    Department Context
                  </h3>
                  <div className="space-y-3">
                    <div>
                      <p className="text-xs text-muted-foreground mb-1">Department</p>
                      <p className="text-sm font-medium text-foreground">{complaint.department.name}</p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground mb-1">Node Head</p>
                      <p className="text-sm font-medium text-foreground">{complaint.department.head}</p>
                    </div>
                    <div className="flex items-center justify-between pt-2 border-t border-border">
                      <span className="text-xs text-muted-foreground">Active Cases</span>
                      <Badge variant="warning">{complaint.department.activeCases} Open</Badge>
                    </div>
                  </div>
                </div>
              </div>

            </div>
          </div>
        </div>
      </main>

      {/* SECTION 12: Footer */}
      <Footer />

      {/* Share Modal (Interactive State Demo) */}
      {isShareModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm p-4 animate-in fade-in duration-200">
          <div className="bg-card border border-border rounded-xl shadow-xl w-full max-w-md overflow-hidden">
            <div className="p-4 border-b border-border flex justify-between items-center bg-secondary/50">
              <h3 className="font-display font-semibold text-foreground">Share Record</h3>
              <button onClick={() => setIsShareModalOpen(false)} className="text-muted-foreground hover:text-foreground">
                <Plus className="w-5 h-5 rotate-45" />
              </button>
            </div>
            <div className="p-6 space-y-4">
              <p className="text-sm text-muted-foreground">Anyone with this link can view the public details of this record. Sensitive evidence remains encrypted.</p>
              <div className="flex items-center gap-2">
                <input 
                  type="text" 
                  readOnly 
                  value={`https://c3ms.kerala.gov.in/complaints/${complaint.id}`}
                  className="flex-1 bg-secondary border border-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none"
                />
                <Button variant="primary" onClick={() => {
                  navigator.clipboard.writeText(`https://c3ms.kerala.gov.in/complaints/${complaint.id}`);
                  setIsShareModalOpen(false);
                }}>Copy</Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
