import React, { useMemo, useState } from 'react';
import { 
  Shield, 
  Activity, 
  Database, 
  Eye, 
  Lock, 
  Cpu, 
  Network, 
  ChevronDown, 
  ChevronUp, 
  ArrowRight, 
  CheckCircle2, 
  FileText, 
  Search, 
  Server, 
  Users, 
  Zap,
  Fingerprint,
  Scale
} from 'lucide-react';
import AppShell from '../components/AppShell';
import { dashboardMetrics } from '../mockData';

// ============================================================================
// INLINE UI PRIMITIVES
// ============================================================================

const Button = React.forwardRef(({ className = '', variant = "default", size = "default", children, ...props }, ref) => {
  const variants = {
    default: "bg-[#059669] text-white hover:bg-[#047857] shadow-sm",
    outline: "border-2 border-[#059669] text-[#059669] hover:bg-[#059669] hover:text-white",
    ghost: "hover:bg-slate-100 text-slate-700",
    dark: "bg-slate-900 text-white hover:bg-slate-800",
  };
  const sizes = {
    default: "h-11 px-6 py-2",
    sm: "h-9 rounded-md px-4 text-sm",
    lg: "h-14 rounded-lg px-8 text-lg",
  };
  
  return (
    <button 
      ref={ref} 
      className={`inline-flex items-center justify-center rounded-lg font-medium transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-[#059669] focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed ${variants[variant]} ${sizes[size]} ${className}`} 
      {...props}
    >
      {children}
    </button>
  );
});
Button.displayName = "Button";

const Card = ({ className = '', children, ...props }) => (
  <div 
    className={`rounded-2xl border border-slate-200 bg-white shadow-sm overflow-hidden ${className}`} 
    {...props}
  >
    {children}
  </div>
);

