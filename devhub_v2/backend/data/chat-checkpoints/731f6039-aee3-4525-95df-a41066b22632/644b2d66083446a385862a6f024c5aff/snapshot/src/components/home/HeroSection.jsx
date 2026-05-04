import { Link } from 'react-router-dom'
import { ArrowRight, Search } from 'lucide-react'

export default function HeroSection() {
  return (
    <section className="relative bg-[#F8FAFC] pt-16 pb-20 lg:pt-24 lg:pb-28 overflow-hidden">
      {/* Decorative background elements */}
      <div className="absolute inset-y-0 left-0 w-1/2 bg-white rounded-r-full opacity-40 blur-3xl pointer-events-none transform -translate-x-1/2"></div>
      <div className="absolute top-0 right-0 w-1/2 h-1/2 bg-blue-50 rounded-bl-full opacity-50 blur-3xl pointer-events-none transform translate-x-1/3 -translate-y-1/4"></div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 lg:gap-8 items-center">
          
          {/* Left Column: Content */}
          <div className="max-w-2xl">
            <div className="inline-flex items-center px-3 py-1 rounded-full bg-blue-100/80 text-blue-800 text-sm font-semibold tracking-wide mb-6 border border-blue-200">
              <span className="flex h-2 w-2 rounded-full bg-blue-600 mr-2 animate-pulse"></span>
              Citizen-Centric Anti-Corruption System
            </div>
            
            <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold text-[#0F172A] tracking-tight leading-[1.15] mb-6">
              Report Corruption <span className="text-transparent bg-clip-text bg-gradient-to-r from-[#047857] to-blue-500">Fearlessly.</span>
              <br />
              <span className="text-3xl sm:text-4xl lg:text-5xl text-slate-700 mt-2 block">AI-Powered Transparency.</span>
            </h1>
            
            <p className="text-lg sm:text-xl text-[#64748B] mb-8 leading-relaxed max-w-xl">
              Secure, anonymous, and immutable grievance redressal for a corruption-free Kerala. Your identity is protected by advanced encryption, and every step is tracked on a tamper-proof ledger.
            </p>
            
            <div className="flex flex-col sm:flex-row gap-4">
              <Link
                to="/file-complaint"
                className="inline-flex justify-center items-center px-6 py-3.5 border border-transparent text-base font-medium rounded-lg text-white bg-[#047857] hover:bg-blue-800 shadow-sm hover:shadow-md transition-all duration-200 group"
              >
                File a Complaint
                <ArrowRight className="ml-2 -mr-1 h-5 w-5 group-hover:translate-x-1 transition-transform" aria-hidden="true" />
              </Link>
              
              <Link
                to="/track"
                className="inline-flex justify-center items-center px-6 py-3.5 border border-slate-300 text-base font-medium rounded-lg text-[#0F172A] bg-white hover:bg-slate-50 shadow-sm hover:shadow transition-all duration-200"
              >
                <Search className="mr-2 -ml-1 h-5 w-5 text-slate-500" aria-hidden="true" />
                Track Status
              </Link>
            </div>

            <div className="mt-10 flex items-center gap-6 text-sm text-slate-500 font-medium">
              <div className="flex items-center gap-2">
                <svg className="h-5 w-5 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                </svg>
                100% Anonymous
              </div>
              <div className="flex items-center gap-2">
                <svg className="h-5 w-5 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
                AI-Assisted Processing
              </div>
            </div>
          </div>

          {/* Right Column: Image */}
          <div className="relative lg:ml-auto w-full max-w-lg lg:max-w-none">
            {/* Decorative offset border */}
            <div className="absolute -inset-4 border-2 border-blue-100 rounded-2xl transform translate-x-3 translate-y-3 -z-10 hidden sm:block"></div>
            
            <div className="relative rounded-2xl overflow-hidden shadow-2xl bg-white aspect-[4/3] sm:aspect-[16/10] lg:aspect-[4/5] xl:aspect-[3/4]">
              <img
                src="https://images.unsplash.com/photo-1589829085413-56de8ae18c73?auto=format&fit=crop&w=1200&q=80"
                alt="Scales of justice representing fairness and transparency"
                className="absolute inset-0 w-full h-full object-cover object-center"
              />
              
              {/* Overlays for depth and text readability if needed */}
              <div className="absolute inset-0 bg-gradient-to-tr from-slate-900/40 via-slate-900/10 to-transparent mix-blend-multiply"></div>
              
              {/* Subtle geometric pattern overlay */}
              <div className="absolute inset-0 opacity-20" style={{ backgroundImage: 'radial-gradient(#ffffff 1px, transparent 1px)', backgroundSize: '20px 20px' }}></div>
              
              {/* Floating stat card */}
              <div className="absolute bottom-6 left-6 right-6 sm:right-auto bg-white/95 backdrop-blur-sm p-4 rounded-xl shadow-lg border border-white/20">
                <div className="flex items-center gap-4">
                  <div className="flex-shrink-0 bg-blue-100 p-2.5 rounded-lg">
                    <svg className="h-6 w-6 text-blue-700" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-slate-500">Resolution Rate</p>
                    <p className="text-xl font-bold text-slate-900">98.4%</p>
                  </div>
                </div>
              </div>
            </div>
          </div>

        </div>
      </div>
    </section>
  )
}