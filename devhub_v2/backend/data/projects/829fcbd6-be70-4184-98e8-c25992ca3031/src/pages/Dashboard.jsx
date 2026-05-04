import { useState } from 'react'
import { complaints, aiAlerts, metrics } from '../mockData'
import DashboardSidebar from '../components/layout/DashboardSidebar'
import KPICards from '../components/dashboard/KPICards'
import AIPredictiveAlerts from '../components/dashboard/AIPredictiveAlerts'
import AssignedCasesTable from '../components/dashboard/AssignedCasesTable'
import { 
  Bell, 
  Search, 
  User, 
  ShieldCheck, 
  ArrowRight, 
  Activity, 
  Database, 
  AlertTriangle, 
  CheckCircle, 
  Clock, 
  MapPin, 
  FileText, 
  Zap, 
  ChevronRight, 
  Filter, 
  Download,
  Menu,
  X
} from 'lucide-react'

// --- Inline Mock Data for Custom Sections ---
// Ensures the page is fully populated even if external mockData is sparse
const departmentRisks = [
  { id: 'dept-1', name: 'Public Works (PWD)', score: 92, trend: '+5%', level: 'Critical', cases: 142 },
  { id: 'dept-2', name: 'Revenue Department', score: 78, trend: '+2%', level: 'High', cases: 315 },
  { id: 'dept-3', name: 'Motor Vehicles (MVD)', score: 65, trend: '-4%', level: 'Medium', cases: 198 },
  { id: 'dept-4', name: 'Local Self Govt (LSGD)', score: 42, trend: '-12%', level: 'Low', cases: 284 },
  { id: 'dept-5', name: 'Health Services', score: 38, trend: '0%', level: 'Low', cases: 156 },
];

const recentAudits = [
  { id: 'tx-9921', action: 'Evidence Hash Verified', actor: 'System AI', time: '10 mins ago', status: 'success', hash: '0x8f2a...9c11' },
  { id: 'tx-9920', action: 'Case Status Updated', actor: 'Dr. Rajesh Kumar', time: '45 mins ago', status: 'success', hash: '0x3a1b...7d22' },
  { id: 'tx-9919', action: 'Anonymous Report Encrypted', actor: 'Citizen #8842', time: '2 hours ago', status: 'success', hash: '0x1c4d...5e99' },
  { id: 'tx-9918', action: 'AI Risk Assessment Logged', actor: 'Predictive Engine', time: '3 hours ago', status: 'warning', hash: '0x9b2f...1a44' },
  { id: 'tx-9917', action: 'Investigation Assigned', actor: 'Director General', time: '5 hours ago', status: 'success', hash: '0x7e5c...2b88' },
];

