import { Bot, Link as LinkIcon, UserX } from 'lucide-react';

export default function FeatureCards() {
  const features = [
    {
      title: 'AI-Powered Analysis',
      description: 'Smart algorithms extract key details, assess credibility, and prioritize high-risk complaints automatically for faster resolution.',
      icon: Bot,
    },
    {
      title: 'Blockchain Audit Trail',
      description: 'Every action and evidence upload is logged on an immutable ledger, ensuring 100% transparency and preventing tampering.',
      icon: LinkIcon,
    },
    {
      title: 'Guaranteed Anonymity',
      description: 'Report corruption fearlessly. Your identity is cryptographically protected and never revealed to the investigated parties.',
      icon: UserX,
    }
  ];

  return (
    <section className="py-20 bg-slate-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-16">
          <h2 className="text-3xl md:text-4xl font-bold text-slate-900 mb-4 tracking-tight">
            Built for Transparency and Trust
          </h2>
          <p className="text-lg text-slate-600 max-w-2xl mx-auto">
            Our platform leverages cutting-edge technology to ensure every grievance is handled securely, fairly, and without prejudice.
          </p>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {features.map((feature, index) => {
            const Icon = feature.icon;
            return (
              <div 
                key={index} 
                className="bg-white border border-slate-200 rounded-lg p-8 shadow-sm hover:shadow-md hover:border-vacb-200 hover:-translate-y-1 transition-all duration-300 flex flex-col items-start group"
              >
                <div className="flex items-center justify-center w-14 h-14 rounded-xl bg-vacb-50 text-vacb-700 mb-6 group-hover:bg-vacb-600 group-hover:text-white transition-colors duration-300">
                  <Icon size={28} strokeWidth={2} />
                </div>
                <h3 className="text-xl font-semibold text-slate-900 mb-3">
                  {feature.title}
                </h3>
                <p className="text-slate-600 leading-relaxed">
                  {feature.description}
                </p>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}