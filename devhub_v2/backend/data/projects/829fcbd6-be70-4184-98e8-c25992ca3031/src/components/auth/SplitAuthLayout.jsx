import React from 'react';
import { ShieldCheck, Lock } from 'lucide-react';

export default function SplitAuthLayout({ children, title, subtitle }) {
  return (
    <div className="min-h-screen flex bg-background font-body text-foreground">
      {/* Left Side - Auth Form Container */}
      <div className="w-full lg:w-1/2 flex flex-col justify-center px-6 sm:px-12 lg:px-24 xl:px-32 relative">
        
        {/* Minimal Brand Header for Mobile/Form Side */}
        <div className="absolute top-8 left-6 sm:left-12 lg:left-24 flex items-center gap-2.5">
          <div className="bg-primary/10 p-2 rounded-lg">
            <ShieldCheck className="w-6 h-6 text-primary" />
          </div>
          <span className="font-display font-bold text-xl tracking-tight text-foreground">
            Vigilance C3MS
          </span>
        </div>

        {/* Form Content Area */}
        <div className="max-w-md w-full mx-auto mt-16 lg:mt-0">
          <div className="mb-8">
            <h1 className="font-display text-3xl sm:text-4xl font-bold mb-3 text-foreground tracking-tight">
              {title}
            </h1>
            <p className="text-muted-foreground text-base sm:text-lg leading-relaxed">
              {subtitle}
            </p>
          </div>
          
          {/* Injected Form (Login/Register) */}
          <div className="bg-card border border-border rounded-xl p-6 sm:p-8 shadow-sm">
            {children}
          </div>
          
          {/* Footer Links / Help */}
          <div className="mt-8 text-center text-sm text-muted-foreground">
            <p>
              Need help accessing your account? <br className="sm:hidden" />
              <a href="#" className="text-primary hover:underline font-medium transition-colors">
                Contact IT Support
              </a>
            </p>
          </div>
        </div>
      </div>

      {/* Right Side - Branded Hero & Trust Badges */}
      <div className="hidden lg:flex lg:w-1/2 relative bg-slate-900 overflow-hidden">
        {/* Background Image - Abstract Architecture/Governance Vibe */}
        <img
          src="https://images.unsplash.com/photo-1541872703-74c5e44368f9?q=80&w=2000&auto=format&fit=crop"
          alt="Secure Governance Architecture"
          className="absolute inset-0 w-full h-full object-cover opacity-30 mix-blend-luminosity"
        />
        
        {/* Gradient Overlay for Brand Colors */}
        <div className="absolute inset-0 bg-gradient-to-br from-primary/95 via-primary/80 to-slate-900/95" />

        {/* Content Container */}
        <div className="relative z-10 flex flex-col justify-center p-16 xl:p-24 text-white w-full h-full">
          
          <div className="mb-16">
            <h2 className="font-display text-4xl xl:text-5xl font-bold mb-6 leading-tight tracking-tight">
              Report Corruption.<br />
              <span className="text-emerald-200">Protect Kerala.</span>
            </h2>
            <p className="text-lg xl:text-xl text-emerald-50/80 max-w-lg font-light leading-relaxed">
              Join thousands of citizens using AI-powered transparency to build a better, corruption-free tomorrow. Your identity is safe. Your voice is heard.
            </p>
          </div>

          {/* Trust Badges - Glassmorphism Style */}
          <div className="space-y-5 max-w-lg">
            <div className="flex items-start gap-4 bg-white/10 p-5 rounded-2xl backdrop-blur-md border border-white/20 shadow-xl transition-transform hover:-translate-y-1 duration-300">
              <div className="bg-emerald-400/20 p-3 rounded-xl shrink-0">
                <ShieldCheck className="w-7 h-7 text-emerald-300" />
              </div>
              <div>
                <h3 className="font-display font-semibold text-lg text-white tracking-wide">
                  100% Anonymous Reporting
                </h3>
                <p className="text-emerald-50/70 text-sm mt-1.5 leading-relaxed">
                  Advanced cryptographic encryption ensures your identity is never revealed without your explicit consent.
                </p>
              </div>
            </div>

            <div className="flex items-start gap-4 bg-white/10 p-5 rounded-2xl backdrop-blur-md border border-white/20 shadow-xl transition-transform hover:-translate-y-1 duration-300">
              <div className="bg-emerald-400/20 p-3 rounded-xl shrink-0">
                <Lock className="w-7 h-7 text-emerald-300" />
              </div>
              <div>
                <h3 className="font-display font-semibold text-lg text-white tracking-wide">
                  Blockchain Verified Evidence
                </h3>
                <p className="text-emerald-50/70 text-sm mt-1.5 leading-relaxed">
                  Every piece of uploaded evidence is hashed and stored immutably on the ledger, preventing tampering.
                </p>
              </div>
            </div>
          </div>
          
          {/* Bottom decorative element */}
          <div className="absolute bottom-12 left-16 xl:left-24 flex items-center gap-3 opacity-60">
            <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-sm font-medium tracking-wider uppercase">Secure Connection Established</span>
          </div>
        </div>
      </div>
    </div>
  );
}