import { Link } from 'react-router-dom'
import { ShieldCheck, ArrowRight, Lock, Activity, Database } from 'lucide-react'

export default function HeroSection() {
  return (
    <section className="relative w-full overflow-hidden bg-background pt-24 pb-20 md:pt-32 md:pb-32 lg:pt-40 lg:pb-40">
      {/* Abstract Geometric Background Image */}
      <div className="absolute inset-0 z-0">
        <img
          src="https://images.unsplash.com/photo-1550684848-fac1c5b4e853?q=80&w=2070&auto=format&fit=crop"
          alt="Abstract geometric background representing secure data"
          className="w-full h-full object-cover opacity-[0.15] mix-blend-luminosity"
        />
        {/* Gradient overlays to blend image into background color */}
        <div className="absolute inset-0 bg-gradient-to-b from-background/40 via-background/80 to-background"></div>
        <div className="absolute inset-0 bg-gradient-to-r from-background via-transparent to-background"></div>
      </div>

      {/* Main Content Container */}
      <div className="relative z-10 container mx-auto px-4 md:px-6 flex flex-col items-center text-center">
        
        {/* Eyebrow Badge */}
        <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-primary/10 border border-primary/20 mb-8 animate-fade-in-up">
          <ShieldCheck className="w-4 h-4 text-primary" />
          <span className="text-sm font-medium font-body text-primary tracking-wide uppercase">
            Official Vigilance Portal
          </span>
        </div>

        {/* Headline */}
        <h1 className="font-display text-5xl md:text-6xl lg:text-7xl font-bold tracking-tight text-foreground mb-6 max-w-4xl leading-[1.1]">
          Report Corruption. <br className="hidden md:block" />
          <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary to-emerald-400">
            Protect Kerala.
          </span>
        </h1>

        {/* Subheadline */}
        <p className="font-body text-lg md:text-xl text-muted-foreground max-w-2xl mb-10 leading-relaxed">
          Empowering citizens to securely report, track, and combat corruption with AI-driven transparency. Your identity is safe. Your voice is heard.
        </p>

        {/* Call to Action Buttons */}
        <div className="flex flex-col sm:flex-row items-center justify-center gap-4 w-full sm:w-auto mb-16">
          <Link
            to="/report"
            className="group inline-flex items-center justify-center gap-2 w-full sm:w-auto px-8 py-4 rounded-lg bg-primary text-white font-body font-semibold text-lg hover:bg-primary/90 transition-all duration-200 shadow-[0_0_20px_rgba(5,150,105,0.3)] hover:shadow-[0_0_25px_rgba(5,150,105,0.5)] hover:-translate-y-0.5"
          >
            <ShieldCheck className="w-5 h-5" />
            <span>File a Report</span>
          </Link>
          
          <Link
            to="/explore"
            className="group inline-flex items-center justify-center gap-2 w-full sm:w-auto px-8 py-4 rounded-lg bg-secondary text-foreground font-body font-semibold text-lg hover:bg-secondary/80 transition-all duration-200 border border-border hover:-translate-y-0.5"
          >
            <span>Explore Directory</span>
            <ArrowRight className="w-5 h-5 text-muted-foreground group-hover:text-foreground transition-colors" />
          </Link>
        </div>

        {/* Trust Indicators / Feature Highlights */}
        <div className="w-full max-w-4xl mx-auto pt-10 border-t border-border/50">
          <p className="text-sm text-muted-foreground font-body mb-6 uppercase tracking-widest font-semibold">
            Powered by Advanced Technology
          </p>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 text-center">
            <div className="flex flex-col items-center gap-2 p-4 rounded-xl bg-card/50 border border-border/50 backdrop-blur-sm">
              <div className="p-3 rounded-full bg-primary/10 text-primary mb-2">
                <Lock className="w-6 h-6" />
              </div>
              <h3 className="font-display font-semibold text-foreground">End-to-End Encryption</h3>
              <p className="text-sm text-muted-foreground font-body">Your identity and evidence remain strictly confidential.</p>
            </div>
            
            <div className="flex flex-col items-center gap-2 p-4 rounded-xl bg-card/50 border border-border/50 backdrop-blur-sm">
              <div className="p-3 rounded-full bg-blue-500/10 text-blue-500 mb-2">
                <Activity className="w-6 h-6" />
              </div>
              <h3 className="font-display font-semibold text-foreground">AI Credibility Check</h3>
              <p className="text-sm text-muted-foreground font-body">Automated analysis to prioritize high-risk complaints.</p>
            </div>
            
            <div className="flex flex-col items-center gap-2 p-4 rounded-xl bg-card/50 border border-border/50 backdrop-blur-sm">
              <div className="p-3 rounded-full bg-amber-500/10 text-amber-500 mb-2">
                <Database className="w-6 h-6" />
              </div>
              <h3 className="font-display font-semibold text-foreground">Blockchain Audit</h3>
              <p className="text-sm text-muted-foreground font-body">Immutable records ensure transparency and prevent tampering.</p>
            </div>
          </div>
        </div>

      </div>
    </section>
  )
}