export default function Dashboard() {
  const [activeTab, setActiveTab] = useState('Overview');
  const [searchQuery, setSearchQuery] = useState('');
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  // Wireframe Data
  const wireframeData = {
    navbar: {
      logo: { text: "Vigilance C3MS", icon: ShieldCheck },
      links: [
        { label: "Active Investigations", href: "/dashboard/cases" },
        { label: "AI Risk Radar", href: "/dashboard/risk-radar" },
        { label: "Department Analytics", href: "/dashboard/departments" },
        { label: "Blockchain Audit Logs", href: "/dashboard/audit" }
      ],
      cta: { label: "Generate Intelligence Report", href: "/dashboard/reports/new" }
    },
    hero: {
      headline: "Investigator Command Center: AI-Powered Transparency for a Better Tomorrow",
      sub: "Monitor real-time corruption reports, analyze predictive risk alerts across Kerala departments, and manage active investigations with blockchain-verified audit trails.",
      cta_primary: { label: "Review High-Risk Alerts", href: "/dashboard/alerts/critical" },
      cta_secondary: { label: "View Department Metrics", href: "/dashboard/departments/overview" },
      image: {
        src: "https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=800&q=80",
        alt: "Secure data analytics dashboard displaying real-time governance metrics and AI credibility scores"
      }
    }
  };

  return (
    <div className="flex h-screen bg-[#0F172A] text-slate-300 font-body overflow-hidden selection:bg-emerald-500/30">
      
      {/* Section 1: Sidebar (Imported Layout Component) */}
      <div className="hidden md:block z-40">
        <DashboardSidebar />
      </div>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col h-screen overflow-y-auto custom-scrollbar relative">
        
        {/* Section 2: Dashboard Header (Navbar from Wireframe) */}
        <header className="sticky top-0 z-30 bg-[#0F172A]/90 backdrop-blur-xl border-b border-slate-800 px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between shadow-sm">
          <div className="flex items-center gap-4 md:hidden">
            <button 
              onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
              className="p-2 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition-colors"
            >
              {isMobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
            </button>
            <div className="flex items-center gap-2 text-white">
              <wireframeData.navbar.logo.icon className="w-6 h-6 text-emerald-500" />
              <span className="font-display font-bold text-lg tracking-tight">
                {wireframeData.navbar.logo.text}
              </span>
            </div>
          </div>

          <div className="hidden md:flex items-center gap-8">
            <nav className="flex items-center gap-6">
              {wireframeData.navbar.links.map((link, idx) => (
                <a 
                  key={idx} 
                  href={link.href}
                  className="text-sm font-medium text-slate-400 hover:text-emerald-400 transition-colors"
                >
                  {link.label}
                </a>
              ))}
            </nav>
          </div>

          <div className="flex items-center gap-4">
            <div className="hidden lg:flex relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
              <input 
                type="text" 
                placeholder="Search cases, alerts..." 
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="bg-slate-900 border border-slate-700 text-sm rounded-full pl-10 pr-4 py-2 text-white placeholder:text-slate-500 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 transition-all w-64"
              />
            </div>
            <button className="relative p-2 text-slate-400 hover:text-white hover:bg-slate-800 rounded-full transition-colors">
              <Bell className="w-5 h-5" />
              <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-rose-500 rounded-full border-2 border-[#0F172A]"></span>
            </button>
            <button className="hidden sm:flex items-center gap-2 bg-emerald-600 hover:bg-emerald-500 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors shadow-lg shadow-emerald-900/20">
              <FileText className="w-4 h-4" />
              {wireframeData.navbar.cta.label}
            </button>
            <div className="w-9 h-9 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center overflow-hidden cursor-pointer hover:border-emerald-500 transition-colors">
              <User className="w-5 h-5 text-slate-400" />
            </div>
          </div>
        </header>

        {/* Mobile Menu Dropdown */}
        {isMobileMenuOpen && (
          <div className="md:hidden absolute top-[73px] left-0 right-0 bg-slate-900 border-b border-slate-800 z-40 px-4 py-4 shadow-xl">
            <nav className="flex flex-col gap-4">
              {wireframeData.navbar.links.map((link, idx) => (
                <a 
                  key={idx} 
                  href={link.href}
                  className="text-sm font-medium text-slate-300 hover:text-emerald-400 transition-colors"
                >
                  {link.label}
                </a>
              ))}
              <button className="flex items-center justify-center gap-2 bg-emerald-600 hover:bg-emerald-500 text-white px-4 py-2.5 rounded-lg text-sm font-medium transition-colors mt-2">
                <FileText className="w-4 h-4" />
                {wireframeData.navbar.cta.label}
              </button>
            </nav>
          </div>
        )}

        <div className="p-4 sm:p-6 lg:p-8 max-w-[1600px] mx-auto w-full space-y-8">
          
          {/* Section 3: Hero / Welcome Banner (From Wireframe) */}
          <section className="relative overflow-hidden rounded-2xl bg-slate-900 border border-slate-800 shadow-2xl group">
            <div className="absolute inset-0 z-0">
              <img 
                src={wireframeData.hero.image.src} 
                alt={wireframeData.hero.image.alt}
                className="w-full h-full object-cover opacity-20 mix-blend-luminosity group-hover:opacity-30 transition-opacity duration-700"
              />
              <div className="absolute inset-0 bg-gradient-to-r from-slate-950 via-slate-900/90 to-transparent"></div>
              {/* Decorative Grid */}
              <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAiIGhlaWdodD0iMjAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PGNpcmNsZSBjeD0iMSIgY3k9IjEiIHI9IjEiIGZpbGw9InJnYmEoMjU1LDI1NSwyNTUsMC4wNSkiLz48L3N2Zz4=')] [mask-image:linear-gradient(to_bottom_right,white,transparent)]"></div>
            </div>
            
            <div className="relative z-10 p-8 sm:p-10 lg:p-12 max-w-4xl">
              <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-semibold uppercase tracking-wider mb-6">
                <Zap className="w-3.5 h-3.5" />
                System Status: Optimal
              </div>
              <h1 className="text-3xl sm:text-4xl lg:text-5xl font-display font-bold text-white leading-tight mb-4 tracking-tight">
                {wireframeData.hero.headline}
              </h1>
              <p className="text-lg text-slate-400 font-body leading-relaxed mb-8 max-w-2xl">
                {wireframeData.hero.sub}
              </p>
              <div className="flex flex-wrap items-center gap-4">
                <a 
                  href={wireframeData.hero.cta_primary.href}
                  className="inline-flex items-center gap-2 bg-emerald-600 hover:bg-emerald-500 text-white px-6 py-3 rounded-xl font-medium transition-all shadow-lg shadow-emerald-900/30 hover:shadow-emerald-900/50 hover:-translate-y-0.5"
                >
                  <AlertTriangle className="w-5 h-5" />
                  {wireframeData.hero.cta_primary.label}
                </a>
                <a 
                  href={wireframeData.hero.cta_secondary.href}
                  className="inline-flex items-center gap-2 bg-slate-800 hover:bg-slate-700 text-white border border-slate-700 hover:border-slate-600 px-6 py-3 rounded-xl font-medium transition-all"
                >
                  <Activity className="w-5 h-5 text-slate-400" />
                  {wireframeData.hero.cta_secondary.label}
                </a>
              </div>
            </div>
          </section>

          {/* Section 4: Interactive Tabs & Quick Filters */}
          <section className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
            <div className="flex items-center gap-1 bg-slate-900 p-1 rounded-xl border border-slate-800">
              {['Overview', 'Cases', 'Alerts'].map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`px-5 py-2 rounded-lg text-sm font-medium transition-all duration-200 ${
                    activeTab === tab 
                      ? 'bg-slate-800 text-white shadow-sm' 
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
                  }`}
                >
                  {tab}
                </button>
              ))}
            </div>
            <div className="flex items-center gap-3">
              <button className="flex items-center gap-2 px-4 py-2 bg-slate-900 border border-slate-800 rounded-lg text-sm font-medium text-slate-300 hover:bg-slate-800 transition-colors">
                <Filter className="w-4 h-4 text-slate-400" />
                Filters
              </button>
              <button className="flex items-center gap-2 px-4 py-2 bg-slate-900 border border-slate-800 rounded-lg text-sm font-medium text-slate-300 hover:bg-slate-800 transition-colors">
                <Download className="w-4 h-4 text-slate-400" />
                Export
              </button>
            </div>
          </section>

          {/* Section 5: KPI Cards (Imported Component Wrapper) */}
          <section className="animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-xl font-display font-semibold text-white flex items-center gap-2">
                <Activity className="w-5 h-5 text-emerald-500" />
                Real-Time Metrics
              </h2>
              <span className="text-xs text-slate-500 font-medium uppercase tracking-wider">Updated just now</span>
            </div>
            {/* The KPICards component is styled for a light theme by default in many setups, 
                but we pass it into our dark container. Assuming it inherits or we force dark mode context. */}
            <div className="[&>div>div]:bg-slate-900 [&>div>div]:border-slate-800 [&>div>div]:text-white [&>div>div_p]:text-slate-400 [&>div>div_h3]:text-white">
              <KPICards metrics={metrics} />
            </div>
          </section>

          {/* Main Dashboard Grid */}
          <div className="grid grid-cols-1 xl:grid-cols-3 gap-8 pb-12">
            
            {/* Left Column (Wider) */}
            <div className="xl:col-span-2 space-y-8">
              
              {/* Section 6: Assigned Cases Table (Imported Component Wrapper) */}
              <section className="bg-slate-900 rounded-2xl border border-slate-800 shadow-sm overflow-hidden flex flex-col h-[500px]">
                <div className="p-5 border-b border-slate-800 flex items-center justify-between bg-slate-900/50">
                  <div>
                    <h2 className="text-lg font-display font-semibold text-white flex items-center gap-2">
                      <FileText className="w-5 h-5 text-blue-400" />
                      Active Investigations
                    </h2>
                    <p className="text-sm text-slate-400 mt-1">Manage and track your assigned cases.</p>
                  </div>
                  <a href="/dashboard/cases" className="text-sm font-medium text-emerald-400 hover:text-emerald-300 flex items-center gap-1 transition-colors">
                    View All <ChevronRight className="w-4 h-4" />
                  </a>
                </div>
                <div className="flex-1 overflow-hidden [&>div]:h-full [&>div]:bg-transparent [&>div]:border-none [&_table]:text-slate-300 [&_th]:bg-slate-800/50 [&_th]:text-slate-400 [&_td]:border-slate-800 [&_tr:hover]:bg-slate-800/30">
                  <AssignedCasesTable cases={complaints} />
                </div>
              </section>

              {/* Section 7: Blockchain Audit Log (Inline Custom Section) */}
              <section className="bg-slate-900 rounded-2xl border border-slate-800 shadow-sm p-6">
                <div className="flex items-center justify-between mb-6">
                  <div>
                    <h2 className="text-lg font-display font-semibold text-white flex items-center gap-2">
                      <Database className="w-5 h-5 text-purple-400" />
                      Immutable Audit Trail
                    </h2>
                    <p className="text-sm text-slate-400 mt-1">Recent cryptographic verifications on the ledger.</p>
                  </div>
                  <button className="text-slate-400 hover:text-white transition-colors">
                    <Search className="w-5 h-5" />
                  </button>
                </div>
                
                <div className="space-y-4">
                  {recentAudits.map((audit, idx) => (
                    <div key={audit.id} className="flex items-start gap-4 p-4 rounded-xl bg-slate-800/30 border border-slate-800/50 hover:bg-slate-800/50 transition-colors group">
                      <div className={`mt-1 p-2 rounded-lg shrink-0 ${
                        audit.status === 'success' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-amber-500/10 text-amber-400'
                      }`}>
                        {audit.status === 'success' ? <CheckCircle className="w-4 h-4" /> : <AlertTriangle className="w-4 h-4" />}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between gap-2 mb-1">
                          <h4 className="text-sm font-medium text-slate-200 truncate">{audit.action}</h4>
                          <span className="text-xs text-slate-500 whitespace-nowrap">{audit.time}</span>
                        </div>
                        <div className="flex items-center gap-3 text-xs text-slate-400">
                          <span className="flex items-center gap-1">
                            <User className="w-3 h-3" /> {audit.actor}
                          </span>
                          <span className="flex items-center gap-1 font-mono text-slate-500 bg-slate-950 px-1.5 py-0.5 rounded">
                            {audit.hash}
                          </span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
                <button className="w-full mt-4 py-2.5 rounded-xl border border-slate-700 text-sm font-medium text-slate-300 hover:bg-slate-800 hover:text-white transition-colors">
                  View Full Ledger
                </button>
              </section>

            </div>

            {/* Right Column (Narrower) */}
            <div className="space-y-8">
              
              {/* Section 8: AI Predictive Alerts (Imported Component Wrapper) */}
              <section className="bg-slate-900 rounded-2xl border border-slate-800 shadow-sm overflow-hidden h-[450px] flex flex-col">
                {/* The AIPredictiveAlerts component handles its own header, but we wrap it to ensure dark mode styling cascades if needed */}
                <div className="flex-1 overflow-hidden [&>div]:h-full [&>div]:bg-transparent [&>div]:border-none [&>div>div:first-child]:bg-slate-900/50 [&>div>div:first-child]:border-slate-800 [&_h3]:text-white [&_p]:text-slate-400 [&_button]:text-slate-300 [&_button.bg-card]:bg-slate-800 [&_button.bg-card]:text-white [&>div>div:last-child>div]:bg-slate-800/30 [&>div>div:last-child>div]:border-slate-800 [&>div>div:last-child>div:hover]:bg-slate-800/60">
                  <AIPredictiveAlerts alerts={aiAlerts} />
                </div>
              </section>

              {/* Section 9: Department Risk Matrix (Inline Custom Section) */}
              <section className="bg-slate-900 rounded-2xl border border-slate-800 shadow-sm p-6">
                <div className="flex items-center justify-between mb-6">
                  <div>
                    <h2 className="text-lg font-display font-semibold text-white flex items-center gap-2">
                      <MapPin className="w-5 h-5 text-rose-400" />
                      Risk Matrix
                    </h2>
                    <p className="text-sm text-slate-400 mt-1">AI-calculated vulnerability scores.</p>
                  </div>
                </div>

                <div className="space-y-5">
                  {departmentRisks.map((dept) => (
                    <div key={dept.id} className="group">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium text-slate-200 group-hover:text-white transition-colors">
                          {dept.name}
                        </span>
                        <div className="flex items-center gap-2">
                          <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                            dept.level === 'Critical' ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20' :
                            dept.level === 'High' ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20' :
                            'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                          }`}>
                            {dept.score}/100
                          </span>
                        </div>
                      </div>
                      <div className="w-full bg-slate-800 rounded-full h-2 overflow-hidden">
                        <div 
                          className={`h-full rounded-full ${
                            dept.level === 'Critical' ? 'bg-rose-500' :
                            dept.level === 'High' ? 'bg-amber-500' :
                            'bg-emerald-500'
                          }`}
                          style={{ width: `${dept.score}%` }}
                        ></div>
                      </div>
                      <div className="flex items-center justify-between mt-1.5">
                        <span className="text-xs text-slate-500">{dept.cases} active cases</span>
                        <span className={`text-xs font-medium flex items-center gap-0.5 ${
                          dept.trend.startsWith('+') ? 'text-rose-400' : 'text-emerald-400'
                        }`}>
                          {dept.trend} {dept.trend.startsWith('+') ? '↑' : '↓'}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
                
                <a href="/dashboard/departments" className="mt-6 flex items-center justify-center gap-2 w-full py-2.5 rounded-xl bg-slate-800/50 text-sm font-medium text-slate-300 hover:bg-slate-800 hover:text-white transition-colors">
                  View Detailed Analytics <ArrowRight className="w-4 h-4" />
                </a>
              </section>

            </div>
          </div>
        </div>
      </main>
    </div>
  );
}