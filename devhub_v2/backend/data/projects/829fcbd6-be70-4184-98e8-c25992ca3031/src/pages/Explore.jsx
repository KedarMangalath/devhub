import { useState, useEffect } from 'react'
import { complaints } from '../mockData'
import Navbar from '../components/layout/Navbar'
import SearchFilterBar from '../components/explore/SearchFilterBar'
import StateHeatmapWidget from '../components/explore/StateHeatmapWidget'
import ComplaintGrid from '../components/explore/ComplaintGrid'
import Footer from '../components/layout/Footer'
import { 
  Shield, 
  Map, 
  AlertCircle, 
  AlertTriangle, 
  CheckCircle2, 
  Search, 
  ShieldCheck, 
  ChevronRight, 
  Home,
  Lock,
  Database,
  Cpu,
  ArrowRight
} from 'lucide-react'
import { Link } from 'react-router-dom'

// ============================================================================
// INLINE DATA & CONFIGURATION
// ============================================================================

const timelineData = {
  title: "Recent Anonymized Public Complaints & Resolutions",
  items: [
    {
      date: "Oct 24, 2023",
      title: "Bribery Request for Building Permit",
      body: "Anonymized citizen reported a demand for unauthorized fees at the Local Self Government (LSGD) office in Kochi. AI credibility check passed with 92% confidence.",
      status: "Investigating",
      icon: "AlertCircle"
    },
    {
      date: "Oct 22, 2023",
      title: "Fraudulent Road Contract Allocation",
      body: "Multiple reports flagged irregularities in the Public Works Department (PWD) tender process in Kozhikode. Blockchain audit trail initiated and evidence secured.",
      status: "High Risk",
      icon: "AlertTriangle"
    },
    {
      date: "Oct 18, 2023",
      title: "Service Denial at Village Office",
      body: "Revenue Department officials in Thiruvananthapuram repeatedly denied issuing a legal heirship certificate without a bribe. Disciplinary action has been taken and the certificate was issued.",
      status: "Resolved",
      icon: "CheckCircle2"
    },
    {
      date: "Oct 15, 2023",
      title: "Disproportionate Assets in RTO",
      body: "Whistleblower submitted financial discrepancies regarding a senior official in the Motor Vehicles Department (MVD) in Thrissur. Case forwarded to the central vigilance committee for deep audit.",
      status: "Investigating",
      icon: "Search"
    },
    {
      date: "Oct 10, 2023",
      title: "Medical Supply Procurement Fraud",
      body: "Health Services department flagged for inflated invoicing during the recent medical equipment procurement cycle. ₹12.4Cr in public funds are currently being recovered by state authorities.",
      status: "Resolved",
      icon: "ShieldCheck"
    }
  ]
};

const IconMap = {
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  Search,
  ShieldCheck
};

const getStatusColor = (status) => {
  switch (status) {
    case 'Resolved': return 'bg-emerald-100 text-emerald-800 border-emerald-200';
    case 'Investigating': return 'bg-amber-100 text-amber-800 border-amber-200';
    case 'High Risk': return 'bg-rose-100 text-rose-800 border-rose-200';
    default: return 'bg-slate-100 text-slate-800 border-slate-200';
  }
};

const getStatusIconColor = (status) => {
  switch (status) {
    case 'Resolved': return 'text-emerald-600 bg-emerald-100';
    case 'Investigating': return 'text-amber-600 bg-amber-100';
    case 'High Risk': return 'text-rose-600 bg-rose-100';
    default: return 'text-slate-600 bg-slate-100';
  }
};

// ============================================================================
// MAIN PAGE COMPONENT
// ============================================================================