const Badge = ({ className = '', variant = "default", children }) => {
  const variants = {
    default: "bg-emerald-100 text-emerald-800 border-emerald-200",
    dark: "bg-slate-800 text-slate-300 border-slate-700",
    outline: "bg-transparent border-slate-300 text-slate-600",
  };
  return (
    <span className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold border ${variants[variant]} ${className}`}>
      {children}
    </span>
  );
};

// ============================================================================
// PAGE COMPONENT
// ============================================================================

export default function AboutC3MS() {
  // State for interactive sections
  const [activeTab, setActiveTab] = useState('citizen');
  const [openFaq, setOpenFaq] = useState('faq-1');

  // Data for Architecture Tabs
  const architectureTabs = [
    {
      id: 'citizen',
      label: 'Citizen Portal',
      icon: Users,
      title: 'Secure & Anonymous Reporting',
      description: 'The frontline of C3MS allows citizens to report corruption via web, mobile, or an AI-powered WhatsApp bot. Identity is protected using zero-knowledge proofs, ensuring whistleblowers remain completely anonymous while still receiving case updates.',
      features: ['Zero-Knowledge Authentication', 'Multi-lingual NLP Bot', 'Secure Media Upload', 'Real-time Status Tracking']
    },
    {
      id: 'ai',
      label: 'AI Triage Engine',
      icon: Cpu,
      title: 'Predictive Risk Scoring',
      description: 'Every incoming report is analyzed by our proprietary AI engine. It cross-references historical data, identifies patterns of organized syndicates, and assigns a credibility score to prioritize high-risk cases automatically.',
      features: ['Natural Language Processing', 'Anomaly Detection', 'Automated Risk Scoring', 'Syndicate Pattern Matching']
    },
    {
      id: 'blockchain',
      label: 'Blockchain Vault',
      icon: Database,
      title: 'Immutable Evidence Ledger',
      description: 'To prevent tampering, all submitted evidence (audio, video, documents) is cryptographically hashed and stored on a private blockchain ledger. This establishes an unbreakable chain of custody admissible in court.',
      features: ['SHA-256 Hashing', 'Distributed Ledger', 'Tamper-proof Audit Trails', 'Cryptographic Verification']
    },
    {
      id: 'investigator',
      label: 'Investigator Hub',
      icon: Shield,
      title: 'Actionable Intelligence',
      description: 'VACB officers access a secure dashboard providing a unified view of cases, AI insights, and evidence. The system automates routine paperwork, allowing investigators to focus on field operations and rapid resolution.',
      features: ['Unified Case Management', 'Automated Reporting', 'Secure Inter-departmental Comms', 'Resource Allocation AI']
    }
  ];

  // Data for FAQs
  const faqs = [
    {
      id: 'faq-1',
      question: 'How does C3MS guarantee my anonymity?',
      answer: 'C3MS uses Zero-Knowledge Proofs (ZKP) for authentication. This means the system verifies you are a unique, valid user without ever knowing or storing your actual identity, phone number, or IP address. Even database administrators cannot link a complaint to a specific person.'
    },
    {
      id: 'faq-2',
      question: 'What happens after I submit a complaint?',
      answer: 'Your complaint is immediately encrypted and hashed on the blockchain. Our AI engine analyzes it for credibility and urgency. It is then routed to the appropriate VACB investigating officer. You can track the progress using the unique, anonymous tracking ID provided at submission.'
    },
    {
      id: 'faq-3',
      question: 'Can evidence be deleted by corrupt officials?',
      answer: 'No. Once evidence is uploaded, its cryptographic hash is permanently recorded on a distributed blockchain ledger. If a file is altered or deleted, the hash will no longer match, instantly flagging the tampering attempt to the Director General.'
    },
    {
      id: 'faq-4',
      question: 'Is the AI making final legal decisions?',
      answer: 'Absolutely not. The AI acts as a triage and intelligence tool. It highlights patterns, flags high-risk anomalies, and prioritizes cases. All investigative actions, legal decisions, and conclusions are made by trained human officers.'
    },
    {
      id: 'faq-5',
      question: 'How is the public data on the Explore page filtered?',
      answer: 'The public Explore page shows aggregated, anonymized data. Specific names, exact locations, and sensitive case details are redacted automatically by our NLP engine before being published to the public transparency dashboard.'
    }
  ];

  // Filter metrics for the stats section
  const displayMetrics = useMemo(() => {
    return dashboardMetrics.filter(m => 
      ['Total Complaints', 'Resolved Cases', 'Funds Recovered', 'System Uptime'].includes(m.label)
    );
  }, []);

  return (
    <AppShell>
      <div className="min-h-screen bg-slate-50 font-body">
        
        {/* =========================================
            SECTION 1: HERO
        ========================================= */}
        <section className="relative isolate overflow-hidden bg-slate-950 pt-24 pb-32 sm:pt-32 sm:pb-40 border-b border-slate-800">
          {/* Background Effects */}
          <div className="absolute inset-0 -z-10 bg-[linear-gradient(to_right,#4f4f4f2e_1px,transparent_1px),linear-gradient(to_bottom,#4f4f4f2e_1px,transparent_1px)] bg-[size:24px_24px] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_0%,#000_70%,transparent_100%)]"></div>
          <div className="absolute left-1/2 top-0 -z-10 -translate-x-1/2 blur-3xl xl:-top-6" aria-hidden="true">
            <div className="aspect-[1155/678] w-[72.1875rem] bg-gradient-to-tr from-[#059669] to-[#0f172a] opacity-30" style={{ clipPath: 'polygon(74.1% 44.1%, 100% 61.6%, 97.5% 26.9%, 85.5% 0.1%, 80.7% 2%, 72.5% 32.5%, 60.2% 62.4%, 52.4% 68.1%, 47.5% 58.3%, 45.2% 34.5%, 27.5% 76.7%, 0.1% 64.9%, 17.9% 100%, 27.6% 76.8%, 76.1% 97.7%, 74.1% 44.1%)' }} />
          </div>

          <div className="mx-auto max-w-7xl px-6 lg:px-8 relative z-10 text-center">
            <Badge variant="dark" className="mb-8 border-emerald-500/30 text-emerald-400">
              <Shield className="w-4 h-4 mr-2" />
              Vigilance & Anti-Corruption Bureau, Kerala
            </Badge>
            <h1 className="mx-auto max-w-4xl font-display text-5xl font-bold tracking-tight text-white sm:text-7xl">
              Empowering Kerala with <span className="text-transparent bg-clip-text bg-gradient-to-r from-emerald-400 to-cyan-400">AI-Driven Transparency</span>
            </h1>
            <p className="mx-auto mt-6 max-w-2xl text-lg leading-8 text-slate-300">
              The Comprehensive Corruption Control & Management System (C3MS) is a next-generation platform designed to protect whistleblowers, accelerate investigations, and restore public trust through immutable technology.
            </p>
            <div className="mt-10 flex items-center justify-center gap-x-6">
              <Button size="lg" onClick={() => window.scrollTo({ top: document.getElementById('architecture').offsetTop, behavior: 'smooth' })}>
                Explore the Architecture
              </Button>
              <a href="/report" className="text-sm font-semibold leading-6 text-white hover:text-emerald-400 transition-colors flex items-center gap-2">
                Report an Incident <ArrowRight className="w-4 h-4" />
              </a>
            </div>
          </div>
        </section>

        {/* =========================================
            SECTION 2: MISSION & VISION
        ========================================= */}
        <section className="py-24 sm:py-32 bg-white">
          <div className="mx-auto max-w-7xl px-6 lg:px-8">
            <div className="mx-auto grid max-w-2xl grid-cols-1 gap-x-16 gap-y-16 sm:gap-y-20 lg:mx-0 lg:max-w-none lg:grid-cols-2 items-center">
              <div>
                <h2 className="text-base font-semibold leading-7 text-emerald-600">Our Mission</h2>
                <p className="mt-2 font-display text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl">
                  Zero Tolerance. Zero Compromise.
                </p>
                <p className="mt-6 text-lg leading-8 text-slate-600">
                  For decades, the fear of retaliation and bureaucratic red tape have silenced citizens. C3MS was built to dismantle these barriers. By combining military-grade encryption with predictive artificial intelligence, we are shifting from reactive policing to proactive vigilance.
                </p>
                <dl className="mt-10 max-w-xl space-y-8 text-base leading-7 text-slate-600 lg:max-w-none">
                  <div className="relative pl-12">
                    <dt className="inline font-semibold text-slate-900">
                      <Lock className="absolute left-1 top-1 h-6 w-6 text-emerald-600" />
                      Protect the Vulnerable.
                    </dt>{' '}
                    <dd className="inline">Ensuring absolute anonymity for whistleblowers so anyone can report corruption without fear.</dd>
                  </div>
                  <div className="relative pl-12">
                    <dt className="inline font-semibold text-slate-900">
                      <Zap className="absolute left-1 top-1 h-6 w-6 text-emerald-600" />
                      Accelerate Justice.
                    </dt>{' '}
                    <dd className="inline">Reducing case resolution time from years to months through AI-assisted evidence processing.</dd>
                  </div>
                  <div className="relative pl-12">
                    <dt className="inline font-semibold text-slate-900">
                      <Eye className="absolute left-1 top-1 h-6 w-6 text-emerald-600" />
                      Ensure Transparency.
                    </dt>{' '}
                    <dd className="inline">Providing the public with real-time, anonymized data on anti-corruption efforts across the state.</dd>
                  </div>
                </dl>
              </div>
              <div className="relative">
                <div className="absolute -inset-4 rounded-xl bg-slate-100/50 -z-10 transform rotate-3"></div>
                <img
                  src="https://images.unsplash.com/photo-1589829085413-56de8ae18c73?auto=format&fit=crop&q=80&w=1200"
                  alt="Scales of Justice"
                  className="w-[48rem] max-w-none rounded-2xl shadow-xl ring-1 ring-slate-400/10 sm:w-[57rem] md:-ml-4 lg:-ml-0 object-cover h-[600px]"
                />
              </div>
            </div>
          </div>
        </section>

        {/* =========================================
            SECTION 3: CORE PILLARS (GRID)
        ========================================= */}
        <section className="py-24 sm:py-32 bg-slate-50">
          <div className="mx-auto max-w-7xl px-6 lg:px-8">
            <div className="mx-auto max-w-2xl text-center">
              <h2 className="text-base font-semibold leading-7 text-emerald-600">Technology Stack</h2>
              <p className="mt-2 font-display text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl">
                The Four Pillars of C3MS
              </p>
              <p className="mt-6 text-lg leading-8 text-slate-600">
                A robust architecture designed to eliminate human interference and guarantee data integrity from submission to conviction.
              </p>
            </div>
            <div className="mx-auto mt-16 max-w-2xl sm:mt-20 lg:mt-24 lg:max-w-none">
              <dl className="grid max-w-xl grid-cols-1 gap-x-8 gap-y-16 lg:max-w-none lg:grid-cols-4">
                {[
                  {
                    name: 'Zero-Knowledge Anonymity',
                    description: 'Cryptographic protocols ensure that even system administrators cannot link a complaint to the citizen who filed it.',
                    icon: Fingerprint,
                  },
                  {
                    name: 'Predictive AI Engine',
                    description: 'Machine learning models analyze text and metadata to detect organized syndicates and prioritize high-risk cases.',
                    icon: Activity,
                  },
                  {
                    name: 'Immutable Ledger',
                    description: 'All evidence is hashed on a private blockchain, creating a tamper-proof chain of custody admissible in court.',
                    icon: Network,
                  },
                  {
                    name: 'Real-time Transparency',
                    description: 'Public dashboards provide live metrics on department performance and case resolutions, fostering public trust.',
                    icon: Eye,
                  },
                ].map((feature) => (
                  <Card key={feature.name} className="flex flex-col p-8 hover:-translate-y-1 transition-transform duration-300 border-slate-200/60 shadow-sm hover:shadow-md">
                    <dt className="flex items-center gap-x-3 text-lg font-semibold leading-7 text-slate-900 font-display">
                      <div className="h-12 w-12 flex items-center justify-center rounded-xl bg-emerald-100 text-emerald-600 mb-4">
                        <feature.icon className="h-6 w-6" aria-hidden="true" />
                      </div>
                    </dt>
                    <dd className="mt-1 flex flex-auto flex-col text-base leading-7 text-slate-600">
                      <h3 className="font-semibold text-slate-900 mb-2">{feature.name}</h3>
                      <p className="flex-auto">{feature.description}</p>
                    </dd>
                  </Card>
                ))}
              </dl>
            </div>
          </div>
        </section>

        {/* =========================================
            SECTION 4: SYSTEM ARCHITECTURE (TABS)
        ========================================= */}
        <section id="architecture" className="py-24 sm:py-32 bg-slate-900 text-white">
          <div className="mx-auto max-w-7xl px-6 lg:px-8">
            <div className="mx-auto max-w-2xl text-center mb-16">
              <h2 className="text-base font-semibold leading-7 text-emerald-400">How It Works</h2>
              <p className="mt-2 font-display text-3xl font-bold tracking-tight text-white sm:text-4xl">
                End-to-End System Architecture
              </p>
            </div>

            <div className="flex flex-col lg:flex-row gap-12">
              {/* Tabs Navigation */}
              <div className="lg:w-1/3 flex flex-col gap-2">
                {architectureTabs.map((tab) => {
                  const isActive = activeTab === tab.id;
                  const Icon = tab.icon;
                  return (
                    <button
                      key={tab.id}
                      onClick={() => setActiveTab(tab.id)}
                      className={`flex items-center gap-4 p-4 rounded-xl text-left transition-all duration-200 ${
                        isActive 
                          ? 'bg-emerald-500/10 border border-emerald-500/30 text-white' 
                          : 'bg-transparent border border-transparent text-slate-400 hover:bg-slate-800 hover:text-slate-200'
                      }`}
                    >
                      <div className={`p-2 rounded-lg ${isActive ? 'bg-emerald-500 text-white' : 'bg-slate-800 text-slate-400'}`}>
                        <Icon className="w-5 h-5" />
                      </div>
                      <span className="font-semibold font-display text-lg">{tab.label}</span>
                    </button>
                  );
                })}
              </div>

              {/* Tab Content */}
              <div className="lg:w-2/3">
                {architectureTabs.map((tab) => {
                  if (activeTab !== tab.id) return null;
                  return (
                    <div key={tab.id} className="bg-slate-800/50 border border-slate-700 rounded-2xl p-8 animate-in fade-in slide-in-from-right-4 duration-500">
                      <div className="flex items-center gap-4 mb-6">
                        <div className="p-3 rounded-xl bg-emerald-500/20 text-emerald-400">
                          <tab.icon className="w-8 h-8" />
                        </div>
                        <h3 className="text-3xl font-bold font-display">{tab.title}</h3>
                      </div>
                      <p className="text-lg text-slate-300 leading-relaxed mb-8">
                        {tab.description}
                      </p>
                      
                      <h4 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-4">Key Capabilities</h4>
                      <ul className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        {tab.features.map((feature, idx) => (
                          <li key={idx} className="flex items-center gap-3 text-slate-200 bg-slate-800/80 p-3 rounded-lg border border-slate-700/50">
                            <CheckCircle2 className="w-5 h-5 text-emerald-400 flex-shrink-0" />
                            <span>{feature}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </section>

        {/* =========================================
            SECTION 5: IMPACT METRICS
        ========================================= */}
        <section className="py-24 sm:py-32 bg-white border-b border-slate-200">
          <div className="mx-auto max-w-7xl px-6 lg:px-8">
            <div className="mx-auto max-w-2xl lg:max-w-none">
              <div className="text-center mb-16">
                <h2 className="text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl font-display">
                  Measurable Impact
                </h2>
                <p className="mt-4 text-lg leading-8 text-slate-600">
                  Since the deployment of C3MS, the VACB has seen unprecedented improvements in reporting rates and case resolution speeds.
                </p>
              </div>
              <dl className="grid grid-cols-1 gap-0.5 overflow-hidden rounded-2xl text-center sm:grid-cols-2 lg:grid-cols-4 border border-slate-200 bg-slate-200">
                {displayMetrics.map((stat) => (
                  <div key={stat.id} className="flex flex-col bg-white p-8">
                    <dt className="text-sm font-semibold leading-6 text-slate-600">{stat.label}</dt>
                    <dd className="order-first text-3xl font-semibold tracking-tight text-slate-900 font-display mb-2">{stat.value}</dd>
                    <dd className="text-xs font-medium text-emerald-600 bg-emerald-50 inline-block px-2 py-1 rounded-full mx-auto mt-2">
                      {stat.trend} {stat.detail}
                    </dd>
                  </div>
                ))}
              </dl>
            </div>
          </div>
        </section>

        {/* =========================================
            SECTION 6: FAQ / TRANSPARENCY
        ========================================= */}
        <section className="py-24 sm:py-32 bg-slate-50">
          <div className="mx-auto max-w-7xl px-6 lg:px-8">
            <div className="mx-auto max-w-4xl divide-y divide-slate-900/10">
              <h2 className="text-2xl font-bold leading-10 tracking-tight text-slate-900 font-display mb-8">
                Frequently Asked Questions
              </h2>
              <dl className="mt-10 space-y-6 divide-y divide-slate-900/10">
                {faqs.map((faq) => (
                  <div key={faq.id} className="pt-6">
                    <dt>
                      <button
                        onClick={() => setOpenFaq(openFaq === faq.id ? null : faq.id)}
                        className="flex w-full items-start justify-between text-left text-slate-900 focus:outline-none group"
                      >
                        <span className="text-base font-semibold leading-7 group-hover:text-emerald-600 transition-colors">
                          {faq.question}
                        </span>
                        <span className="ml-6 flex h-7 items-center">
                          {openFaq === faq.id ? (
                            <ChevronUp className="h-5 w-5 text-emerald-600" aria-hidden="true" />
                          ) : (
                            <ChevronDown className="h-5 w-5 text-slate-400 group-hover:text-emerald-600" aria-hidden="true" />
                          )}
                        </span>
                      </button>
                    </dt>
                    {openFaq === faq.id && (
                      <dd className="mt-4 pr-12 animate-in fade-in slide-in-from-top-2 duration-200">
                        <p className="text-base leading-7 text-slate-600">{faq.answer}</p>
                      </dd>
                    )}
                  </div>
                ))}
              </dl>
            </div>
          </div>
        </section>

        {/* =========================================
            SECTION 7: CTA
        ========================================= */}
        <section className="relative isolate overflow-hidden bg-emerald-900 py-16 sm:py-24 lg:py-32">
          <div className="absolute inset-0 -z-10 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-emerald-800 via-emerald-900 to-slate-950 opacity-80"></div>
          <div className="mx-auto max-w-7xl px-6 lg:px-8 text-center">
            <h2 className="text-3xl font-bold tracking-tight text-white sm:text-4xl font-display">
              Ready to make a difference?
            </h2>
            <p className="mx-auto mt-6 max-w-xl text-lg leading-8 text-emerald-100">
              Your voice is the strongest weapon against corruption. Report incidents securely, anonymously, and track the impact of your actions.
            </p>
            <div className="mt-10 flex items-center justify-center gap-x-6">
              <Button size="lg" className="bg-white text-emerald-900 hover:bg-slate-100">
                File a Secure Report
              </Button>
              <Button size="lg" variant="outline" className="border-emerald-400 text-emerald-100 hover:bg-emerald-800 hover:text-white">
                View Public Data
              </Button>
            </div>
          </div>
        </section>

      </div>
    </AppShell>
  );
}
