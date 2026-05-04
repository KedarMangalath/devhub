import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import Navbar from '../components/layout/Navbar';
import Footer from '../components/layout/Footer';
import { 
  Shield, 
  Target, 
  Users, 
  Award, 
  ArrowRight, 
  CheckCircle2, 
  Clock, 
  CircleDashed, 
  Building2, 
  Landmark, 
  Map as MapIcon, 
  Car, 
  Stethoscope, 
  ChevronRight, 
  Activity, 
  Lock, 
  Database,
  ShieldCheck,
  Server,
  FileText,
  X
} from 'lucide-react';
import { categories, dashboardMetrics } from '../mockData.js';

// ============================================================================
// INLINE UI PRIMITIVES
// Built inline to guarantee highly styled elements without relying on external 
// UI component files that may not exist in the strict file plan.
// ============================================================================

const Badge = ({ children, variant = 'default', className = '' }) => {
  const variants = {
    default: 'bg-slate-800 text-slate-300 border-slate-700',
    success: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
    warning: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
    info: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
    outline: 'bg-transparent text-slate-400 border-slate-700',
  };
  
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border backdrop-blur-sm ${variants[variant]} ${className}`}>
      {children}
    </span>
  );
};

const Button = ({ children, variant = 'primary', size = 'default', className = '', as: Component = 'button', ...props }) => {
  const variants = {
    primary: 'bg-emerald-600 text-white hover:bg-emerald-500 shadow-lg shadow-emerald-900/20 border border-emerald-500/50',
    secondary: 'bg-slate-800 text-white hover:bg-slate-700 border border-slate-700',
    outline: 'bg-transparent text-slate-300 hover:text-white border border-slate-700 hover:border-slate-500 hover:bg-slate-800/50',
    ghost: 'bg-transparent text-slate-400 hover:text-white hover:bg-slate-800',
  };
  
  const sizes = {
    default: 'px-5 py-2.5 text-sm',
    sm: 'px-3 py-1.5 text-xs',
    lg: 'px-6 py-3 text-base',
  };

  return (
    <Component 
      className={`inline-flex items-center justify-center rounded-lg font-medium transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-emerald-500/50 focus:ring-offset-2 focus:ring-offset-slate-950 ${variants[variant]} ${sizes[size]} ${className}`}
      {...props}
    >
      {children}
    </Component>
  );
};

// ============================================================================
// PAGE COMPONENT
// ============================================================================

export default function About() {
  // --- State for Interactions ---
  // 1. Timeline Filtering
  const [timelineFilter, setTimelineFilter] = useState('All');
  
  // 2. Department Logo Cloud Selection
  const [selectedDept, setSelectedDept] = useState(null);
  const [isAnimating, setIsAnimating] = useState(false);

  // --- Wireframe Data ---
  const heroData = {
    headline: "AI-Powered Transparency for a Better Tomorrow in Kerala",
    sub: "Discover how the Vigilance and Anti-Corruption Bureau leverages artificial intelligence and blockchain technology to protect citizens, ensure accountability, and eradicate systemic corruption across all government departments.",
    cta_primary: { label: "View Transparency Dashboard", href: "/dashboard" },
    cta_secondary: { label: "Read Our Mission", href: "#mission" },
    image: {
      url: "https://images.unsplash.com/photo-1589829085413-56de8ae18c73?w=800&q=80",
      alt: "Abstract representation of secure governance and justice architecture"
    }
  };

  const timelineData = {
    title: "The Evolution of Vigilance C3MS Architecture",
    items: [
      {
        date: "Phase 1: 2022",
        title: "Secure Reporting Infrastructure",
        body: "Established the foundational encrypted citizen reporting portal, ensuring absolute anonymity and secure data transmission for whistleblowers across all 14 districts.",
        status: "Completed"
      },
      {
        date: "Phase 2: 2023",
        title: "AI Credibility Assessment Integration",
        body: "Deployed advanced machine learning models to automatically evaluate incoming complaints, filtering out spam and prioritizing high-risk corruption cases for immediate action.",
        status: "Completed"
      },
      {
        date: "Phase 3: Early 2024",
        title: "Blockchain Audit Trails",
        body: "Implemented immutable blockchain ledgers for all case files and evidence uploads, guaranteeing that no complaint record can be tampered with, altered, or deleted by any party.",
        status: "Completed"
      },
      {
        date: "Phase 4: Late 2024",
        title: "Predictive Vigilance Analytics",
        body: "Launched predictive algorithms analyzing historical data across the Public Works Department and Revenue Department to identify anomalies and stop scams before they start.",
        status: "In Progress"
      },
      {
        date: "Phase 5: 2025",
        title: "Full Inter-Departmental Integration",
        body: "Connecting all major state departments including Motor Vehicles, Civil Supplies, and Health Services into a single, unified real-time monitoring grid for comprehensive oversight.",
        status: "Planned"
      }
    ]
  };

  const logoCloudData = {
    label: "Integrated Government Departments & Monitored Sectors",
    logos: [
      { name: "Public Works Department (PWD)", icon: Building2, id: 'pwd' },
      { name: "Revenue Department", icon: Landmark, id: 'rev' },
      { name: "Local Self Government (LSGD)", icon: MapIcon, id: 'lsgd' },
      { name: "Motor Vehicles Department (MVD)", icon: Car, id: 'mvd' },
      { name: "Kerala Police", icon: Shield, id: 'pol' },
      { name: "Health Services", icon: Stethoscope, id: 'hlt' }
    ]
  };

  // --- Helper Functions ---
  const getStatusIcon = (status) => {
    switch (status) {
      case 'Completed': return <CheckCircle2 className="w-5 h-5 text-emerald-400" />;
      case 'In Progress': return <Activity className="w-5 h-5 text-amber-400" />;
      case 'Planned': return <CircleDashed className="w-5 h-5 text-slate-400" />;
      default: return <Clock className="w-5 h-5 text-slate-400" />;
    }
  };

  const getStatusBadgeVariant = (status) => {
    switch (status) {
      case 'Completed': return 'success';
      case 'In Progress': return 'warning';
      case 'Planned': return 'outline';
      default: return 'default';
    }
  };

  const filteredTimeline = timelineData.items.filter(item => 
    timelineFilter === 'All' ? true : item.status === timelineFilter
  );

  const handleDeptClick = (dept) => {
    if (selectedDept?.id === dept.id) {
      setSelectedDept(null);
    } else {
      setIsAnimating(true);
      setSelectedDept(dept);
      setTimeout(() => setIsAnimating(false), 300);
    }
  };

  // Find a matching category from mockData to show realistic stats when a department is clicked
  const getMockStatsForDept = (deptName) => {
    const match = categories.find(c => deptName.includes(c.name.split(' ')[0]));
    return match ? match.count : Math.floor(Math.random() * 200) + 50;
  };

  return (
    <div className="min-h-screen flex flex-col bg-slate-950 font-body text-slate-300 selection:bg-emerald-500/30">
      {/* 1. Navbar Section */}
      <Navbar />

      <main className="flex-grow">
        
        {/* 2. MissionHero Section */}
        <section className="relative isolate overflow-hidden pt-16 pb-24 sm:pt-24 sm:pb-32 lg:pb-40 border-b border-slate-800">
          {/* Background Effects */}
          <div className="absolute inset-0 -z-10 bg-[radial-gradient(ellipse_80%_80%_at_50%_-20%,rgba(5,150,105,0.15),rgba(255,255,255,0))]"></div>
          <div className="absolute inset-y-0 right-1/2 -z-10 -mr-96 w-[200%] origin-top-right skew-x-[-30deg] bg-slate-900/50 shadow-xl shadow-emerald-900/10 ring-1 ring-slate-800 sm:-mr-80 lg:-mr-96"></div>
          
          {/* Grid Pattern */}
          <div className="absolute inset-0 -z-20 bg-[linear-gradient(to_right,#4f4f4f1a_1px,transparent_1px),linear-gradient(to_bottom,#4f4f4f1a_1px,transparent_1px)] bg-[size:24px_24px] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_0%,#000_70%,transparent_100%)]"></div>

          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
            <div className="lg:grid lg:grid-cols-12 lg:gap-16 items-center">
              
              {/* Hero Text Content */}
              <div className="lg:col-span-6 text-center lg:text-left">
                <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-sm font-medium mb-8 animate-in fade-in slide-in-from-bottom-4 duration-700">
                  <ShieldCheck className="w-4 h-4" />
                  <span>Vigilance & Anti-Corruption Bureau</span>
                </div>
                
                <h1 className="font-display text-4xl sm:text-5xl lg:text-6xl font-bold text-white tracking-tight mb-6 leading-[1.1] animate-in fade-in slide-in-from-bottom-6 duration-700 delay-100">
                  {heroData.headline.split('Kerala')[0]}
                  <span className="text-transparent bg-clip-text bg-gradient-to-r from-emerald-400 to-teal-500">Kerala</span>
                </h1>
                
                <p className="text-lg sm:text-xl text-slate-400 mb-10 leading-relaxed max-w-2xl mx-auto lg:mx-0 animate-in fade-in slide-in-from-bottom-8 duration-700 delay-200">
                  {heroData.sub}
                </p>
                
                <div className="flex flex-col sm:flex-row items-center justify-center lg:justify-start gap-4 animate-in fade-in slide-in-from-bottom-10 duration-700 delay-300">
                  <Button as={Link} to={heroData.cta_primary.href} variant="primary" size="lg" className="w-full sm:w-auto group">
                    {heroData.cta_primary.label}
                    <ArrowRight className="ml-2 w-4 h-4 group-hover:translate-x-1 transition-transform" />
                  </Button>
                  <Button as="a" href={heroData.cta_secondary.href} variant="outline" size="lg" className="w-full sm:w-auto">
                    {heroData.cta_secondary.label}
                  </Button>
                </div>

                {/* Trust Indicators */}
                <div className="mt-12 pt-8 border-t border-slate-800/50 flex flex-wrap justify-center lg:justify-start gap-6 sm:gap-10 animate-in fade-in duration-1000 delay-500">
                  <div className="flex items-center gap-2">
                    <Lock className="w-5 h-5 text-slate-500" />
                    <span className="text-sm text-slate-400 font-medium">256-bit Encryption</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Database className="w-5 h-5 text-slate-500" />
                    <span className="text-sm text-slate-400 font-medium">Immutable Ledger</span>
                  </div>
                </div>
              </div>

              {/* Hero Image & Floating Elements */}
              <div className="lg:col-span-6 mt-16 lg:mt-0 relative hidden md:block">
                <div className="relative rounded-2xl overflow-hidden border border-slate-800 shadow-2xl shadow-emerald-900/20 aspect-[4/3] group">
                  <div className="absolute inset-0 bg-gradient-to-tr from-slate-950/80 via-transparent to-transparent z-10"></div>
                  <img 
                    src={heroData.image.url} 
                    alt={heroData.image.alt}
                    className="w-full h-full object-cover transition-transform duration-1000 group-hover:scale-105 opacity-80 mix-blend-luminosity"
                  />
                  
                  {/* Floating Stat Card (Using mockData) */}
                  <div className="absolute bottom-6 left-6 right-6 z-20 bg-slate-900/90 backdrop-blur-md border border-slate-700 rounded-xl p-5 shadow-xl transform translate-y-4 opacity-0 animate-[fade-in-up_1s_ease-out_0.8s_forwards]">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-4">
                        <div className="p-3 bg-emerald-500/20 rounded-lg border border-emerald-500/30">
                          <Server className="w-6 h-6 text-emerald-400" />
                        </div>
                        <div>
                          <p className="text-sm font-medium text-slate-400">{dashboardMetrics[7].label}</p>
                          <p className="text-2xl font-display font-bold text-white">{dashboardMetrics[7].value}</p>
                        </div>
                      </div>
                      <div className="text-right">
                        <Badge variant="success" className="mb-1">{dashboardMetrics[7].trend}</Badge>
                        <p className="text-xs text-slate-500">{dashboardMetrics[7].detail}</p>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Decorative Elements */}
                <div className="absolute -top-6 -right-6 w-24 h-24 bg-emerald-500/10 rounded-full blur-2xl"></div>
                <div className="absolute -bottom-10 -left-10 w-32 h-32 bg-blue-500/10 rounded-full blur-2xl"></div>
              </div>
            </div>
          </div>
        </section>

        {/* Mission Anchor Target (Invisible structural element to satisfy wireframe CTA) */}
        <div id="mission" className="scroll-mt-24"></div>

        {/* 3. HistoryTimeline Section */}
        <section className="py-24 bg-slate-900 relative border-b border-slate-800">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            
            {/* Section Header & Filters */}
            <div className="text-center max-w-3xl mx-auto mb-16">
              <h2 className="font-display text-3xl md:text-4xl font-bold text-white mb-6">
                {timelineData.title}
              </h2>
              <p className="text-slate-400 text-lg mb-10">
                A phased approach to building the most secure, transparent, and technologically advanced anti-corruption infrastructure in the nation.
              </p>
              
              {/* Interactive Filter */}
              <div className="inline-flex flex-wrap justify-center items-center gap-2 p-1.5 bg-slate-950 rounded-xl border border-slate-800">
                {['All', 'Completed', 'In Progress', 'Planned'].map((filter) => (
                  <button
                    key={filter}
                    onClick={() => setTimelineFilter(filter)}
                    className={`px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 ${
                      timelineFilter === filter
                        ? 'bg-slate-800 text-white shadow-sm border border-slate-700'
                        : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900 border border-transparent'
                    }`}
                  >
                    {filter}
                  </button>
                ))}
              </div>
            </div>

            {/* Timeline Container */}
            <div className="relative max-w-4xl mx-auto">
              {/* Central Vertical Line (Desktop) */}
              <div className="hidden md:block absolute left-1/2 top-0 bottom-0 w-px bg-gradient-to-b from-slate-800 via-slate-700 to-slate-800 -translate-x-1/2"></div>
              
              {/* Left Vertical Line (Mobile) */}
              <div className="md:hidden absolute left-6 top-0 bottom-0 w-px bg-slate-800"></div>

              <div className="space-y-12 md:space-y-24">
                {filteredTimeline.map((item, index) => {
                  const isEven = index % 2 === 0;
                  
                  return (
                    <div key={index} className={`relative flex flex-col md:flex-row items-start ${isEven ? 'md:flex-row-reverse' : ''} group`}>
                      
                      {/* Timeline Node/Icon */}
                      <div className="absolute left-6 md:left-1/2 -translate-x-1/2 flex items-center justify-center w-10 h-10 rounded-full bg-slate-950 border-2 border-slate-800 group-hover:border-emerald-500/50 transition-colors duration-300 z-10 mt-1 md:mt-0">
                        {getStatusIcon(item.status)}
                      </div>

                      {/* Content Card */}
                      <div className={`ml-16 md:ml-0 w-full md:w-[calc(50%-3rem)] ${isEven ? 'md:pr-12 md:text-right' : 'md:pl-12'}`}>
                        <div className="bg-slate-950 border border-slate-800 rounded-2xl p-6 hover:border-slate-700 transition-all duration-300 hover:shadow-lg hover:shadow-slate-900/50 relative overflow-hidden">
                          
                          {/* Subtle background glow based on status */}
                          <div className={`absolute top-0 ${isEven ? 'right-0' : 'left-0'} w-32 h-32 rounded-full blur-3xl opacity-10 -z-10 ${
                            item.status === 'Completed' ? 'bg-emerald-500' : 
                            item.status === 'In Progress' ? 'bg-amber-500' : 'bg-slate-500'
                          }`}></div>

                          <div className={`flex items-center gap-3 mb-4 ${isEven ? 'md:justify-end' : ''}`}>
                            <span className="text-sm font-bold text-slate-500 font-display tracking-wider uppercase">
                              {item.date}
                            </span>
                            <Badge variant={getStatusBadgeVariant(item.status)}>
                              {item.status}
                            </Badge>
                          </div>
                          
                          <h3 className="text-xl font-display font-bold text-white mb-3">
                            {item.title}
                          </h3>
                          
                          <p className="text-slate-400 leading-relaxed text-sm">
                            {item.body}
                          </p>
                        </div>
                      </div>
                    </div>
                  );
                })}
                
                {filteredTimeline.length === 0 && (
                  <div className="text-center py-12">
                    <p className="text-slate-500">No phases found for the selected filter.</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        </section>

        {/* 4. LogoCloud Section */}
        <section className="py-24 bg-slate-950 relative overflow-hidden">
          {/* Decorative background */}
          <div className="absolute top-0 inset-x-0 h-px bg-gradient-to-r from-transparent via-slate-800 to-transparent"></div>
          
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
            <div className="text-center mb-16">
              <h2 className="font-display text-2xl md:text-3xl font-bold text-white mb-4">
                {logoCloudData.label}
              </h2>
              <p className="text-slate-400 max-w-2xl mx-auto">
                Our AI-driven monitoring grid spans across critical state infrastructure, ensuring no department operates in the shadows. Click a department to view active oversight metrics.
              </p>
            </div>

            {/* Interactive Grid */}
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 sm:gap-6">
              {logoCloudData.logos.map((dept) => {
                const Icon = dept.icon;
                const isSelected = selectedDept?.id === dept.id;
                
                return (
                  <button
                    key={dept.id}
                    onClick={() => handleDeptClick(dept)}
                    className={`relative flex flex-col items-center justify-center p-6 rounded-2xl border transition-all duration-300 group ${
                      isSelected 
                        ? 'bg-emerald-500/10 border-emerald-500/50 shadow-lg shadow-emerald-900/20' 
                        : 'bg-slate-900/50 border-slate-800 hover:bg-slate-800 hover:border-slate-700'
                    }`}
                  >
                    <div className={`p-3 rounded-xl mb-4 transition-colors duration-300 ${
                      isSelected ? 'bg-emerald-500 text-white' : 'bg-slate-800 text-slate-400 group-hover:text-emerald-400'
                    }`}>
                      <Icon className="w-6 h-6" strokeWidth={1.5} />
                    </div>
                    <span className={`text-xs font-medium text-center leading-tight transition-colors duration-300 ${
                      isSelected ? 'text-emerald-400' : 'text-slate-400 group-hover:text-slate-300'
                    }`}>
                      {dept.name}
                    </span>
                    
                    {/* Active Indicator Dot */}
                    {isSelected && (
                      <div className="absolute -bottom-1.5 left-1/2 -translate-x-1/2 w-3 h-3 bg-emerald-500 rounded-full border-2 border-slate-950"></div>
                    )}
                  </button>
                );
              })}
            </div>

            {/* Expanded Detail View (Interaction Result) */}
            <div className={`mt-8 transition-all duration-500 ease-in-out overflow-hidden ${
              selectedDept ? 'max-h-96 opacity-100' : 'max-h-0 opacity-0'
            }`}>
              {selectedDept && (
                <div className={`bg-slate-900 border border-slate-800 rounded-2xl p-6 sm:p-8 relative ${isAnimating ? 'animate-pulse' : ''}`}>
                  <button 
                    onClick={() => setSelectedDept(null)}
                    className="absolute top-4 right-4 p-2 text-slate-500 hover:text-white hover:bg-slate-800 rounded-lg transition-colors"
                  >
                    <X className="w-5 h-5" />
                  </button>
                  
                  <div className="flex flex-col md:flex-row items-start md:items-center gap-6">
                    <div className="p-4 bg-slate-950 rounded-xl border border-slate-800">
                      <selectedDept.icon className="w-10 h-10 text-emerald-500" strokeWidth={1.5} />
                    </div>
                    
                    <div className="flex-grow">
                      <h3 className="text-xl font-display font-bold text-white mb-2">
                        {selectedDept.name} Oversight Profile
                      </h3>
                      <p className="text-sm text-slate-400 max-w-2xl">
                        Real-time monitoring is active. The C3MS AI engine continuously analyzes procurement data, citizen reports, and historical trends within this sector to identify anomalies.
                      </p>
                    </div>
                    
                    <div className="flex gap-4 w-full md:w-auto">
                      <div className="bg-slate-950 border border-slate-800 rounded-xl p-4 flex-1 md:w-32 text-center">
                        <p className="text-xs text-slate-500 mb-1">Active Cases</p>
                        <p className="text-2xl font-display font-bold text-white">
                          {getMockStatsForDept(selectedDept.name)}
                        </p>
                      </div>
                      <div className="bg-slate-950 border border-slate-800 rounded-xl p-4 flex-1 md:w-32 text-center">
                        <p className="text-xs text-slate-500 mb-1">Risk Level</p>
                        <Badge variant={getMockStatsForDept(selectedDept.name) > 150 ? 'warning' : 'success'} className="mt-1">
                          {getMockStatsForDept(selectedDept.name) > 150 ? 'Elevated' : 'Nominal'}
                        </Badge>
                      </div>
                    </div>
                  </div>
                  
                  <div className="mt-6 pt-6 border-t border-slate-800 flex justify-end">
                    <Button as={Link} to="/explore" variant="outline" size="sm" className="gap-2">
                      <FileText className="w-4 h-4" />
                      View Public Records
                    </Button>
                  </div>
                </div>
              )}
            </div>

          </div>
        </section>

      </main>

      {/* 5. Footer Section */}
      <Footer />
    </div>
  );
}
