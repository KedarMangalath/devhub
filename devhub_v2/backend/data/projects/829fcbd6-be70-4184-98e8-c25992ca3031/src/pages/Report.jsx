import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { 
  ShieldCheck, 
  Lock, 
  Shield, 
  ChevronRight, 
  CheckCircle2, 
  AlertTriangle, 
  FileText, 
  BrainCircuit, 
  Database, 
  ArrowRight, 
  Info, 
  HelpCircle, 
  ChevronDown, 
  ChevronUp,
  Menu,
  X,
  EyeOff,
  FileKey,
  Fingerprint,
  Building2
} from 'lucide-react';

// Exact imports as requested
import MinimalNavbar from '../components/layout/MinimalNavbar';
import WorkflowStepper from '../components/report/WorkflowStepper';
import MinimalFooter from '../components/layout/MinimalFooter';

// Import mock data
import { categories } from '../mockData';

// ============================================================================
// INLINE UI PRIMITIVES
// ============================================================================

const Badge = ({ children, variant = 'default', className = '' }) => {
  const variants = {
    default: 'bg-slate-800 text-slate-300 border-slate-700',
    success: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
    warning: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
    danger: 'bg-rose-500/10 text-rose-400 border-rose-500/20',
    info: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
    primary: 'bg-emerald-600 text-white border-emerald-500',
  };
  
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${variants[variant]} ${className}`}>
      {children}
    </span>
  );
};

const Card = ({ children, className = '' }) => (
  <div className={`bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-lg ${className}`}>
    {children}
  </div>
);

// ============================================================================
// WIREFRAME DATA
// ============================================================================

const wireframeData = {
  navbar: {
    logo: { text: "Vigilance C3MS", icon: ShieldCheck, href: "/" },
    links: [
      { label: "Dashboard", href: "/dashboard" },
      { label: "Track Complaint", href: "/track" },
      { label: "Department Analytics", href: "/departments" },
      { label: "Whistleblower Policy", href: "/policy" }
    ],
    cta: { label: "Secure Officer Login", href: "/login", icon: Lock }
  },
  timeline: {
    title: "Transparent Complaint Lifecycle: From Secure Submission to Final Resolution",
    items: [
      {
        date: "Step 1 - Immediate",
        title: "Secure Data Entry & Evidence Upload",
        body: "Citizens provide detailed incident descriptions and upload supporting documents, audio, or video evidence through an encrypted, anonymous portal ensuring complete identity protection.",
        status: "Active"
      },
      {
        date: "Step 2 - Within Minutes",
        title: "AI Credibility Check & Risk Scoring",
        body: "Our proprietary AI engine analyzes the submitted evidence, cross-references historical departmental data, and assigns a preliminary credibility and risk score to prioritize severe cases.",
        status: "Automated"
      },
      {
        date: "Step 3 - 1 to 3 Days",
        title: "Nodal Officer Review & Blockchain Logging",
        body: "Assigned nodal officers review the AI-scored report. Every action, view, and status update is immutably logged on the blockchain to ensure absolute transparency and prevent tampering.",
        status: "Investigating"
      },
      {
        date: "Step 4 - 4 to 15 Days",
        title: "Departmental Inquiry & Field Investigation",
        body: "The respective government department (e.g., Public Works Department or Revenue Department) conducts a thorough field investigation based on the verified evidence and AI insights.",
        status: "High Risk"
      },
      {
        date: "Step 5 - 16 to 30 Days",
        title: "Final Verdict & Public Fund Recovery",
        body: "Disciplinary actions are strictly enforced, stolen public funds are recovered, and the citizen is notified of the successful resolution while maintaining their strict anonymity.",
        status: "Resolved"
      }
    ]
  },
  footer: {
    brand: {
      name: "Vigilance C3MS",
      description: "Empowering citizens to securely report, track, and combat corruption with AI-driven transparency and 100% blockchain-backed audit trails.",
      logo_icon: Shield
    },
    link_groups: [
      {
        title: "Citizen Services",
        links: [
          { label: "File a New Report", href: "/report" },
          { label: "Track Existing Report", href: "/track" },
          { label: "Whistleblower Protection", href: "/protection" },
          { label: "Evidence Guidelines", href: "/guidelines" }
        ]
      },
      {
        title: "Monitored Departments",
        links: [
          { label: "Public Works Department (PWD)", href: "/departments/pwd" },
          { label: "Revenue Department", href: "/departments/revenue" },
          { label: "Local Self Government (LSGD)", href: "/departments/lsgd" },
          { label: "Motor Vehicles Department (MVD)", href: "/departments/mvd" }
        ]
      },
      {
        title: "System Transparency",
        links: [
          { label: "AI Credibility Scoring", href: "/transparency/ai" },
          { label: "Blockchain Audit Logs", href: "/transparency/blockchain" },
          { label: "Open Data Portal", href: "/transparency/data" },
          { label: "Annual Impact Reports", href: "/transparency/reports" }
        ]
      }
    ],
    legal: "© 2024 Vigilance & Anti-Corruption Bureau, Kerala. All rights reserved. Secured by AES-256 Encryption and Immutable Ledger Technology."
  }
};

// ============================================================================
// MAIN PAGE COMPONENT
// ============================================================================

export default function Report() {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [activeFaq, setActiveFaq] = useState(null);

  const toggleFaq = (index) => {
    setActiveFaq(activeFaq === index ? null : index);
  };

  const getStatusVariant = (status) => {
    switch (status) {
      case 'Active': return 'primary';
      case 'Automated': return 'info';
      case 'Investigating': return 'warning';
      case 'High Risk': return 'danger';
      case 'Resolved': return 'success';
      default: return 'default';
    }
  };

  const faqs = [
    {
      question: "Is my identity truly anonymous?",
      answer: "Yes. We use Zero-Knowledge Proofs (ZKP) and IP masking. Your personal details are never stored in plain text, and even system administrators cannot link your submission to your identity."
    },
    {
      question: "What kind of evidence should I upload?",
      answer: "Clear audio recordings, video footage, scanned documents, or photographs of official requests. Ensure files are under 50MB. Our AI will automatically enhance and transcribe media files."
    },
    {
      question: "How do I track my complaint without an account?",
      answer: "Upon submission, you will receive a unique, cryptographically generated Tracking ID. Save this ID securely. You can use it on the 'Track Complaint' page to view real-time blockchain updates."
    },
    {
      question: "What happens if my evidence is deemed insufficient?",
      answer: "The AI engine will flag the report for manual review. An investigating officer may request additional details through our secure, anonymous two-way messaging portal using your Tracking ID."
    }
  ];

  return (
    <div className="min-h-screen bg-slate-950 text-slate-300 font-body selection:bg-emerald-500/30">
      
      {/* SECTION 1: NAVBAR (Wireframe Fidelity) */}
      <nav className="sticky top-0 z-50 w-full border-b border-slate-800 bg-slate-950/80 backdrop-blur-md">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-20">
            
            {/* Logo */}
            <div className="flex-shrink-0 flex items-center">
              <Link to={wireframeData.navbar.logo.href} className="flex items-center gap-3 group">
                <div className="bg-emerald-600 p-2.5 rounded-xl group-hover:bg-emerald-500 transition-colors shadow-lg shadow-emerald-900/20">
                  <wireframeData.navbar.logo.icon className="h-6 w-6 text-white" />
                </div>
                <span className="font-display font-bold text-2xl tracking-tight text-white">
                  {wireframeData.navbar.logo.text.split(' ')[0]} <span className="text-emerald-500">{wireframeData.navbar.logo.text.split(' ')[1]}</span>
                </span>
              </Link>
            </div>

            {/* Desktop Links */}
            <div className="hidden md:flex items-center space-x-8">
              {wireframeData.navbar.links.map((link, idx) => (
                <Link 
                  key={idx} 
                  to={link.href}
                  className="text-sm font-medium text-slate-300 hover:text-white transition-colors"
                >
                  {link.label}
                </Link>
              ))}
            </div>

            {/* CTA */}
            <div className="hidden md:flex items-center">
              <Link 
                to={wireframeData.navbar.cta.href}
                className="inline-flex items-center gap-2 bg-slate-800 hover:bg-slate-700 text-white px-5 py-2.5 rounded-lg text-sm font-medium transition-all border border-slate-700 hover:border-slate-600"
              >
                <wireframeData.navbar.cta.icon className="w-4 h-4 text-emerald-500" />
                {wireframeData.navbar.cta.label}
              </Link>
            </div>

            {/* Mobile menu button */}
            <div className="md:hidden flex items-center">
              <button 
                onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
                className="text-slate-300 hover:text-white p-2"
              >
                {isMobileMenuOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
              </button>
            </div>
          </div>
        </div>

        {/* Mobile Menu */}
        {isMobileMenuOpen && (
          <div className="md:hidden bg-slate-900 border-b border-slate-800 px-4 pt-2 pb-6 space-y-1">
            {wireframeData.navbar.links.map((link, idx) => (
              <Link 
                key={idx} 
                to={link.href}
                className="block px-3 py-3 text-base font-medium text-slate-300 hover:text-white hover:bg-slate-800 rounded-md"
              >
                {link.label}
              </Link>
            ))}
            <Link 
              to={wireframeData.navbar.cta.href}
              className="mt-4 flex items-center gap-2 bg-emerald-600 text-white px-4 py-3 rounded-md text-base font-medium"
            >
              <wireframeData.navbar.cta.icon className="w-5 h-5" />
              {wireframeData.navbar.cta.label}
            </Link>
          </div>
        )}
      </nav>

      {/* SECTION 2: HERO */}
      <section className="relative pt-20 pb-16 lg:pt-28 lg:pb-24 overflow-hidden">
        {/* Background Effects */}
        <div className="absolute inset-0 -z-10 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-emerald-900/20 via-slate-950 to-slate-950"></div>
        <div className="absolute top-0 right-0 -translate-y-12 translate-x-1/3 w-[800px] h-[800px] bg-emerald-500/5 rounded-full blur-3xl pointer-events-none"></div>
        
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10 text-center">
          <Badge variant="success" className="mb-6 px-4 py-1.5 text-sm border-emerald-500/30">
            <ShieldCheck className="w-4 h-4 mr-2" />
            100% Anonymous & Encrypted
          </Badge>
          
          <h1 className="text-4xl md:text-6xl font-display font-bold text-white tracking-tight mb-6 max-w-4xl mx-auto leading-tight">
            File a Secure Report.<br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-emerald-400 to-teal-500">
              Protect Public Integrity.
            </span>
          </h1>
          
          <p className="text-lg md:text-xl text-slate-400 max-w-2xl mx-auto mb-10 leading-relaxed">
            Submit your evidence with absolute confidence. Our AI-driven, blockchain-backed system ensures your identity remains protected while holding corrupt officials accountable.
          </p>

          <div className="flex flex-wrap justify-center gap-6 text-sm font-medium text-slate-400">
            <div className="flex items-center gap-2">
              <EyeOff className="w-5 h-5 text-emerald-500" />
              Zero-Knowledge Proofs
            </div>
            <div className="flex items-center gap-2">
              <FileKey className="w-5 h-5 text-emerald-500" />
              AES-256 Encryption
            </div>
            <div className="flex items-center gap-2">
              <Database className="w-5 h-5 text-emerald-500" />
              Immutable Ledger
            </div>
          </div>
        </div>
      </section>

      {/* SECTION 3: WORKFLOW STEPPER (Imported Component) */}
      <section className="py-12 bg-slate-900/50 border-y border-slate-800 relative z-20">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="bg-slate-950 rounded-2xl border border-slate-800 shadow-2xl shadow-black/50 p-6 md:p-10">
            <WorkflowStepper />
          </div>
        </div>
      </section>

      {/* SECTION 4: TIMELINE (Wireframe Fidelity) */}
      <section className="py-24 relative overflow-hidden">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-3xl mx-auto mb-16">
            <h2 className="text-3xl md:text-4xl font-display font-bold text-white mb-4">
              {wireframeData.timeline.title.split(':')[0]}:
              <span className="block text-emerald-400 text-2xl md:text-3xl mt-2">
                {wireframeData.timeline.title.split(':')[1]}
              </span>
            </h2>
            <p className="text-slate-400 text-lg">
              Understand exactly how your report is processed, verified, and acted upon without ever compromising your safety.
            </p>
          </div>

          <div className="max-w-4xl mx-auto relative">
            {/* Vertical Line */}
            <div className="absolute left-4 md:left-1/2 top-0 bottom-0 w-px bg-gradient-to-b from-emerald-500/50 via-slate-700 to-transparent transform md:-translate-x-1/2"></div>

            <div className="space-y-12">
              {wireframeData.timeline.items.map((item, index) => {
                const isEven = index % 2 === 0;
                return (
                  <div key={index} className={`relative flex flex-col md:flex-row items-start ${isEven ? 'md:flex-row-reverse' : ''}`}>
                    
                    {/* Timeline Dot */}
                    <div className="absolute left-4 md:left-1/2 w-8 h-8 rounded-full bg-slate-900 border-2 border-emerald-500 transform -translate-x-1/2 flex items-center justify-center z-10 shadow-[0_0_15px_rgba(16,185,129,0.3)]">
                      <div className="w-2.5 h-2.5 rounded-full bg-emerald-400"></div>
                    </div>

                    {/* Content Card */}
                    <div className={`ml-12 md:ml-0 md:w-1/2 ${isEven ? 'md:pl-12' : 'md:pr-12'}`}>
                      <Card className="p-6 hover:border-emerald-500/30 transition-colors group">
                        <div className="flex items-center justify-between mb-3">
                          <span className="text-sm font-bold text-emerald-500 tracking-wider uppercase">
                            {item.date}
                          </span>
                          <Badge variant={getStatusVariant(item.status)}>
                            {item.status}
                          </Badge>
                        </div>
                        <h3 className="text-xl font-display font-semibold text-white mb-3 group-hover:text-emerald-400 transition-colors">
                          {item.title}
                        </h3>
                        <p className="text-slate-400 leading-relaxed">
                          {item.body}
                        </p>
                      </Card>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </section>

      {/* SECTION 5: SECURITY FEATURES */}
      <section className="py-20 bg-slate-900 border-y border-slate-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid md:grid-cols-3 gap-8">
            <div className="p-6 rounded-2xl bg-slate-950 border border-slate-800">
              <div className="w-12 h-12 rounded-lg bg-emerald-500/10 flex items-center justify-center mb-6">
                <Fingerprint className="w-6 h-6 text-emerald-400" />
              </div>
              <h3 className="text-xl font-display font-semibold text-white mb-3">Identity Masking</h3>
              <p className="text-slate-400">Your IP address and device metadata are stripped immediately upon connection. We do not log access records.</p>
            </div>
            <div className="p-6 rounded-2xl bg-slate-950 border border-slate-800">
              <div className="w-12 h-12 rounded-lg bg-blue-500/10 flex items-center justify-center mb-6">
                <BrainCircuit className="w-6 h-6 text-blue-400" />
              </div>
              <h3 className="text-xl font-display font-semibold text-white mb-3">AI Redaction</h3>
              <p className="text-slate-400">Our AI automatically scans uploaded documents and audio to redact names, voices, or details that could identify you.</p>
            </div>
            <div className="p-6 rounded-2xl bg-slate-950 border border-slate-800">
              <div className="w-12 h-12 rounded-lg bg-amber-500/10 flex items-center justify-center mb-6">
                <Database className="w-6 h-6 text-amber-400" />
              </div>
              <h3 className="text-xl font-display font-semibold text-white mb-3">Immutable Evidence</h3>
              <p className="text-slate-400">Once submitted, evidence is hashed and stored on a blockchain ledger, ensuring it can never be altered or deleted by corrupt actors.</p>
            </div>
          </div>
        </div>
      </section>

      {/* SECTION 6: MONITORED DEPARTMENTS (Using mockData) */}
      <section className="py-24">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col md:flex-row md:items-end justify-between mb-12 gap-6">
            <div className="max-w-2xl">
              <h2 className="text-3xl font-display font-bold text-white mb-4">Monitored Departments</h2>
              <p className="text-slate-400">
                Our system actively routes complaints to specialized nodal officers within these key government sectors.
              </p>
            </div>
            <Link to="/explore" className="inline-flex items-center text-emerald-400 hover:text-emerald-300 font-medium transition-colors">
              View Public Directory <ArrowRight className="ml-2 w-4 h-4" />
            </Link>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
            {categories.map((dept) => (
              <div 
                key={dept.id} 
                className="p-4 rounded-xl bg-slate-900 border border-slate-800 hover:border-slate-700 transition-all group cursor-default"
              >
                <div 
                  className="w-10 h-10 rounded-lg flex items-center justify-center mb-4 opacity-80 group-hover:opacity-100 transition-opacity"
                  style={{ backgroundColor: `${dept.color}20`, color: dept.color }}
                >
                  <Building2 className="w-5 h-5" />
                </div>
                <h4 className="text-sm font-medium text-slate-200 group-hover:text-white transition-colors line-clamp-2">
                  {dept.name}
                </h4>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* SECTION 7: FAQ / GUIDELINES */}
      <section className="py-20 bg-slate-900/50 border-t border-slate-800">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-display font-bold text-white mb-4">Reporting Guidelines & FAQ</h2>
            <p className="text-slate-400">Everything you need to know before submitting your evidence.</p>
          </div>

          <div className="space-y-4">
            {faqs.map((faq, index) => (
              <div 
                key={index} 
                className="bg-slate-950 border border-slate-800 rounded-xl overflow-hidden transition-all duration-200"
              >
                <button
                  onClick={() => toggleFaq(index)}
                  className="w-full px-6 py-4 flex items-center justify-between text-left focus:outline-none"
                >
                  <span className="font-medium text-slate-200">{faq.question}</span>
                  {activeFaq === index ? (
                    <ChevronUp className="w-5 h-5 text-emerald-500 flex-shrink-0" />
                  ) : (
                    <ChevronDown className="w-5 h-5 text-slate-500 flex-shrink-0" />
                  )}
                </button>
                
                <div 
                  className={`px-6 overflow-hidden transition-all duration-300 ease-in-out ${
                    activeFaq === index ? 'max-h-48 pb-5 opacity-100' : 'max-h-0 opacity-0'
                  }`}
                >
                  <p className="text-slate-400 text-sm leading-relaxed">
                    {faq.answer}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* SECTION 8: FOOTER (Wireframe Fidelity) */}
      <footer className="bg-slate-950 border-t border-slate-800 pt-16 pb-8">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-12 mb-16">
            
            {/* Brand Column */}
            <div className="lg:col-span-2">
              <Link to="/" className="flex items-center gap-2 mb-6">
                <div className="bg-emerald-600 p-2 rounded-lg">
                  <wireframeData.footer.brand.logo_icon className="h-5 w-5 text-white" />
                </div>
                <span className="font-display font-bold text-xl tracking-tight text-white">
                  {wireframeData.footer.brand.name}
                </span>
              </Link>
              <p className="text-slate-400 text-sm leading-relaxed max-w-sm">
                {wireframeData.footer.brand.description}
              </p>
            </div>

            {/* Link Groups */}
            {wireframeData.footer.link_groups.map((group, idx) => (
              <div key={idx}>
                <h4 className="text-white font-semibold mb-6">{group.title}</h4>
                <ul className="space-y-4">
                  {group.links.map((link, linkIdx) => (
                    <li key={linkIdx}>
                      <Link 
                        to={link.href}
                        className="text-slate-400 hover:text-emerald-400 text-sm transition-colors"
                      >
                        {link.label}
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>

          {/* Legal */}
          <div className="pt-8 border-t border-slate-800 flex flex-col md:flex-row items-center justify-between gap-4">
            <p className="text-slate-500 text-sm text-center md:text-left">
              {wireframeData.footer.legal}
            </p>
            <div className="flex items-center gap-4 text-slate-500">
              <ShieldCheck className="w-5 h-5" />
              <Lock className="w-5 h-5" />
              <Database className="w-5 h-5" />
            </div>
          </div>
        </div>
      </footer>

    </div>
  );
}
