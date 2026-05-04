import { Link } from 'react-router-dom';
import { 
  ShieldAlert, 
  Search, 
  MessageSquare, 
  Smartphone, 
  Lock, 
  BrainCircuit,
  CheckCircle,
  Users,
  BarChart,
  Globe,
  FileText,
  Clock,
  ChevronRight,
  Star
} from 'lucide-react';

export default function Home() {
  return (
    <div className="space-y-16 pb-16">
      {/* Hero Section */}
      <section className="relative text-center py-20 px-4 sm:px-6 lg:px-8 bg-white rounded-3xl shadow-sm border border-gray-100 overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-b from-vacb-50 to-white opacity-50 pointer-events-none"></div>
        <div className="relative z-10">
          <ShieldAlert className="h-20 w-20 text-vacb-600 mx-auto mb-8 animate-pulse" />
          <h1 className="text-5xl font-extrabold text-gray-900 tracking-tight sm:text-6xl md:text-7xl mb-6">
            Zero Tolerance to <span className="text-vacb-600">Corruption</span>
          </h1>
          <p className="mt-6 max-w-3xl mx-auto text-xl md:text-2xl text-gray-500 leading-relaxed">
            Citizen-Centric Anti-Corruption Complaint Management System (C3MS). 
            Secure, anonymous, and AI-powered grievance redressal for a transparent future.
          </p>
          <div className="mt-10 flex flex-col sm:flex-row justify-center gap-4 sm:gap-6">
            <Link to="/submit" className="btn-primary text-lg px-10 py-4 rounded-xl shadow-lg hover:shadow-xl transform hover:-translate-y-1 transition-all flex items-center justify-center gap-2">
              File a Complaint <ChevronRight className="h-5 w-5" />
            </Link>
            <Link to="/track" className="btn-secondary text-lg px-10 py-4 rounded-xl shadow-sm hover:shadow-md transition-all flex items-center justify-center gap-2">
              Track Status <Search className="h-5 w-5" />
            </Link>
          </div>
          <div className="mt-12 flex items-center justify-center gap-8 text-sm text-gray-500 font-medium">
            <div className="flex items-center gap-2">
              <CheckCircle className="h-5 w-5 text-green-500" /> 100% Anonymous
            </div>
            <div className="flex items-center gap-2">
              <CheckCircle className="h-5 w-5 text-green-500" /> End-to-End Encrypted
            </div>
            <div className="flex items-center gap-2">
              <CheckCircle className="h-5 w-5 text-green-500" /> 24/7 Support
            </div>
          </div>
        </div>
      </section>

      {/* How It Works Section */}
      <section className="py-12">
        <div className="text-center mb-12">
          <h2 className="text-3xl font-bold text-gray-900 sm:text-4xl">How It Works</h2>
          <p className="mt-4 text-lg text-gray-600 max-w-2xl mx-auto">
            Our streamlined process ensures your voice is heard and acted upon swiftly, without compromising your identity.
          </p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8 relative">
          <div className="hidden md:block absolute top-1/2 left-0 w-full h-0.5 bg-gray-200 -z-10 transform -translate-y-1/2"></div>
          
          {[
            { icon: FileText, title: "1. Submit", desc: "File your complaint securely via web, app, or WhatsApp." },
            { icon: BrainCircuit, title: "2. AI Analysis", desc: "Our AI instantly categorizes and prioritizes the issue." },
            { icon: Users, title: "3. Investigation", desc: "Assigned to the right officer for thorough investigation." },
            { icon: CheckCircle, title: "4. Resolution", desc: "Track progress until the issue is fully resolved." }
          ].map((step, idx) => (
            <div key={idx} className="bg-white p-6 rounded-2xl shadow-sm border border-gray-100 text-center relative">
              <div className="mx-auto bg-vacb-100 w-16 h-16 rounded-full flex items-center justify-center mb-6 border-4 border-white shadow-sm">
                <step.icon className="h-8 w-8 text-vacb-600" />
              </div>
              <h3 className="text-xl font-bold mb-3 text-gray-900">{step.title}</h3>
              <p className="text-gray-600">{step.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Features Grid */}
      <section className="bg-gray-50 -mx-4 sm:-mx-6 lg:-mx-8 px-4 sm:px-6 lg:px-8 py-16 rounded-3xl">
        <div className="text-center mb-12">
          <h2 className="text-3xl font-bold text-gray-900 sm:text-4xl">System Capabilities</h2>
          <p className="mt-4 text-lg text-gray-600 max-w-2xl mx-auto">
            Powered by cutting-edge technology to ensure transparency, security, and efficiency.
          </p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
          <div className="bg-white p-8 rounded-2xl shadow-sm hover:shadow-md transition-shadow border border-gray-100">
            <div className="bg-blue-50 w-14 h-14 rounded-xl flex items-center justify-center mb-6">
              <Smartphone className="h-7 w-7 text-blue-600" />
            </div>
            <h3 className="text-xl font-bold mb-3 text-gray-900">Multi-Channel Intake</h3>
            <p className="text-gray-600 leading-relaxed">Submit complaints seamlessly via our Web Portal, Mobile Application, WhatsApp Chatbot, or Toll-Free IVR system (1800-XXX-XXXX).</p>
          </div>
          
          <div className="bg-white p-8 rounded-2xl shadow-sm hover:shadow-md transition-shadow border border-gray-100">
            <div className="bg-purple-50 w-14 h-14 rounded-xl flex items-center justify-center mb-6">
              <BrainCircuit className="h-7 w-7 text-purple-600" />
            </div>
            <h3 className="text-xl font-bold mb-3 text-gray-900">AI-Powered Triage</h3>
            <p className="text-gray-600 leading-relaxed">Our advanced NLP engine automatically reads, categorizes, prioritizes, and routes incoming complaints to the most appropriate investigating officer.</p>
          </div>

          <div className="bg-white p-8 rounded-2xl shadow-sm hover:shadow-md transition-shadow border border-gray-100">
            <div className="bg-green-50 w-14 h-14 rounded-xl flex items-center justify-center mb-6">
              <Lock className="h-7 w-7 text-green-600" />
            </div>
            <h3 className="text-xl font-bold mb-3 text-gray-900">Blockchain Secured</h3>
            <p className="text-gray-600 leading-relaxed">Immutable audit logs ensure complete transparency. End-to-end encryption guarantees that whistleblower identities remain strictly confidential.</p>
          </div>

          <div className="bg-white p-8 rounded-2xl shadow-sm hover:shadow-md transition-shadow border border-gray-100">
            <div className="bg-orange-50 w-14 h-14 rounded-xl flex items-center justify-center mb-6">
              <BarChart className="h-7 w-7 text-orange-600" />
            </div>
            <h3 className="text-xl font-bold mb-3 text-gray-900">Real-time Analytics</h3>
            <p className="text-gray-600 leading-relaxed">Comprehensive dashboards provide actionable insights, heatmaps, and trend analysis for department heads to monitor corruption hotspots.</p>
          </div>

          <div className="bg-white p-8 rounded-2xl shadow-sm hover:shadow-md transition-shadow border border-gray-100">
            <div className="bg-teal-50 w-14 h-14 rounded-xl flex items-center justify-center mb-6">
              <Globe className="h-7 w-7 text-teal-600" />
            </div>
            <h3 className="text-xl font-bold mb-3 text-gray-900">Multilingual Support</h3>
            <p className="text-gray-600 leading-relaxed">Full support for Malayalam, English, and Hindi. Our AI translates and processes complaints regardless of the language used by the citizen.</p>
          </div>

          <div className="bg-white p-8 rounded-2xl shadow-sm hover:shadow-md transition-shadow border border-gray-100">
            <div className="bg-rose-50 w-14 h-14 rounded-xl flex items-center justify-center mb-6">
              <Clock className="h-7 w-7 text-rose-600" />
            </div>
            <h3 className="text-xl font-bold mb-3 text-gray-900">SLA Monitoring</h3>
            <p className="text-gray-600 leading-relaxed">Automated escalation matrices ensure that no complaint sits idle. Strict 30-day resolution SLAs are enforced system-wide.</p>
          </div>
        </div>
      </section>

      {/* Statistics Section */}
      <section className="py-12">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
          {[
            { label: "Complaints Resolved", value: "12,450+" },
            { label: "Active Investigations", value: "843" },
            { label: "Average Resolution Time", value: "14 Days" },
            { label: "Citizen Satisfaction", value: "98%" }
          ].map((stat, idx) => (
            <div key={idx} className="bg-white p-6 rounded-2xl shadow-sm border border-gray-100 text-center">
              <div className="text-3xl md:text-4xl font-extrabold text-vacb-600 mb-2">{stat.value}</div>
              <div className="text-sm md:text-base text-gray-600 font-medium">{stat.label}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Testimonials / Impact */}
      <section className="py-12">
        <h2 className="text-3xl font-bold text-gray-900 text-center mb-12">Impact Stories</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {[
            { quote: "The anonymity provided by this system gave me the courage to report a major irregularity in my department. The response was swift and professional.", author: "Anonymous Whistleblower" },
            { quote: "Tracking my complaint was incredibly easy. I received SMS updates at every stage, and the issue was resolved within two weeks.", author: "Citizen, Trivandrum" },
            { quote: "As an investigating officer, the AI triage saves me hours of manual sorting. I can focus immediately on high-priority cases.", author: "Vigilance Officer" }
          ].map((testimonial, idx) => (
            <div key={idx} className="bg-vacb-50 p-8 rounded-2xl relative">
              <Star className="h-8 w-8 text-vacb-300 absolute top-6 right-6 opacity-50" />
              <p className="text-gray-700 italic mb-6 relative z-10">"{testimonial.quote}"</p>
              <div className="font-semibold text-gray-900">- {testimonial.author}</div>
            </div>
          ))}
        </div>
      </section>

      {/* FAQ Section */}
      <section className="py-12 max-w-4xl mx-auto">
        <h2 className="text-3xl font-bold text-gray-900 text-center mb-10">Frequently Asked Questions</h2>
        <div className="space-y-6">
          {[
            { q: "Is my identity really kept secret?", a: "Yes. If you choose to file anonymously, our system uses advanced encryption to strip all identifying metadata. Not even the investigating officers will know your identity." },
            { q: "What types of complaints can I file?", a: "You can report bribery, misuse of public funds, disproportionate assets, nepotism, and any other corrupt practices involving public servants or government departments." },
            { q: "How long does it take to resolve a complaint?", a: "Our strict Service Level Agreement (SLA) mandates a maximum resolution time of 30 days. However, many straightforward cases are resolved much faster." },
            { q: "Can I submit evidence like photos or audio?", a: "Absolutely. Our platform supports secure uploads of documents, images, audio recordings, and videos up to 50MB per file." }
          ].map((faq, idx) => (
            <div key={idx} className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
              <h4 className="text-lg font-bold text-gray-900 mb-2 flex items-start gap-3">
                <MessageSquare className="h-6 w-6 text-vacb-500 flex-shrink-0 mt-0.5" />
                {faq.q}
              </h4>
              <p className="text-gray-600 ml-9">{faq.a}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Quick Stats / Trust Banner */}
      <section className="bg-gradient-to-r from-vacb-900 to-vacb-800 rounded-3xl p-10 text-white flex flex-col md:flex-row items-center justify-between shadow-xl overflow-hidden relative">
        <div className="absolute -right-20 -top-20 opacity-10">
          <ShieldAlert className="h-64 w-64" />
        </div>
        <div className="mb-8 md:mb-0 relative z-10">
          <h3 className="text-3xl font-bold mb-2">Kerala State Data Centre Hosted</h3>
          <p className="text-vacb-100 text-lg">Fully compliant with IT Act 2000 & Data Protection Guidelines.</p>
          <div className="mt-6 flex gap-4">
            <span className="bg-white/20 px-4 py-2 rounded-full text-sm font-medium backdrop-blur-sm">ISO 27001 Certified</span>
            <span className="bg-white/20 px-4 py-2 rounded-full text-sm font-medium backdrop-blur-sm">GovCloud Infrastructure</span>
          </div>
        </div>
        <div className="flex gap-10 relative z-10">
          <div className="text-center bg-white/10 p-6 rounded-2xl backdrop-blur-sm border border-white/20">
            <div className="text-4xl font-extrabold mb-1">30 Days</div>
            <div className="text-vacb-100 font-medium">Max Resolution SLA</div>
          </div>
          <div className="text-center bg-white/10 p-6 rounded-2xl backdrop-blur-sm border border-white/20">
            <div className="text-4xl font-extrabold mb-1">100%</div>
            <div className="text-vacb-100 font-medium">Auditability</div>
          </div>
        </div>
      </section>
      
      {/* CTA Section */}
      <section className="text-center py-16">
        <h2 className="text-3xl font-bold text-gray-900 mb-6">Ready to make a difference?</h2>
        <p className="text-xl text-gray-600 mb-8 max-w-2xl mx-auto">Join thousands of citizens in building a corruption-free society. Your voice matters.</p>
        <Link to="/submit" className="inline-flex items-center justify-center gap-2 btn-primary text-xl px-12 py-5 rounded-full shadow-lg hover:shadow-xl transform hover:-translate-y-1 transition-all">
          Report an Incident Now <ChevronRight className="h-6 w-6" />
        </Link>
      </section>
    </div>
  );
}