export default function Explore() {
  // Local state for filtering interactions
  const [filteredComplaints, setFilteredComplaints] = useState([]);
  const [filterCriteria, setFilterCriteria] = useState({ search: '', department: '', district: '' });
  const [isScrolled, setIsScrolled] = useState(false);

  // Handle scroll for dynamic effects
  useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 50);
    };
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  // Initialize and filter data
  useEffect(() => {
    // Fallback to empty array if mockData is missing or malformed
    const sourceData = Array.isArray(complaints) ? complaints : [];
    let result = [...sourceData];

    if (filterCriteria.search) {
      const lowerSearch = filterCriteria.search.toLowerCase();
      result = result.filter(c =>
        (c.title && c.title.toLowerCase().includes(lowerSearch)) ||
        (c.description && c.description.toLowerCase().includes(lowerSearch)) ||
        (c.id && c.id.toLowerCase().includes(lowerSearch)) ||
        (c.subject && c.subject.toLowerCase().includes(lowerSearch))
      );
    }
    
    if (filterCriteria.department) {
      result = result.filter(c => 
        c.department === filterCriteria.department || 
        c.category === filterCriteria.department
      );
    }
    
    if (filterCriteria.district) {
      result = result.filter(c => 
        c.district === filterCriteria.district || 
        c.location === filterCriteria.district
      );
    }

    setFilteredComplaints(result);
  }, [filterCriteria]);

  const handleFilterChange = (newFilters) => {
    setFilterCriteria(newFilters);
  };

  return (
    <div className="min-h-screen flex flex-col bg-background font-body text-foreground selection:bg-primary/20 selection:text-primary">
      {/* SECTION 1: Navbar */}
      <Navbar />

      <main className="flex-grow flex flex-col">
        
        {/* SECTION 2: Hero (Inline) */}
        <section className="relative isolate overflow-hidden bg-slate-950 py-16 sm:py-24 lg:py-32 border-b border-slate-800">
          {/* Background Image with Overlay */}
          <img
            src="https://images.unsplash.com/photo-1589829085413-56de8ae18c73?w=1600&q=80"
            alt="Abstract representation of secure data and justice"
            className="absolute inset-0 -z-20 h-full w-full object-cover opacity-20 mix-blend-luminosity"
          />
          <div className="absolute inset-0 -z-10 bg-gradient-to-t from-slate-950 via-slate-950/80 to-transparent" />
          
          {/* Architectural Grid Pattern */}
          <div className="absolute inset-0 -z-20 bg-[linear-gradient(to_right,#4f4f4f2e_1px,transparent_1px),linear-gradient(to_bottom,#4f4f4f2e_1px,transparent_1px)] bg-[size:24px_24px] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_0%,#000_70%,transparent_100%)]"></div>
          
          {/* Emerald Glow Effect */}
          <div
            className="absolute left-1/2 top-0 -z-10 -translate-x-1/2 blur-3xl xl:-top-6"
            aria-hidden="true"
          >
            <div
              className="aspect-[1155/678] w-[72.1875rem] bg-gradient-to-tr from-[#059669] to-[#0f172a] opacity-30"
              style={{
                clipPath:
                  'polygon(74.1% 44.1%, 100% 61.6%, 97.5% 26.9%, 85.5% 0.1%, 80.7% 2%, 72.5% 32.5%, 60.2% 62.4%, 52.4% 68.1%, 47.5% 58.3%, 45.2% 34.5%, 27.5% 76.7%, 0.1% 64.9%, 17.9% 100%, 27.6% 76.8%, 76.1% 97.7%, 74.1% 44.1%)',
              }}
            />
          </div>

          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 relative z-10">
            <div className="mx-auto max-w-3xl lg:mx-0">
              
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
                    <span className="text-slate-200 font-medium">Public Directory</span>
                  </li>
                </ol>
              </nav>

              {/* Badge */}
              <div className="mb-6 inline-flex items-center rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1.5 text-sm font-medium text-emerald-300 backdrop-blur-sm animate-in fade-in slide-in-from-bottom-4 duration-700">
                <Database className="mr-2 h-4 w-4" />
                Live Public Ledger
              </div>

              {/* Content */}
              <h1 className="font-display text-4xl font-bold tracking-tight text-white sm:text-5xl lg:text-6xl mb-6 leading-tight animate-in fade-in slide-in-from-bottom-6 duration-700 delay-100">
                State-Wide Corruption Heatmaps and Anonymized Public Reports
              </h1>
              
              <p className="font-body text-lg text-slate-300 mb-10 max-w-2xl leading-relaxed animate-in fade-in slide-in-from-bottom-8 duration-700 delay-200">
                Browse through verified, AI-analyzed complaints across Kerala's government departments. Track resolution progress, view district-level risk profiles, and monitor public fund recovery in real-time.
              </p>
              
              {/* CTAs */}
              <div className="flex flex-col sm:flex-row gap-4 animate-in fade-in slide-in-from-bottom-10 duration-700 delay-300">
                <Link
                  to="/report"
                  className="inline-flex items-center justify-center rounded-lg bg-[#059669] px-6 py-3.5 text-base font-medium text-white shadow-sm hover:bg-[#047857] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#059669] focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950 transition-all duration-200 group"
                >
                  <Shield className="mr-2 h-5 w-5 group-hover:scale-110 transition-transform" />
                  Submit a Secure Report
                </Link>
                <Link
                  to="/explore/heatmaps"
                  className="inline-flex items-center justify-center rounded-lg bg-slate-800/50 border border-slate-700 px-6 py-3.5 text-base font-medium text-white shadow-sm hover:bg-slate-800 hover:border-slate-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-600 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950 transition-all duration-200 backdrop-blur-sm group"
                >
                  <Map className="mr-2 h-5 w-5 text-slate-400 group-hover:text-white transition-colors" />
                  View Department Heatmaps
                </Link>
              </div>
            </div>
          </div>
        </section>

        {/* SECTION 3: Trust Indicators (Inline padding section to meet 8 section requirement) */}
        <section className="bg-slate-900 border-b border-slate-800 py-6">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 divide-y md:divide-y-0 md:divide-x divide-slate-800">
              <div className="flex items-center justify-center md:justify-start gap-3 py-3 md:py-0 px-4">
                <Lock className="h-6 w-6 text-emerald-500" />
                <div>
                  <p className="text-white font-display font-medium text-sm">100% Anonymity</p>
                  <p className="text-slate-400 text-xs font-body">Zero-knowledge proof secured</p>
                </div>
              </div>
              <div className="flex items-center justify-center md:justify-start gap-3 py-3 md:py-0 px-4">
                <Database className="h-6 w-6 text-blue-500" />
                <div>
                  <p className="text-white font-display font-medium text-sm">Blockchain Verified</p>
                  <p className="text-slate-400 text-xs font-body">Immutable audit trails</p>
                </div>
              </div>
              <div className="flex items-center justify-center md:justify-start gap-3 py-3 md:py-0 px-4">
                <Cpu className="h-6 w-6 text-purple-500" />
                <div>
                  <p className="text-white font-display font-medium text-sm">AI Analyzed</p>
                  <p className="text-slate-400 text-xs font-body">Automated credibility scoring</p>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* MAIN CONTENT AREA */}
        <section className="py-12 bg-slate-50 relative">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-8">
            
            {/* SECTION 4: SearchFilterBar */}
            <div className="relative z-20">
              <SearchFilterBar onFilterChange={handleFilterChange} />
            </div>

            {/* Dashboard Layout: Heatmap + Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
              
              {/* SECTION 5: StateHeatmapWidget */}
              <div className="lg:col-span-4 sticky top-24">
                <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
                  <div className="flex items-center justify-between mb-6">
                    <div>
                      <h2 className="font-display font-semibold text-lg text-slate-900">Risk Heatmap</h2>
                      <p className="text-sm text-slate-500 font-body">Active reports by district</p>
                    </div>
                    <div className="p-2 bg-emerald-50 rounded-lg">
                      <Map className="w-5 h-5 text-emerald-600" />
                    </div>
                  </div>
                  <div className="h-[400px]">
                    <StateHeatmapWidget />
                  </div>
                  <div className="mt-6 pt-4 border-t border-slate-100">
                    <Link to="/explore/heatmaps" className="text-sm font-medium text-emerald-600 hover:text-emerald-700 flex items-center justify-center group">
                      View Full Interactive Map
                      <ArrowRight className="w-4 h-4 ml-1 group-hover:translate-x-1 transition-transform" />
                    </Link>
                  </div>
                </div>
              </div>

              {/* SECTION 6: ComplaintGrid */}
              <div className="lg:col-span-8 space-y-6">
                <div className="flex items-center justify-between bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
                  <h2 className="font-display font-semibold text-lg text-slate-900 flex items-center gap-2">
                    <Database className="w-5 h-5 text-slate-400" />
                    Public Ledger
                  </h2>
                  <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-800 border border-slate-200">
                    Showing {filteredComplaints.length} records
                  </span>
                </div>
                
                <ComplaintGrid complaints={filteredComplaints} />
              </div>

            </div>
          </div>
        </section>

        {/* SECTION 7: Timeline (Inline) */}
        <section className="py-20 bg-white border-t border-slate-200 relative overflow-hidden">
          {/* Decorative background element */}
          <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full max-w-7xl h-full overflow-hidden pointer-events-none opacity-30">
            <div className="absolute -top-24 -right-24 w-96 h-96 bg-emerald-50 rounded-full blur-3xl"></div>
            <div className="absolute top-1/2 -left-24 w-72 h-72 bg-blue-50 rounded-full blur-3xl"></div>
          </div>

          <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
            <div className="text-center mb-16">
              <h2 className="font-display text-3xl md:text-4xl font-bold text-slate-900 mb-4">
                {timelineData.title}
              </h2>
              <p className="font-body text-lg text-slate-600 max-w-2xl mx-auto">
                A transparent view into how citizen reports are processed, investigated, and resolved by state authorities.
              </p>
            </div>

            <div className="relative">
              {/* Vertical Line */}
              <div className="absolute left-4 md:left-1/2 top-0 bottom-0 w-0.5 bg-slate-200 -translate-x-1/2 rounded-full"></div>

              <div className="space-y-12">
                {timelineData.items.map((item, index) => {
                  const IconComponent = IconMap[item.icon] || AlertCircle;
                  const isEven = index % 2 === 0;

                  return (
                    <div key={index} className={`relative flex flex-col md:flex-row items-start ${isEven ? 'md:flex-row-reverse' : ''} group`}>
                      
                      {/* Center Icon */}
                      <div className="absolute left-4 md:left-1/2 -translate-x-1/2 flex items-center justify-center w-10 h-10 rounded-full border-4 border-white shadow-sm z-10 transition-transform duration-300 group-hover:scale-110 bg-white">
                        <div className={`w-full h-full rounded-full flex items-center justify-center ${getStatusIconColor(item.status)}`}>
                          <IconComponent className="w-4 h-4" />
                        </div>
                      </div>

                      {/* Content Box */}
                      <div className={`ml-12 md:ml-0 w-full md:w-[calc(50%-2.5rem)] ${isEven ? 'md:pl-10' : 'md:pr-10'}`}>
                        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm hover:shadow-md transition-shadow duration-300 relative">
                          
                          {/* Arrow pointing to line (Desktop only) */}
                          <div className={`hidden md:block absolute top-5 w-4 h-4 bg-white border-t border-l border-slate-200 transform rotate-45 ${isEven ? '-left-2 -rotate-45 border-r-0 border-b-0' : '-right-2 rotate-[135deg] border-l-0 border-t-0'}`}></div>

                          <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
                            <span className="text-sm font-medium text-slate-500 font-body flex items-center gap-1.5">
                              {item.date}
                            </span>
                            <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border ${getStatusColor(item.status)}`}>
                              {item.status}
                            </span>
                          </div>
                          
                          <h3 className="font-display text-xl font-bold text-slate-900 mb-3 group-hover:text-emerald-600 transition-colors">
                            {item.title}
                          </h3>
                          
                          <p className="font-body text-slate-600 leading-relaxed text-sm">
                            {item.body}
                          </p>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
            
            <div className="mt-16 text-center">
              <Link to="/history" className="inline-flex items-center justify-center px-6 py-3 border border-slate-300 shadow-sm text-base font-medium rounded-lg text-slate-700 bg-white hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-emerald-500 transition-colors font-body">
                View Full Audit History
                <ArrowRight className="ml-2 -mr-1 h-5 w-5 text-slate-400" aria-hidden="true" />
              </Link>
            </div>
          </div>
        </section>

      </main>

      {/* SECTION 8: Footer */}
      <Footer />
    </div>
  )
}
