import React from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, Shield, Clock, Video, Star } from 'lucide-react'
import AppShell from '../components/layout/AppShell'
import Button from '../components/ui/Button'
import DoctorCard from '../components/domain/DoctorCard'
import { doctors, specialties, testimonials } from '../mockData'

export default function LandingPage() {
  const [activeTestimonial, setActiveTestimonial] = React.useState(0);

  const safeTestimonials = testimonials?.length > 0 ? testimonials : [
    { 
      id: 1, 
      author: "Sarah Jenkins", 
      rating: 5, 
      text: "The AI summary after my visit was incredibly detailed. I finally understand my treatment plan and feel in control of my health." 
    },
    { 
      id: 2, 
      author: "Michael Chen", 
      rating: 5, 
      text: "Dr. Chen was attentive and the video quality was perfect. Highly recommend Omnia for anyone with a busy schedule." 
    },
    { 
      id: 3, 
      author: "Emma Thompson", 
      rating: 4.8, 
      text: "Booking was a breeze. I saw a specialist within 2 hours of feeling sick. The prescription was sent straight to my pharmacy." 
    }
  ];

  React.useEffect(() => {
    const interval = setInterval(() => {
      setActiveTestimonial((prev) => (prev + 1) % safeTestimonials.length);
    }, 6000);
    return () => clearInterval(interval);
  }, [safeTestimonials.length]);

  return (
    <AppShell>
      {/* Hero Section */}
      <section className="relative bg-white overflow-hidden">
        <div className="absolute inset-0 bg-[url('https://images.unsplash.com/photo-1550831107-1553da8c8464?auto=format&fit=crop&w=2000&q=10')] bg-cover bg-center opacity-[0.03] pointer-events-none"></div>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-20 pb-24 lg:pt-32 lg:pb-36 relative z-10">
          <div className="lg:grid lg:grid-cols-12 lg:gap-16 items-center">
            <div className="lg:col-span-6 text-center lg:text-left">
              <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-sky-50 text-sky-700 text-sm font-semibold mb-8 border border-sky-100 shadow-sm">
                <Star className="w-4 h-4 fill-sky-600" />
                <span>98% Patient Satisfaction</span>
              </div>
              <h1 className="text-4xl sm:text-5xl lg:text-6xl font-display font-bold text-slate-900 tracking-tight mb-6 leading-[1.1]">
                Intelligent care, <br className="hidden lg:block" />
                <span className="text-sky-600">anywhere.</span>
              </h1>
              <p className="text-lg text-slate-600 mb-8 max-w-2xl mx-auto lg:mx-0 font-body leading-relaxed">
                Meet your AI health assistant. Connect with top-rated board-certified specialists in minutes. Your health journey, simplified and secure.
              </p>
              <div className="flex flex-col sm:flex-row items-center justify-center lg:justify-start gap-4">
                <Link to="/doctors" className="w-full sm:w-auto">
                  <Button size="lg" className="w-full group text-base px-8">
                    Find a Doctor
                    <ArrowRight className="w-4 h-4 ml-2 group-hover:translate-x-1 transition-transform" />
                  </Button>
                </Link>
                <div className="flex items-center gap-3 text-sm text-slate-600 font-medium px-4 py-2 bg-slate-50 rounded-lg border border-slate-100">
                  <Clock className="w-4 h-4 text-emerald-500" />
                  Under 10 min wait
                </div>
              </div>
            </div>
            <div className="lg:col-span-6 mt-16 lg:mt-0 relative">
              <div className="relative rounded-[2rem] overflow-hidden shadow-2xl aspect-[4/3] lg:aspect-square border-8 border-white bg-slate-100">
                <img 
                  src="https://images.unsplash.com/photo-1576091160550-2173ff9e5ee5?auto=format&fit=crop&w=1000&q=80" 
                  alt="Doctor consulting with patient virtually" 
                  className="object-cover w-full h-full"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-slate-900/30 to-transparent"></div>
              </div>
              {/* Floating Trust Badge */}
              <div className="absolute -bottom-6 -left-6 bg-white p-4 rounded-2xl shadow-xl border border-slate-100 flex items-center gap-4 z-20">
                <div className="w-12 h-12 bg-emerald-50 rounded-full flex items-center justify-center text-emerald-600 shrink-0">
                  <Shield className="w-6 h-6" />
                </div>
                <div>
                  <p className="text-sm font-bold text-slate-900 font-display">HIPAA Compliant</p>
                  <p className="text-xs text-slate-500 font-medium">100% Secure Platform</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Specialty Grid */}
      <section className="py-24 bg-slate-50 border-y border-slate-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-3xl mx-auto mb-16">
            <h2 className="text-3xl md:text-4xl font-display font-bold text-slate-900 mb-4">Specialized care for your needs</h2>
            <p className="text-slate-600 text-lg">Choose from over 500+ board-certified doctors across various medical specialties.</p>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4 md:gap-6">
            {(specialties || []).slice(0, 10).map(spec => (
              <Link 
                key={spec.id} 
                to={`/doctors?specialty=${spec.id}`} 
                className="bg-white p-6 rounded-2xl border border-slate-200 hover:border-sky-300 hover:shadow-md transition-all duration-300 group text-center flex flex-col items-center"
              >
                <div className="w-14 h-14 bg-sky-50 rounded-2xl flex items-center justify-center text-sky-600 mb-5 group-hover:scale-110 group-hover:bg-sky-100 transition-all duration-300">
                  <span className="text-2xl font-display font-bold">{spec.name.charAt(0)}</span>
                </div>
                <h3 className="font-semibold text-slate-900 mb-1.5 font-display">{spec.name}</h3>
                <p className="text-sm text-slate-500 font-medium">{spec.doctor_count} Doctors</p>
              </Link>
            ))}
          </div>
        </div>
      </section>

      {/* How It Works */}
      <section className="py-24 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-20">
            <h2 className="text-3xl md:text-4xl font-display font-bold text-slate-900 mb-4">How Omnia Works</h2>
            <p className="text-slate-600 text-lg max-w-2xl mx-auto">Get the care you need in four simple steps, powered by intelligent matching.</p>
          </div>
          <div className="grid md:grid-cols-4 gap-12 relative">
            {/* Connecting line for desktop */}
            <div className="hidden md:block absolute top-10 left-[12%] right-[12%] h-0.5 bg-slate-100 z-0"></div>
            
            {[
              { icon: Shield, title: "Describe Symptoms", desc: "Securely share your health concerns with our AI triage." },
              { icon: Star, title: "Smart Match", desc: "Get matched with the right specialist instantly." },
              { icon: Clock, title: "Book a Time", desc: "Choose a convenient slot, often available today." },
              { icon: Video, title: "Virtual Visit", desc: "Connect via high-quality, secure video call." }
            ].map((step, idx) => (
              <div key={idx} className="relative z-10 flex flex-col items-center text-center group">
                <div className="w-20 h-20 bg-white border-8 border-slate-50 rounded-full flex items-center justify-center text-sky-600 shadow-sm mb-6 group-hover:border-sky-50 group-hover:scale-105 transition-all duration-300">
                  <step.icon className="w-8 h-8" strokeWidth={2} />
                </div>
                <h3 className="text-xl font-display font-bold text-slate-900 mb-3">{step.title}</h3>
                <p className="text-base text-slate-600 leading-relaxed">{step.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Featured Doctors */}
      <section className="py-24 bg-slate-50 border-t border-slate-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col md:flex-row md:items-end justify-between mb-12 gap-6">
            <div className="max-w-2xl">
              <h2 className="text-3xl md:text-4xl font-display font-bold text-slate-900 mb-4">Top-rated specialists</h2>
              <p className="text-slate-600 text-lg">Book an appointment with our most highly recommended and experienced doctors.</p>
            </div>
            <Link to="/doctors" className="shrink-0">
              <Button variant="outline" className="group bg-white">
                View All Doctors
                <ArrowRight className="w-4 h-4 ml-2 group-hover:translate-x-1 transition-transform" />
              </Button>
            </Link>
          </div>
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
            {(doctors || []).slice(0, 3).map(doctor => (
              <DoctorCard key={doctor.id} doctor={doctor} />
            ))}
          </div>
        </div>
      </section>

      {/* Testimonial Carousel */}
      <section className="py-24 bg-white overflow-hidden">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-4xl font-display font-bold text-slate-900 mb-4">Patient Stories</h2>
            <p className="text-slate-600 text-lg">Don't just take our word for it. Hear from our community.</p>
          </div>
          
          <div className="relative max-w-4xl mx-auto">
            <div className="overflow-hidden rounded-3xl bg-slate-50 border border-slate-100">
              <div 
                className="flex transition-transform duration-700 ease-in-out"
                style={{ transform: `translateX(-${activeTestimonial * 100}%)` }}
              >
                {safeTestimonials.map((t, idx) => (
                  <div key={t.id || idx} className="w-full flex-shrink-0 px-6 py-12 md:p-16 text-center">
                    <div className="flex justify-center gap-1.5 mb-8">
                      {[...Array(5)].map((_, i) => (
                        <Star 
                          key={i} 
                          className={`w-6 h-6 ${i < Math.floor(t.rating || 5) ? 'text-amber-400 fill-amber-400' : 'text-slate-200 fill-slate-200'}`} 
                        />
                      ))}
                    </div>
                    <p className="text-xl md:text-3xl font-display font-medium text-slate-900 mb-10 leading-relaxed">
                      "{t.text}"
                    </p>
                    <div>
                      <p className="font-bold text-slate-900 text-lg">{t.author}</p>
                      <p className="text-sm text-slate-500 font-medium mt-1">{t.role || 'Verified Patient'}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
            
            <div className="flex justify-center gap-3 mt-8">
              {safeTestimonials.map((_, idx) => (
                <button
                  key={idx}
                  onClick={() => setActiveTestimonial(idx)}
                  className={`w-3 h-3 rounded-full transition-all duration-300 ${
                    idx === activeTestimonial 
                      ? 'bg-sky-600 w-8' 
                      : 'bg-slate-300 hover:bg-slate-400'
                  }`}
                  aria-label={`Go to testimonial ${idx + 1}`}
                />
              ))}
            </div>
          </div>
        </div>
      </section>
    </AppShell>
  );
}