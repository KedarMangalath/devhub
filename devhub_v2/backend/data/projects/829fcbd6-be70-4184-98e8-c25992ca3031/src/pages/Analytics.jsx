import { useState } from 'react'
import { departments } from '../mockData'
import DashboardSidebar from '../components/layout/DashboardSidebar'
import PredictiveTrendChart from '../components/analytics/PredictiveTrendChart'
import DepartmentRiskMatrix from '../components/analytics/DepartmentRiskMatrix'
import { Download, Calendar, Filter } from 'lucide-react'
import { 
  Shield, 
  ArrowRight, 
  Activity, 
  AlertTriangle, 
  CheckCircle, 
  Clock, 
  MapPin, 
  TrendingUp, 
  BarChart3, 
  Zap, 
  ShieldAlert, 
  FileText, 
  ChevronRight, 
  Home, 
  Search, 
  ChevronDown,
  Target,
  Crosshair,
  Eye
} from 'lucide-react'

// --- Wireframe Data ---
const wireframeData = {
  navbar: {
    logo: { text: "Vigilance C3MS", icon: "Shield" },
    links: [
      { label: "Command Center", url: "/dashboard" },
      { label: "Predictive Analytics", url: "/analytics" },
      { label: "Blockchain Audit Logs", url: "/audit" },
      { label: "Department Risk Profiles", url: "/departments" }
    ],
    cta: { label: "Nodal Officer Portal", url: "/login" }
  },
  hero: {
    headline: "Predictive Vigilance: Stopping Scams Before They Start",
    sub: "Leverage AI-driven insights and historical blockchain data to identify high-risk departments, forecast potential corruption hotspots across Kerala, and allocate investigative resources proactively.",
    cta_primary: { label: "Generate Risk Forecast", url: "/analytics/forecast" },
    cta_secondary: { label: "View Live Heatmap", url: "/analytics/heatmap" },
    image: {
      url: "https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=800&q=80",
      alt: "Advanced data analytics dashboard showing predictive trends and corruption heatmaps"
    }
  },
  timeline: {
    title: "AI-Detected Anomaly Alerts & Predictive Risk Escalations",
    items: [
      {
        date: "2023-10-24 09:15 AM",
        title: "High Risk Alert: Public Works Department (PWD)",
        body: "AI models detected a 300% spike in anonymous complaints regarding fraudulent road contract allocations in the Kozhikode district over the last 48 hours.",
        status: "High Risk"
      },
      {
        date: "2023-10-23 14:30 PM",
        title: "Pattern Identified: Revenue Department Bribery",
        body: "Sequential reports indicate a coordinated bribery request for building permits across multiple village offices in Thiruvananthapuram. AI Credibility score: 92%.",
        status: "Investigating"
      },
      {
        date: "2023-10-22 11:05 AM",
        title: "Disproportionate Assets Flagged in RTO",
        body: "Cross-referencing Motor Vehicles Department (MVD) records with recent citizen submissions reveals severe anomalies in asset declarations by regional officers.",
        status: "Investigating"
      },
      {
        date: "2023-10-20 16:45 PM",
        title: "Service Denial Cluster Resolved: Local Self Government",
        body: "Intervention successful in Thrissur municipality following predictive alerts of systemic service denial at the village office level. Operations normalized and audited.",
        status: "Resolved"
      },
      {
        date: "2023-10-18 08:20 AM",
        title: "Emerging Threat: Civil Supplies Distribution",
        body: "Predictive algorithms forecast a high probability of supply chain leakage in the Ernakulam district based on historical seasonal data and recent minor complaints.",
        status: "High Risk"
      }
    ]
  }
};

