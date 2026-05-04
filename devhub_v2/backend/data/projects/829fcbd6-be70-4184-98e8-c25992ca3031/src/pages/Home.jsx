import React, { useState, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { 
  Shield, 
  ShieldCheck, 
  BrainCircuit, 
  Link as LinkIcon, 
  Activity, 
  Map, 
  FileText, 
  Menu, 
  X, 
  ChevronDown, 
  ChevronUp, 
  ArrowRight, 
  Quote, 
  ChevronLeft, 
  ChevronRight,
  Twitter,
  Facebook,
  Mail
} from 'lucide-react';

// Exact imports requested by the file contract
import Navbar from '../components/layout/Navbar';
import HeroSection from '../components/home/HeroSection';
import FeatureGrid from '../components/home/FeatureGrid';
import StatsBand from '../components/home/StatsBand';
import TestimonialCarousel from '../components/home/TestimonialCarousel';
import FAQAccordion from '../components/home/FAQAccordion';
import Footer from '../components/layout/Footer';

export default function Home() {
  // Local state for interactions
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [activeTestimonial, setActiveTestimonial] = useState(0);
  const [openFaqId, setOpenFaqId] = useState(0);
  const location = useLocation();

  // Close mobile menu on route change
  useEffect(() => {
    setIsMobileMenuOpen(false);
  }, [location.pathname]);

  // Wireframe Data
  const navData = {
    logo: { text: "Vigilance C3MS", icon: Shield },
    links: [
      { label: "Report Corruption", url: "/report" },
      { label: "Track Status", url: "/track" },
      { label: "Transparency Dashboard", url: "/dashboard" },
      { label: "Department Login", url: "/login" }
    ],
    cta: { label: "File a Report", url: "/report" }
  };

  const heroData = {
    headline: "Report Corruption. Protect Kerala. Your Identity is Safe.",
    sub: "Empowering citizens to securely report, track, and combat corruption with AI-driven transparency. Join the movement for a cleaner, more accountable government today.",
    cta_primary: { label: "Submit a Secure Report", url: "/report" },
    image: {
      src: "https://images.unsplash.com/photo-1584972208180-608020922485?w=800&q=80",
      alt: "Abstract representation of secure digital governance and justice"
    }
  };

  const logoCloudData = {
    label: "Integrated with Government Departments Across Kerala",
    logos: [
      { name: "Public Works Department (PWD)", src: "https://picsum.photos/seed/pwd/200/100" },
      { name: "Revenue Department", src: "https://picsum.photos/seed/revenue/200/100" },
      { name: "Local Self Government (LSGD)", src: "https://picsum.photos/seed/lsgd/200/100" },
      { name: "Motor Vehicles Department (MVD)", src: "https://picsum.photos/seed/mvd/200/100" },
      { name: "Kerala Police", src: "https://picsum.photos/seed/police/200/100" }
    ]
  };

  const featureData = {
    headline: "Predictive Vigilance: Stopping Scams Before They Start",
    items: [
      { icon: ShieldCheck, title: "End-to-End Anonymity", body: "Your identity is cryptographically protected. We ensure whistleblowers remain completely anonymous throughout the entire investigation process." },
      { icon: BrainCircuit, title: "AI Credibility Scoring", body: "Our advanced artificial intelligence analyzes submitted evidence to prioritize high-risk complaints and filter out malicious or false reports." },
      { icon: LinkIcon, title: "Blockchain Audit Trails", body: "Every action taken on your complaint is logged on an immutable blockchain ledger, ensuring no data can be tampered with or deleted by officials." },
      { icon: Activity, title: "Real-Time Tracking", body: "Monitor the exact status of your report with our transparent tracking dashboard. Know exactly which department and officer is handling your case." },
      { icon: Map, title: "Predictive Vigilance", body: "By analyzing patterns across 14 districts, our system identifies corruption hotspots and stops fraudulent contract allocations before they happen." },
      { icon: FileText, title: "Smart Evidence Upload", body: "Easily upload documents, audio recordings, and images. Our system automatically extracts text and metadata to build a stronger case file." }
    ]
  };

  const statsData = {
    items: [
      { value: "₹12.4Cr", label: "Public Funds Recovered", detail: "Directly traced and recovered through verified citizen reports." },
      { value: "30 Days", label: "Average Resolution Time", detail: "Down from 180 days using our AI-driven routing workflow." },
      { value: "100%", label: "Blockchain Verified", detail: "Immutable audit trails generated for every single complaint." },
      { value: "10,000+", label: "Citizens Protected", detail: "Whistleblowers kept completely anonymous and safe from retaliation." }
    ]
  };

  const testimonialData = {
    headline: "Real Impact: How Citizens Are Cleaning Up Kerala",
    items: [
      {
        quote: "I was asked for a bribe for my building permit. I reported it here anonymously, and within two weeks, the LSGD took strict action. I finally got my permit without paying a single rupee.",
        name: "Anonymous Citizen",
        role: "Resident of Kochi",
        avatar: "https://picsum.photos/seed/cit1/100/100"
      },
      {
        quote: "The blockchain audit trail gave me the confidence to report disproportionate assets in the RTO. Knowing that the records couldn't be altered by corrupt officials made all the difference.",
        name: "Whistleblower 402",
        role: "Thiruvananthapuram",
        avatar: "https://picsum.photos/seed/cit2/100/100"
      },
      {
        quote: "As a vigilance officer, the AI credibility scoring helps me prioritize genuine cases of service denial at village offices. It has improved our department's efficiency by over 50%.",
        name: "Rajesh K.",
        role: "Vigilance Officer",
        avatar: "https://picsum.photos/seed/cit3/100/100"
      }
    ]
  };

  const faqData = [
    {
      question: "How is my identity protected when I file a report?",
      answer: "We use zero-knowledge proof authentication and end-to-end encryption. Your personal details are stripped from the report before it reaches any human investigator. Only a cryptographic hash connects you to your case, allowing you to track it without revealing who you are."
    },
    {
      question: "What happens immediately after I submit a complaint?",
      answer: "Our AI engine instantly analyzes your submission, cross-references it with historical data, and assigns a credibility score. High-risk cases with strong evidence are immediately flagged and routed to the appropriate district vigilance officer for priority action."
    },
    {
      question: "Can corrupt officials delete or alter my complaint?",
      answer: "No. Every complaint, piece of evidence, and status update is recorded on an immutable blockchain ledger. Once data is entered into the C3MS system, it cannot be tampered with, deleted, or hidden by anyone, ensuring absolute transparency."
    },
    {
      question: "What kind of evidence should I upload?",
      answer: "You can upload documents (PDFs), images, audio recordings, and videos. Strong evidence includes official receipts, recorded conversations, photographs of disproportionate assets, or copies of denied applications. Our system automatically extracts text from images to build your case file."
    }
  ];

  const nextTestimonial = () => {
    setActiveTestimonial((prev) => (prev + 1) % testimonialData.items.length);
  };

  const prevTestimonial = () => {
    setActiveTestimonial((prev) => (prev - 1 + testimonialData.items.length) % testimonialData.items.length);
  };

  const toggleFaq = (index) => {
    setOpenFaqId(openFaqId === index ? null : index);
  };

  return (
    <div className="min-h-screen flex flex-col bg-background text-foreground font-body selection:bg-primary/30">
      
      {/* 1. NAVBAR SECTION */}
      <header className="sticky top-0 z-50 w-full border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex h-20 items-center justify-between">
            {/* Logo */}
            <div className="flex-shrink-0">
              <Link to="/" className="flex items-center gap-3 group">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary text-white shadow-lg shadow-primary/20 transition-transform group-hover:scale-105">
                  <navData.logo.icon className="h-6 w-6" strokeWidth={2.5} />
                </div>
                <span className="font-display text-2xl font-bold tracking-tight text-foreground">
                  {navData.logo.text.split(' ')[0]} <span className="text-primary">{navData.logo.text.split(' ')[1]}</span>
                </span>
              </Link>
            </div>

            {/* Desktop Nav */}
            <nav className="hidden md:flex items-center space-x-8">
              {navData.links.map((link, idx) => (
                <Link
                  key={idx}
                  to={link.url}
                  className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
                >
                  {link.label}
                </Link>
              ))}
            </nav>

            {/* Desktop CTA */}
            <div className="hidden md:flex items-center">
              <Link
                to={navData.cta.url}
                className="inline-flex items-center justify-center rounded-lg bg-primary px-6 py-2.5 text-sm font-semibold text-white shadow-md shadow-primary/20 transition-all hover:bg-primary/90 hover:-translate-y-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background"
              >
                {navData.cta.label}
              </Link>
            </div>

            {/* Mobile Menu Button */}
            <div className="flex md:hidden">
              <button
                onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
                className="inline-flex items-center justify-center rounded-md p-2 text-muted-foreground hover:bg-secondary hover:text-foreground focus:outline-none"
              >
                {isMobileMenuOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
              </button>
            </div>
          </div>
        </div>

        {/* Mobile Menu */}
        <div className={`md:hidden transition-all duration-300 ease-in-out overflow-hidden ${isMobileMenuOpen ? 'max-h-96 border-b border-border opacity-100' : 'max-h-0 opacity-0'}`}>
          <div className="space-y-1 px-4 pb-6 pt-2 bg-background">
            {navData.links.map((link, idx) => (
              <Link
                key={idx}
                to={link.url}
                className="block rounded-md px-3 py-3 text-base font-medium text-muted-foreground hover:bg-secondary hover:text-foreground"
              >
                {link.label}
              </Link>
            ))}
            <div className="pt-4">
              <Link
                to={navData.cta.url}
                className="flex w-full items-center justify-center rounded-lg bg-primary px-4 py-3 text-base font-semibold text-white shadow-sm hover:bg-primary/90"
              >
                {navData.cta.label}
              </Link>
            </div>
          </div>
        </div>
      </header>

      <main className="flex-1">
        
        {/* 2. HERO SECTION */}
        <section className="relative overflow-hidden border-b border-border bg-background pt-16 md:pt-24 lg:pt-32 pb-16 md:pb-24">
          {/* Background Glow */}
          <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full max-w-7xl h-full pointer-events-none">
            <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-primary/10 rounded-full blur-[100px]"></div>
            <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-blue-500/10 rounded-full blur-[100px]"></div>
          </div>

          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 relative z-10">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 lg:gap-8 items-center">
              <div className="max-w-2xl">
                <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-secondary border border-border mb-8">
                  <ShieldCheck className="w-4 h-4 text-primary" />
                  <span className="text-xs font-semibold text-foreground tracking-wide uppercase">Official Vigilance Portal</span>
                </div>
                
                <h1 className="font-display text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tight text-foreground mb-6 leading-[1.1]">
                  {heroData.headline.split('.')[0]}.<br />
                  <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary to-emerald-400">
                    {heroData.headline.split('.')[1]}.
                  </span><br />
                  {heroData.headline.split('.')[2]}.
                </h1>
                
                <p className="text-lg sm:text-xl text-muted-foreground mb-10 leading-relaxed max-w-xl">
                  {heroData.sub}
                </p>
                
                <div className="flex flex-col sm:flex-row gap-4">
                  <Link
                    to={heroData.cta_primary.url}
                    className="inline-flex items-center justify-center gap-2 rounded-xl bg-primary px-8 py-4 text-base font-semibold text-white shadow-lg shadow-primary/25 transition-all hover:bg-primary/90 hover:-translate-y-1"
                  >
                    <Shield className="w-5 h-5" />
                    {heroData.cta_primary.label}
                  </Link>
                  <Link
                    to="/explore"
                    className="inline-flex items-center justify-center gap-2 rounded-xl bg-secondary border border-border px-8 py-4 text-base font-semibold text-foreground transition-all hover:bg-secondary/80 hover:-translate-y-1"
                  >
                    Explore Directory
                    <ArrowRight className="w-5 h-5 text-muted-foreground" />
                  </Link>
                </div>
              </div>
              
              <div className="relative lg:ml-auto w-full max-w-lg lg:max-w-none mx-auto">
                <div className="relative rounded-2xl overflow-hidden border border-border shadow-2xl shadow-black/20 aspect-[4/3]">
                  <div className="absolute inset-0 bg-gradient-to-tr from-primary/20 to-transparent mix-blend-overlay z-10"></div>
                  <img 
                    src={heroData.image.src} 
                    alt={heroData.image.alt}
                    className="w-full h-full object-cover"
                  />
                  {/* Decorative UI Overlay */}
                  <div className="absolute bottom-6 left-6 right-6 z-20 bg-background/90 backdrop-blur-md border border-border rounded-xl p-4 shadow-lg flex items-center gap-4">
                    <div className="h-12 w-12 rounded-full bg-primary/20 flex items-center justify-center flex-shrink-0">
                      <Activity className="h-6 w-6 text-primary" />
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-foreground">System Status: Active</p>
                      <p className="text-xs text-muted-foreground">Monitoring 14 districts in real-time</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* 3. LOGO CLOUD SECTION */}
        <section className="py-12 border-b border-border bg-secondary/30">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
            <p className="text-center text-sm font-semibold uppercase tracking-widest text-muted-foreground mb-8">
              {logoCloudData.label}
            </p>
            <div className="flex flex-wrap justify-center gap-8 md:gap-16 items-center opacity-70 grayscale hover:grayscale-0 transition-all duration-500">
              {logoCloudData.logos.map((logo, idx) => (
                <div key={idx} className="flex flex-col items-center gap-2 group">
                  <img 
                    src={logo.src} 
                    alt={logo.name} 
                    className="h-12 object-contain rounded-md mix-blend-luminosity group-hover:mix-blend-normal transition-all"
                  />
                  <span className="text-xs font-medium text-muted-foreground group-hover:text-foreground transition-colors">{logo.name}</span>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* 4. FEATURE GRID SECTION */}
        <section className="py-24 bg-background relative">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
            <div className="text-center max-w-3xl mx-auto mb-16">
              <h2 className="font-display text-3xl md:text-4xl font-bold text-foreground mb-6 tracking-tight">
                {featureData.headline}
              </h2>
              <div className="h-1 w-20 bg-primary mx-auto rounded-full"></div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
              {featureData.items.map((feature, idx) => {
                const Icon = feature.icon;
                return (
                  <div 
                    key={idx} 
                    className="bg-card border border-border rounded-2xl p-8 shadow-sm hover:shadow-md hover:border-primary/30 transition-all duration-300 group"
                  >
                    <div className="h-14 w-14 rounded-xl bg-primary/10 flex items-center justify-center mb-6 group-hover:bg-primary group-hover:text-white transition-colors duration-300">
                      <Icon className="h-7 w-7 text-primary group-hover:text-white transition-colors" strokeWidth={2} />
                    </div>
                    <h3 className="font-display text-xl font-semibold text-foreground mb-3">
                      {feature.title}
                    </h3>
                    <p className="text-muted-foreground leading-relaxed text-sm md:text-base">
                      {feature.body}
                    </p>
                  </div>
                );
              })}
            </div>
          </div>
        </section>

        {/* 5. STATS BAND SECTION */}
        <section className="relative py-20 bg-slate-950 border-y border-slate-800 overflow-hidden">
          {/* Dark theme specific background */}
          <div className="absolute inset-0 bg-[linear-gradient(to_right,#4f4f4f2e_1px,transparent_1px),linear-gradient(to_bottom,#4f4f4f2e_1px,transparent_1px)] bg-[size:24px_24px] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_0%,#000_70%,transparent_100%)]"></div>
          
          <div className="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 z-10">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-10 lg:gap-8 divide-y sm:divide-y-0 sm:divide-x divide-slate-800">
              {statsData.items.map((stat, idx) => (
                <div key={idx} className="flex flex-col items-center text-center pt-8 sm:pt-0 px-4">
                  <dt className="order-2 mt-2 text-lg font-medium leading-6 text-slate-400 font-display">
                    {stat.label}
                  </dt>
                  <dd className="order-1 text-5xl font-bold tracking-tight text-white font-display mb-2 drop-shadow-md">
                    {stat.value}
                  </dd>
                  <p className="order-3 mt-3 text-sm text-slate-500 max-w-xs">
                    {stat.detail}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* 6. TESTIMONIAL CAROUSEL SECTION */}
        <section className="py-24 bg-secondary/30 border-b border-border">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
            <div className="text-center mb-16">
              <h2 className="font-display text-3xl md:text-4xl font-bold text-foreground mb-4 tracking-tight">
                {testimonialData.headline}
              </h2>
            </div>

            <div className="relative max-w-4xl mx-auto">
              <div className="overflow-hidden rounded-3xl bg-card border border-border shadow-xl">
                <div 
                  className="flex transition-transform duration-500 ease-in-out"
                  style={{ transform: `translateX(-${activeTestimonial * 100}%)` }}
                >
                  {testimonialData.items.map((item, idx) => (
                    <div key={idx} className="w-full flex-shrink-0 p-8 md:p-16 flex flex-col items-center text-center">
                      <Quote className="w-12 h-12 text-primary/40 mb-8" />
                      <blockquote className="text-xl md:text-2xl font-medium text-foreground leading-relaxed mb-10">
                        "{item.quote}"
                      </blockquote>
                      <div className="flex items-center gap-4 mt-auto">
                        <img 
                          src={item.avatar} 
                          alt={item.name} 
                          className="w-14 h-14 rounded-full border-2 border-primary/20 object-cover"
                        />
                        <div className="text-left">
                          <div className="font-display font-bold text-foreground text-lg">{item.name}</div>
                          <div className="text-sm text-muted-foreground">{item.role}</div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Carousel Controls */}
              <div className="flex justify-center items-center gap-6 mt-8">
                <button 
                  onClick={prevTestimonial}
                  className="p-3 rounded-full bg-card border border-border text-foreground hover:bg-secondary hover:text-primary transition-colors focus:outline-none focus:ring-2 focus:ring-primary"
                  aria-label="Previous testimonial"
                >
                  <ChevronLeft className="w-5 h-5" />
                </button>
                <div className="flex gap-2">
                  {testimonialData.items.map((_, idx) => (
                    <button
                      key={idx}
                      onClick={() => setActiveTestimonial(idx)}
                      className={`w-2.5 h-2.5 rounded-full transition-all ${activeTestimonial === idx ? 'bg-primary w-8' : 'bg-border hover:bg-primary/50'}`}
                      aria-label={`Go to testimonial ${idx + 1}`}
                    />
                  ))}
                </div>
                <button 
                  onClick={nextTestimonial}
                  className="p-3 rounded-full bg-card border border-border text-foreground hover:bg-secondary hover:text-primary transition-colors focus:outline-none focus:ring-2 focus:ring-primary"
                  aria-label="Next testimonial"
                >
                  <ChevronRight className="w-5 h-5" />
                </button>
              </div>
            </div>
          </div>
        </section>

        {/* 7. FAQ ACCORDION SECTION */}
        <section className="py-24 bg-background">
          <div className="mx-auto max-w-3xl px-4 sm:px-6 lg:px-8">
            <div className="text-center mb-12">
              <h2 className="font-display text-3xl md:text-4xl font-bold text-foreground mb-4 tracking-tight">
                Frequently Asked Questions
              </h2>
              <p className="text-lg text-muted-foreground">
                Everything you need to know about the Vigilance C3MS platform and how to report securely.
              </p>
            </div>

            <div className="space-y-4">
              {faqData.map((faq, idx) => {
                const isOpen = openFaqId === idx;
                return (
                  <div 
                    key={idx} 
                    className={`border rounded-xl overflow-hidden transition-all duration-200 ${isOpen ? 'bg-card border-primary/30 shadow-md' : 'bg-background border-border hover:border-border/80'}`}
                  >
                    <button
                      onClick={() => toggleFaq(idx)}
                      className="w-full px-6 py-5 flex items-center justify-between text-left focus:outline-none"
                      aria-expanded={isOpen}
                    >
                      <span className={`text-lg font-semibold font-display pr-8 ${isOpen ? 'text-primary' : 'text-foreground'}`}>
                        {faq.question}
                      </span>
                      <span className={`flex-shrink-0 transition-transform duration-200 ${isOpen ? 'text-primary rotate-180' : 'text-muted-foreground'}`}>
                        <ChevronDown className="w-5 h-5" />
                      </span>
                    </button>
                    <div 
                      className={`px-6 overflow-hidden transition-all duration-300 ease-in-out ${isOpen ? 'max-h-96 pb-6 opacity-100' : 'max-h-0 opacity-0'}`}
                    >
                      <p className="text-muted-foreground leading-relaxed">
                        {faq.answer}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </section>

      </main>

      {/* 8. FOOTER SECTION */}
      <footer className="bg-slate-950 text-slate-300 py-16 border-t border-slate-800 mt-auto">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-12 md:gap-8 mb-12">
            
            {/* Brand */}
            <div className="col-span-1 md:col-span-1">
              <Link to="/" className="flex items-center gap-2 text-white mb-6 group">
                <Shield className="h-8 w-8 text-primary group-hover:text-emerald-400 transition-colors" />
                <span className="font-display font-bold text-2xl tracking-tight">C3MS</span>
              </Link>
              <p className="text-sm text-slate-400 leading-relaxed mb-6">
                Empowering citizens to securely report, track, and combat corruption with AI-driven transparency and blockchain verification.
              </p>
              <div className="flex gap-4">
                <a href="#" className="p-2 rounded-full bg-slate-900 text-slate-400 hover:text-white hover:bg-primary transition-all">
                  <Twitter className="h-4 w-4" />
                </a>
                <a href="#" className="p-2 rounded-full bg-slate-900 text-slate-400 hover:text-white hover:bg-primary transition-all">
                  <Facebook className="h-4 w-4" />
                </a>
                <a href="#" className="p-2 rounded-full bg-slate-900 text-slate-400 hover:text-white hover:bg-primary transition-all">
                  <Mail className="h-4 w-4" />
                </a>
              </div>
            </div>

            {/* Links */}
            <div>
              <h3 className="font-display font-semibold text-white mb-6 tracking-wide text-sm uppercase">Platform</h3>
              <ul className="space-y-4">
                <li><Link to="/" className="text-sm text-slate-400 hover:text-primary transition-colors">Home</Link></li>
                <li><Link to="/explore" className="text-sm text-slate-400 hover:text-primary transition-colors">Public Directory</Link></li>
                <li><Link to="/report" className="text-sm text-slate-400 hover:text-primary transition-colors">File a Complaint</Link></li>
                <li><Link to="/dashboard" className="text-sm text-slate-400 hover:text-primary transition-colors">Investigator Portal</Link></li>
              </ul>
            </div>

            <div>
              <h3 className="font-display font-semibold text-white mb-6 tracking-wide text-sm uppercase">Information</h3>
              <ul className="space-y-4">
                <li><Link to="/about" className="text-sm text-slate-400 hover:text-primary transition-colors">About C3MS</Link></li>
                <li><Link to="/privacy" className="text-sm text-slate-400 hover:text-primary transition-colors">Privacy Policy</Link></li>
                <li><Link to="/terms" className="text-sm text-slate-400 hover:text-primary transition-colors">Terms of Service</Link></li>
                <li><Link to="/contact" className="text-sm text-slate-400 hover:text-primary transition-colors">Contact Support</Link></li>
              </ul>
            </div>

            {/* Newsletter / Contact */}
            <div>
              <h3 className="font-display font-semibold text-white mb-6 tracking-wide text-sm uppercase">Emergency Contact</h3>
              <div className="bg-slate-900 rounded-xl p-5 border border-slate-800">
                <p className="text-sm text-slate-400 mb-2">Toll-Free Vigilance Helpline:</p>
                <p className="text-xl font-display font-bold text-white mb-4">1064</p>
                <p className="text-xs text-slate-500">Available 24/7 for immediate assistance regarding bribery or corruption.</p>
              </div>
            </div>
          </div>

          <div className="pt-8 border-t border-slate-800 flex flex-col md:flex-row justify-between items-center gap-4">
            <p className="text-sm text-slate-500">
              &copy; {new Date().getFullYear()} Vigilance & Anti-Corruption Bureau, Government of Kerala. All rights reserved.
            </p>
            <div className="flex items-center gap-2 text-sm text-slate-500">
              <ShieldCheck className="w-4 h-4 text-primary" />
              Secured by C3MS Blockchain Infrastructure
            </div>
          </div>
        </div>
      </footer>

    </div>
  );
}
