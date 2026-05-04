import React from 'react';
import { BrainCircuit, Link as LinkIcon, UserX, Lock } from 'lucide-react';

export default function FeatureGrid() {
  const features = [
    {
      icon: BrainCircuit,
      title: "AI Credibility Scoring",
      description: "Advanced machine learning algorithms instantly analyze reports for credibility, prioritizing high-risk cases and filtering out noise to accelerate investigations.",
      colorClass: "text-emerald-600",
      bgClass: "bg-emerald-600/10"
    },
    {
      icon: LinkIcon,
      title: "Blockchain Audit Trails",
      description: "Every action, piece of evidence, and status update is immutably recorded on a secure blockchain ledger, ensuring zero tampering and absolute transparency.",
      colorClass: "text-blue-600",
      bgClass: "bg-blue-600/10"
    },
    {
      icon: UserX,
      title: "Guaranteed Anonymity",
      description: "Report corruption without fear of retaliation. Our system strips metadata and protects your identity through end-to-end encryption and secure routing.",
      colorClass: "text-amber-600",
      bgClass: "bg-amber-600/10"
    },
    {
      icon: Lock,
      title: "Bank-Grade Security",
      description: "Your data is protected by military-grade encryption protocols, ensuring that sensitive evidence and personal information remain strictly confidential at all times.",
      colorClass: "text-indigo-600",
      bgClass: "bg-indigo-600/10"
    }
  ];

  return (
    <section className="py-24 bg-background relative overflow-hidden">
      {/* Subtle background decoration */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full max-w-7xl h-full pointer-events-none">
        <div className="absolute top-20 left-10 w-72 h-72 bg-primary/5 rounded-full blur-3xl"></div>
        <div className="absolute bottom-20 right-10 w-96 h-96 bg-blue-500/5 rounded-full blur-3xl"></div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
        <div className="text-center max-w-3xl mx-auto mb-16">
          <span className="inline-block py-1 px-3 rounded-full bg-primary/10 text-primary font-body text-sm font-semibold tracking-wide uppercase mb-4">
            Core Capabilities
          </span>
          <h2 className="font-display text-3xl md:text-4xl lg:text-5xl font-bold text-foreground mb-6 leading-tight">
            Next-Generation Vigilance Technology
          </h2>
          <p className="font-body text-lg text-muted-foreground leading-relaxed">
            Empowering citizens and investigators with cutting-edge tools to ensure transparency, security, and swift justice across all government departments.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
          {features.map((feature, index) => (
            <div 
              key={index} 
              className="bg-card border border-border rounded-2xl p-8 shadow-sm hover:shadow-md transition-all duration-300 hover:-translate-y-1 group"
            >
              <div className={`h-14 w-14 rounded-xl flex items-center justify-center mb-6 transition-colors duration-300 ${feature.bgClass}`}>
                <feature.icon className={`h-7 w-7 ${feature.colorClass}`} strokeWidth={2} />
              </div>
              <h3 className="font-display text-xl font-semibold text-foreground mb-3 group-hover:text-primary transition-colors duration-300">
                {feature.title}
              </h3>
              <p className="font-body text-muted-foreground leading-relaxed text-sm md:text-base">
                {feature.description}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}