// --- Inline UI Primitives ---
const Badge = ({ children, variant = 'default', className = '' }) => {
  const variants = {
    default: 'bg-slate-100 text-slate-800 border-slate-200',
    success: 'bg-emerald-100 text-emerald-800 border-emerald-200',
    warning: 'bg-amber-100 text-amber-800 border-amber-200',
    danger: 'bg-rose-100 text-rose-800 border-rose-200',
    info: 'bg-blue-100 text-blue-800 border-blue-200',
  };
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border ${variants[variant]} ${className}`}>
      {children}
    </span>
  );
};

const Button = ({ children, variant = 'primary', className = '', ...props }) => {
  const variants = {
    primary: 'bg-[#059669] text-white hover:bg-[#047857] shadow-sm',
    secondary: 'bg-white text-slate-700 border border-slate-300 hover:bg-slate-50 shadow-sm',
    outline: 'bg-transparent text-[#059669] border border-[#059669] hover:bg-[#059669] hover:text-white',
    ghost: 'bg-transparent text-slate-600 hover:bg-slate-100',
  };
  return (
    <button 
      className={`inline-flex items-center justify-center px-4 py-2 text-sm font-medium rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[#059669] ${variants[variant]} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
};

const Card = ({ children, className = '' }) => (
  <div className={`bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden ${className}`}>
    {children}
  </div>
);

// --- Main Page Component ---
export default function Analytics() {
  // Local State for Interactions
  const [timeRange, setTimeRange] = useState('6m');
  const [timelineFilter, setTimelineFilter] = useState('All');
  const [searchQuery, setSearchQuery] = useState('');
  const [activeRegionTab, setActiveRegionTab] = useState('North');

  // Filter Timeline Data
  const filteredTimeline = wireframeData.timeline.items.filter(item => {
    const matchesFilter = timelineFilter === 'All' || item.status === timelineFilter;
    const matchesSearch = item.title.toLowerCase().includes(searchQuery.toLowerCase()) || 
                          item.body.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesFilter && matchesSearch;
  });

  // Helper for Timeline Status Colors
  const getStatusConfig = (status) => {
    switch (status) {
      case 'High Risk': return { color: 'text-rose-600', bg: 'bg-rose-100', border: 'border-rose-200', icon: AlertTriangle, badge: 'danger' };
      case 'Investigating': return { color: 'text-amber-600', bg: 'bg-amber-100', border: 'border-amber-200', icon: Search, badge: 'warning' };
      case 'Resolved': return { color: 'text-emerald-600', bg: 'bg-emerald-100', border: 'border-emerald-200', icon: CheckCircle, badge: 'success' };
      default: return { color: 'text-slate-600', bg: 'bg-slate-100', border: 'border-slate-200', icon: Activity, badge: 'default' };
    }
  };

  return (
    <div className="flex h-screen overflow-hidden bg-[#F8FAFC] font-body text-slate-900">
      {/* Sidebar Layout Wrapper */}
      <DashboardSidebar />

      {/* Main Content Area */}
      <main className="flex-1 overflow-y-auto relative">
        
        {/* SECTION 1: Analytics Header (Navbar context) */}
        <header className="sticky top-0 z-30 bg-white/80 backdrop-blur-md border-b border-slate-200 px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 text-slate-500 text-sm font-medium">
              <Home className="w-4 h-4" />
              <ChevronRight className="w-4 h-4" />
              <span className="text-slate-900">Command Center</span>
              <ChevronRight className="w-4 h-4" />
              <span className="text-[#059669] font-semibold">Predictive Analytics</span>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <div className="hidden md:flex items-center bg-slate-100 rounded-lg p-1">
              {['1m', '3m', '6m', '1y'].map(range => (
                <button
                  key={range}
                  onClick={() => setTimeRange(range)}
                  className={`px-3 py-1 text-xs font-medium rounded-md transition-all ${
                    timeRange === range 
                      ? 'bg-white text-slate-900 shadow-sm' 
                      : 'text-slate-500 hover:text-slate-700'
                  }`}
                >
                  {range.toUpperCase()}
                </button>
              ))}
            </div>
            <Button variant="outline" className="gap-2 hidden sm:flex">
              <Download className="w-4 h-4" />
              Export Report
            </Button>
          </div>
        </header>

        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
          
          {/* SECTION 2: Page Hero */}
          <section className="relative rounded-2xl overflow-hidden bg-slate-900 text-white shadow-xl border border-slate-800">
            <div className="absolute inset-0 z-0">
              <img 
                src={wireframeData.hero.image.url} 
                alt={wireframeData.hero.image.alt}
                className="w-full h-full object-cover opacity-30 mix-blend-luminosity"
              />
              <div className="absolute inset-0 bg-gradient-to-r from-slate-900 via-slate-900/90 to-transparent" />
            </div>
            
            <div className="relative z-10 p-8 md:p-12 lg:w-2/3">
              <Badge variant="success" className="mb-6 bg-emerald-500/20 text-emerald-300 border-emerald-500/30 backdrop-blur-sm">
                <Zap className="w-3 h-3 mr-1.5" /> AI Engine Active
              </Badge>
              <h1 className="text-3xl md:text-4xl lg:text-5xl font-display font-bold tracking-tight mb-4 leading-tight">
                {wireframeData.hero.headline}
              </h1>
              <p className="text-slate-300 text-lg mb-8 max-w-2xl leading-relaxed">
                {wireframeData.hero.sub}
              </p>
              <div className="flex flex-wrap items-center gap-4">
                <Button variant="primary" className="gap-2 text-base px-6 py-3">
                  <Target className="w-5 h-5" />
                  {wireframeData.hero.cta_primary.label}
                </Button>
                <Button variant="secondary" className="gap-2 text-base px-6 py-3 bg-white/10 text-white border-white/20 hover:bg-white/20">
                  <MapPin className="w-5 h-5" />
                  {wireframeData.hero.cta_secondary.label}
                </Button>
              </div>
            </div>
          </section>

          {/* SECTION 3: Quick Stats / KPI Cards */}
          <section className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {[
              { label: 'Forecast Accuracy', value: '94.2%', trend: '+2.1%', icon: Crosshair, color: 'text-emerald-600', bg: 'bg-emerald-100' },
              { label: 'High Risk Departments', value: '3', trend: '-1', icon: ShieldAlert, color: 'text-rose-600', bg: 'bg-rose-100' },
              { label: 'Anomalies Detected', value: '1,284', trend: '+14%', icon: Activity, color: 'text-blue-600', bg: 'bg-blue-100' },
              { label: 'Preventative Actions', value: '42', trend: '+8', icon: Shield, color: 'text-amber-600', bg: 'bg-amber-100' }
            ].map((stat, idx) => (
              <Card key={idx} className="p-5 flex items-start justify-between hover:shadow-md transition-shadow">
                <div>
                  <p className="text-sm font-medium text-slate-500 mb-1">{stat.label}</p>
                  <div className="flex items-baseline gap-2">
                    <h3 className="text-2xl font-display font-bold text-slate-900">{stat.value}</h3>
                    <span className={`text-xs font-medium ${stat.trend.startsWith('+') ? 'text-emerald-600' : 'text-rose-600'}`}>
                      {stat.trend}
                    </span>
                  </div>
                </div>
                <div className={`p-3 rounded-lg ${stat.bg}`}>
                  <stat.icon className={`w-5 h-5 ${stat.color}`} />
                </div>
              </Card>
            ))}
          </section>

          {/* SECTION 4 & 5: Charts Grid */}
          <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Predictive Trend Chart */}
            <div className="flex flex-col h-[450px]">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h2 className="text-lg font-display font-bold text-slate-900">Statewide Corruption Forecast</h2>
                  <p className="text-sm text-slate-500">6-month predictive volume based on historical data</p>
                </div>
                <Badge variant="info" className="gap-1">
                  <TrendingUp className="w-3 h-3" /> Trending
                </Badge>
              </div>
              <div className="flex-1 bg-white rounded-xl border border-slate-200 shadow-sm p-4">
                <PredictiveTrendChart />
              </div>
            </div>

            {/* Department Risk Matrix */}
            <div className="flex flex-col h-[450px]">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h2 className="text-lg font-display font-bold text-slate-900">Department Risk Matrix</h2>
                  <p className="text-sm text-slate-500">Volume vs. Resolution Time vs. AI Risk Score</p>
                </div>
                <Button variant="ghost" className="h-8 px-2 text-slate-500">
                  <Filter className="w-4 h-4 mr-2" /> Filter
                </Button>
              </div>
              <div className="flex-1 bg-white rounded-xl border border-slate-200 shadow-sm p-4">
                <DepartmentRiskMatrix departments={departments} />
              </div>
            </div>
          </section>

          {/* SECTION 6: AI-Detected Anomaly Alerts Timeline (Wireframe) */}
          <section className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
            <div className="p-6 border-b border-slate-200 bg-slate-50/50 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <h2 className="text-xl font-display font-bold text-slate-900 flex items-center gap-2">
                  <Zap className="w-5 h-5 text-amber-500" />
                  {wireframeData.timeline.title}
                </h2>
                <p className="text-sm text-slate-500 mt-1">Real-time escalations from the C3MS Predictive Engine</p>
              </div>
              
              {/* Interactive Filters */}
              <div className="flex items-center gap-3">
                <div className="relative">
                  <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                  <input 
                    type="text" 
                    placeholder="Search alerts..." 
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="pl-9 pr-4 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#059669] focus:border-transparent w-full sm:w-48"
                  />
                </div>
                <select 
                  value={timelineFilter}
                  onChange={(e) => setTimelineFilter(e.target.value)}
                  className="py-2 pl-3 pr-8 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#059669] appearance-none bg-white"
                >
                  <option value="All">All Statuses</option>
                  <option value="High Risk">High Risk</option>
                  <option value="Investigating">Investigating</option>
                  <option value="Resolved">Resolved</option>
                </select>
              </div>
            </div>

            <div className="p-6">
              {filteredTimeline.length === 0 ? (
                <div className="text-center py-12">
                  <div className="w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center mx-auto mb-4">
                    <Search className="w-8 h-8 text-slate-400" />
                  </div>
                  <h3 className="text-lg font-medium text-slate-900">No alerts found</h3>
                  <p className="text-slate-500">Try adjusting your search or filters.</p>
                </div>
              ) : (
                <div className="relative border-l-2 border-slate-200 ml-4 space-y-8 pb-4">
                  {filteredTimeline.map((item, index) => {
                    const config = getStatusConfig(item.status);
                    const Icon = config.icon;
                    
                    return (
                      <div key={index} className="relative pl-8 group">
                        {/* Timeline Node */}
                        <div className={`absolute -left-[17px] top-1 w-8 h-8 rounded-full border-4 border-white flex items-center justify-center shadow-sm transition-transform group-hover:scale-110 ${config.bg} ${config.color}`}>
                          <Icon className="w-3.5 h-3.5" />
                        </div>
                        
                        {/* Content Card */}
                        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm hover:shadow-md transition-shadow">
                          <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-2 mb-3">
                            <div>
                              <div className="flex items-center gap-2 mb-1">
                                <Badge variant={config.badge}>{item.status}</Badge>
                                <span className="text-xs font-medium text-slate-500 flex items-center gap-1">
                                  <Calendar className="w-3 h-3" />
                                  {item.date}
                                </span>
                              </div>
                              <h3 className="text-base font-bold text-slate-900 font-display leading-tight">
                                {item.title}
                              </h3>
                            </div>
                            <Button variant="ghost" className="h-8 px-3 text-xs shrink-0 self-start">
                              View Details
                            </Button>
                          </div>
                          <p className="text-sm text-slate-600 leading-relaxed">
                            {item.body}
                          </p>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </section>

          {/* SECTION 7: Regional Risk Distribution (Inline UI) */}
          <section className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
              <div className="p-5 border-b border-slate-200 flex items-center justify-between">
                <h2 className="text-lg font-display font-bold text-slate-900">Regional Risk Distribution</h2>
                <div className="flex bg-slate-100 rounded-lg p-1">
                  {['North', 'Central', 'South'].map(region => (
                    <button
                      key={region}
                      onClick={() => setActiveRegionTab(region)}
                      className={`px-4 py-1.5 text-sm font-medium rounded-md transition-all ${
                        activeRegionTab === region 
                          ? 'bg-white text-slate-900 shadow-sm' 
                          : 'text-slate-500 hover:text-slate-700'
                      }`}
                    >
                      {region}
                    </button>
                  ))}
                </div>
              </div>
              <div className="p-5 space-y-5">
                {[
                  { district: 'Kozhikode', risk: 85, trend: 'up' },
                  { district: 'Kannur', risk: 62, trend: 'down' },
                  { district: 'Wayanad', risk: 45, trend: 'stable' },
                  { district: 'Kasaragod', risk: 30, trend: 'down' },
                ].map((item, idx) => (
                  <div key={idx} className="flex items-center gap-4">
                    <div className="w-24 shrink-0">
                      <span className="text-sm font-medium text-slate-700">{item.district}</span>
                    </div>
                    <div className="flex-1 h-2.5 bg-slate-100 rounded-full overflow-hidden">
                      <div 
                        className={`h-full rounded-full ${
                          item.risk > 75 ? 'bg-rose-500' : item.risk > 50 ? 'bg-amber-500' : 'bg-emerald-500'
                        }`}
                        style={{ width: `${item.risk}%` }}
                      />
                    </div>
                    <div className="w-16 text-right flex items-center justify-end gap-1">
                      <span className="text-sm font-bold text-slate-900">{item.risk}</span>
                      {item.trend === 'up' && <TrendingUp className="w-3 h-3 text-rose-500" />}
                      {item.trend === 'down' && <TrendingUp className="w-3 h-3 text-emerald-500 rotate-180" />}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* SECTION 8: Actionable Recommendations */}
            <div className="bg-slate-900 rounded-xl border border-slate-800 shadow-sm overflow-hidden text-white flex flex-col">
              <div className="p-5 border-b border-slate-800">
                <h2 className="text-lg font-display font-bold flex items-center gap-2">
                  <Target className="w-5 h-5 text-[#059669]" />
                  AI Recommendations
                </h2>
              </div>
              <div className="p-5 flex-1 space-y-4 overflow-y-auto">
                <div className="bg-slate-800/50 rounded-lg p-4 border border-slate-700/50 hover:border-slate-600 transition-colors">
                  <div className="flex items-start gap-3">
                    <div className="mt-0.5 w-2 h-2 rounded-full bg-rose-500 shrink-0" />
                    <div>
                      <h4 className="text-sm font-semibold mb-1">Initiate PWD Audit (Kozhikode)</h4>
                      <p className="text-xs text-slate-400 mb-3">High probability of contract fraud detected. Recommend immediate freeze on new tenders.</p>
                      <Button variant="primary" className="h-7 px-3 text-xs w-full">Deploy Task Force</Button>
                    </div>
                  </div>
                </div>
                <div className="bg-slate-800/50 rounded-lg p-4 border border-slate-700/50 hover:border-slate-600 transition-colors">
                  <div className="flex items-start gap-3">
                    <div className="mt-0.5 w-2 h-2 rounded-full bg-amber-500 shrink-0" />
                    <div>
                      <h4 className="text-sm font-semibold mb-1">Review RTO Asset Declarations</h4>
                      <p className="text-xs text-slate-400 mb-3">Anomalies found in 14 officer profiles. Cross-reference with recent property registrations.</p>
                      <Button variant="secondary" className="h-7 px-3 text-xs w-full bg-slate-700 text-white border-slate-600 hover:bg-slate-600">Schedule Review</Button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </section>

          {/* SECTION 9: Footer Actions */}
          <footer className="py-6 border-t border-slate-200 flex flex-col sm:flex-row items-center justify-between gap-4 text-sm text-slate-500">
            <p>Data refreshed automatically every 15 minutes via Blockchain Oracle.</p>
            <div className="flex items-center gap-4">
              <button className="hover:text-slate-900 transition-colors flex items-center gap-1">
                <Eye className="w-4 h-4" /> View Raw Data
              </button>
              <button className="hover:text-slate-900 transition-colors flex items-center gap-1">
                <FileText className="w-4 h-4" /> Documentation
              </button>
            </div>
          </footer>

        </div>
      </main>
    </div>
  );
}