import React, { useState } from 'react';
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
  Star,
  AlertTriangle,
  FileWarning,
  PhoneCall,
  Mail,
  MapPin,
  X,
  Send,
  Bot,
  Newspaper,
  Download,
  ExternalLink,
  Info
} from 'lucide-react';

export default function Home() {
  const [isChatOpen, setIsChatOpen] = useState(false);

  return (
    <div className="min-h-screen bg-gray-50 font-sans">
      {/* Top Govt Banner */}
      <div className="bg-vacb-900 text-white py-1 px-4 text-xs sm:text-sm flex justify-between items-center border-b border-vacb-800">
        <div className="flex items-center gap-4">
          <span>കേരള സർക്കാർ | Government of Kerala</span>
          <span className="hidden sm:inline-block border-l border-vacb-700 pl-4">Vigilance & Anti-Corruption Bureau</span>
        </div>
        <div className="flex items-center gap-4">
          <a href="#main-content" className="hover:underline focus:ring-2 focus:ring-white">Skip to Main Content</a>
          <div className="flex gap-2">
            <button className="bg-vacb-800 px-2 py-0.5 rounded text-xs">A-</button>
            <button className="bg-vacb-800 px-2 py-0.5 rounded text-xs">A</button>
            <button className="bg-vacb-800 px-2 py-0.5 rounded text-xs">A+</button>
          </div>
          <div className="flex gap-2">
            <button className="w-4 h-4 bg-white border border-gray-400 rounded-sm" title="Light Theme"></button>
            <button className="w-4 h-4 bg-black border border-gray-400 rounded-sm" title="Dark Theme"></button>
          </div>
          <select className="bg-vacb-800 border-none text-xs rounded px-2 py-1">
            <option>English</option>
            <option>മലയാളം</option>
          </select>
        </div>
      </div>

      {/* Header / Logo Area */}
      <header className="bg-white shadow-sm border-b-4 border-vacb-600 py-4 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row justify-between items-center gap-4">
          <div className="flex items-center gap-4">
            <img src="https://upload.wikimedia.org/wikipedia/commons/thumb/5/5b/Emblem_of_Kerala.svg/120px-Emblem_of_Kerala.svg.png" alt="Kerala Govt Emblem" className="h-20 w-auto" onError={(e) => { e.target.onerror = null; e.target.src = 'https://via.placeholder.com/80x100?text=Emblem'; }} />
            <div>
              <h1 className="text-2xl md:text-3xl font-extrabold text-vacb-800 uppercase tracking-tight">
                Vigilance & Anti-Corruption Bureau
              </h1>
              <h2 className="text-lg md:text-xl font-bold text-red-700">
                വിജിലൻസ് ആൻഡ് ആന്റി കറപ്ഷൻ ബ്യൂറോ
              </h2>
              <p className="text-sm text-gray-600 font-medium mt-1">Citizen-Centric Anti-Corruption Complaint Management System (C3MS)</p>
            </div>
          </div>
          <div className="flex flex-col items-end gap-2 hidden lg:flex">
            <div className="flex items-center gap-2 text-vacb-700 font-bold">
              <PhoneCall className="h-5 w-5" /> Toll Free: 1064 / 8592900900
            </div>
            <div className="text-sm text-gray-500">Working Hours: 24x7 Control Room</div>
          </div>
        </div>
      </header>

      {/* Marquee News Ticker */}
      <div className="bg-red-700 text-white flex items-center">
        <div className="bg-red-900 px-4 py-2 font-bold whitespace-nowrap flex items-center gap-2 z-10 shadow-md">
          <AlertTriangle className="h-4 w-4 animate-pulse" /> LATEST UPDATES
        </div>
        <marquee className="py-2 text-sm font-medium" scrollamount="5">
          <span className="mx-4">🚨 New AI-powered complaint registration system launched by Hon'ble Chief Minister.</span>
          <span className="mx-4">|</span>
          <span className="mx-4">📢 Citizens can now track their complaints via WhatsApp. Send 'HI' to 8592900900.</span>
          <span className="mx-4">|</span>
          <span className="mx-4">⚠️ Vigilance Awareness Week 2024: "Say no to corruption; commit to the Nation".</span>
          <span className="mx-4">|</span>
          <span className="mx-4">അഴിമതി രഹിത കേരളം - പരാതികൾ ഓൺലൈനായി നൽകുക.</span>
        </marquee>
      </div>

      {/* Main Navigation (Cluttered Govt Style) */}
      <nav className="bg-vacb-700 text-white shadow-md sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <ul className="flex flex-wrap text-sm font-medium">
            <li><Link to="/" className="block px-4 py-3 hover:bg-vacb-600 border-r border-vacb-600">Home</Link></li>
            <li><a href="#" className="block px-4 py-3 hover:bg-vacb-600 border-r border-vacb-600">About Us</a></li>
            <li><a href="#" className="block px-4 py-3 hover:bg-vacb-600 border-r border-vacb-600">Organizational Chart</a></li>
            <li><a href="#" className="block px-4 py-3 hover:bg-vacb-600 border-r border-vacb-600">RTI Act</a></li>
            <li><a href="#" className="block px-4 py-3 hover:bg-vacb-600 border-r border-vacb-600">Circulars & Orders</a></li>
            <li><a href="#" className="block px-4 py-3 hover:bg-vacb-600 border-r border-vacb-600">Success Stories</a></li>
            <li><a href="#" className="block px-4 py-3 hover:bg-vacb-600 border-r border-vacb-600">Contact Us</a></li>
            <li><Link to="/login" className="block px-4 py-3 bg-red-600 hover:bg-red-700 font-bold">Officer Login</Link></li>
          </ul>
        </div>
      </nav>

      <main id="main-content" className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-8">
        
        {/* Top Section: Hero + Messages */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          
          {/* Left Sidebar: Quick Links */}
          <div className="lg:col-span-3 space-y-6">
            <div className="bg-white border border-gray-200 rounded-lg shadow-sm overflow-hidden">
              <div className="bg-vacb-800 text-white p-3 font-bold flex items-center gap-2">
                <FileWarning className="h-5 w-5" /> Online Services
              </div>
              <ul className="divide-y divide-gray-100 text-sm">
                <li>
                  <Link to="/submit" className="flex items-center gap-2 p-3 hover:bg-vacb-50 text-vacb-700 font-bold transition-colors">
                    <ChevronRight className="h-4 w-4 text-red-500" /> File a New Complaint (പരാതി നൽകുക)
                  </Link>
                </li>
                <li>
                  <Link to="/track" className="flex items-center gap-2 p-3 hover:bg-vacb-50 text-vacb-700 font-bold transition-colors">
                    <ChevronRight className="h-4 w-4 text-red-500" /> Track Complaint Status (തൽസ്ഥിതി)
                  </Link>
                </li>
                <li>
                  <a href="#" className="flex items-center gap-2 p-3 hover:bg-gray-50 text-gray-700 transition-colors">
                    <ChevronRight className="h-4 w-4 text-vacb-500" /> Upload Additional Evidence
                  </a>
                </li>
                <li>
                  <a href="#" className="flex items-center gap-2 p-3 hover:bg-gray-50 text-gray-700 transition-colors">
                    <ChevronRight className="h-4 w-4 text-vacb-500" /> Request Vigilance Clearance
                  </a>
                </li>
                <li>
                  <a href="#" className="flex items-center gap-2 p-3 hover:bg-gray-50 text-gray-700 transition-colors">
                    <ChevronRight className="h-4 w-4 text-vacb-500" /> Download Forms
                  </a>
                </li>
              </ul>
            </div>

            <div className="bg-white border border-gray-200 rounded-lg shadow-sm overflow-hidden">
              <div className="bg-vacb-800 text-white p-3 font-bold flex items-center gap-2">
                <Newspaper className="h-5 w-5" /> What's New
              </div>
              <div className="p-4 h-64 overflow-y-auto text-sm space-y-4">
                <div className="border-b border-gray-100 pb-2">
                  <span className="text-xs text-red-600 font-bold">15 Oct 2023</span>
                  <a href="#" className="block mt-1 text-vacb-700 hover:underline">Implementation of AI-based Triage System in VACB Headquarters.</a>
                  <img src="https://upload.wikimedia.org/wikipedia/commons/thumb/3/3b/New_blinking.gif/50px-New_blinking.gif" alt="New" className="h-3 inline ml-2" />
                </div>
                <div className="border-b border-gray-100 pb-2">
                  <span className="text-xs text-red-600 font-bold">02 Oct 2023</span>
                  <a href="#" className="block mt-1 text-vacb-700 hover:underline">Circular No. 14/2023: Guidelines for anonymous whistleblowers.</a>
                </div>
                <div className="border-b border-gray-100 pb-2">
                  <span className="text-xs text-red-600 font-bold">28 Sep 2023</span>
                  <a href="#" className="block mt-1 text-vacb-700 hover:underline">List of officers awarded Chief Minister's Police Medal for Meritorious Service.</a>
                </div>
                <div className="border-b border-gray-100 pb-2">
                  <span className="text-xs text-red-600 font-bold">10 Sep 2023</span>
                  <a href="#" className="block mt-1 text-vacb-700 hover:underline">Tender Notice: Procurement of advanced digital forensics equipment.</a>
                </div>
              </div>
              <div className="bg-gray-50 p-2 text-center border-t border-gray-200">
                <a href="#" className="text-xs text-vacb-700 font-bold hover:underline">View All News</a>
              </div>
            </div>
          </div>

          {/* Center: Hero Image & Main Actions */}
          <div className="lg:col-span-6 space-y-6">
            <div className="relative rounded-lg overflow-hidden shadow-md border border-gray-200 bg-white">
              <div className="h-64 sm:h-80 bg-gray-200 relative">
                <img 
                  src="https://images.unsplash.com/photo-1599940824399-b87987ceb72a?auto=format&fit=crop&q=80&w=1000" 
                  alt="Kerala Secretariat" 
                  className="w-full h-full object-cover"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-vacb-900/90 via-vacb-900/40 to-transparent flex flex-col justify-end p-6">
                  <h2 className="text-2xl sm:text-3xl font-bold text-white mb-2 drop-shadow-lg">
                    Zero Tolerance to Corruption
                  </h2>
                  <p className="text-vacb-100 text-sm sm:text-base drop-shadow-md">
                    Secure, anonymous, and AI-powered grievance redressal for a transparent Kerala.
                  </p>
                </div>
              </div>
              <div className="p-6 bg-white">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <Link to="/submit" className="flex flex-col items-center justify-center p-6 bg-gradient-to-br from-vacb-600 to-vacb-800 text-white rounded-xl shadow-md hover:shadow-lg transform hover:-translate-y-1 transition-all border-2 border-transparent hover:border-vacb-300 group">
                    <ShieldAlert className="h-10 w-10 mb-3 group-hover:scale-110 transition-transform" />
                    <span className="text-lg font-bold">File a Complaint</span>
                    <span className="text-xs text-vacb-200 mt-1">പരാതി നൽകുക</span>
                  </Link>
                  <Link to="/track" className="flex flex-col items-center justify-center p-6 bg-gradient-to-br from-gray-100 to-gray-200 text-vacb-800 rounded-xl shadow-md hover:shadow-lg transform hover:-translate-y-1 transition-all border-2 border-gray-300 hover:border-vacb-500 group">
                    <Search className="h-10 w-10 mb-3 text-vacb-600 group-hover:scale-110 transition-transform" />
                    <span className="text-lg font-bold">Track Status</span>
                    <span className="text-xs text-gray-500 mt-1">തൽസ്ഥിതി അറിയുക</span>
                  </Link>
                </div>
                
                <div className="mt-6 flex items-center justify-center gap-6 text-xs sm:text-sm text-gray-600 font-medium bg-vacb-50 p-3 rounded-lg border border-vacb-100">
                  <div className="flex items-center gap-1.5">
                    <CheckCircle className="h-4 w-4 text-green-600" /> 100% Anonymous
                  </div>
                  <div className="flex items-center gap-1.5">
                    <Lock className="h-4 w-4 text-green-600" /> End-to-End Encrypted
                  </div>
                  <div className="flex items-center gap-1.5">
                    <BrainCircuit className="h-4 w-4 text-vacb-600" /> AI-Powered Triage
                  </div>
                </div>
              </div>
            </div>

            {/* About Section */}
            <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
              <h3 className="text-xl font-bold text-vacb-800 mb-4 border-b-2 border-red-600 pb-2 inline-block">About C3MS</h3>
              <p className="text-gray-700 text-sm leading-relaxed text-justify">
                The Citizen-Centric Anti-Corruption Complaint Management System (C3MS) is a state-of-the-art platform developed for the Vigilance and Anti-Corruption Bureau, Government of Kerala. Leveraging advanced Artificial Intelligence, Natural Language Processing, and Blockchain technology, C3MS ensures that every grievance is securely recorded, intelligently categorized, and swiftly routed to the appropriate investigating officer.
              </p>
              <p className="text-gray-700 text-sm leading-relaxed text-justify mt-3">
                Citizens can report instances of bribery, disproportionate assets, and misuse of official position by public servants with complete anonymity. The system enforces strict Service Level Agreements (SLAs) to guarantee timely resolution.
              </p>
              <a href="#" className="text-vacb-600 text-sm font-bold mt-4 inline-flex items-center hover:underline">
                Read More <ChevronRight className="h-4 w-4" />
              </a>
            </div>
          </div>

          {/* Right Sidebar: Messages & Stats */}
          <div className="lg:col-span-3 space-y-6">
            {/* CM Message */}
            <div className="bg-white border border-gray-200 rounded-lg shadow-sm overflow-hidden text-center">
              <div className="bg-vacb-800 text-white p-2 font-bold text-sm">
                Chief Minister's Message
              </div>
              <div className="p-4">
                <img 
                  src="https://upload.wikimedia.org/wikipedia/commons/thumb/4/4b/Pinarayi_Vijayan_2023.jpg/220px-Pinarayi_Vijayan_2023.jpg" 
                  alt="Chief Minister" 
                  className="w-24 h-24 rounded-full mx-auto border-4 border-gray-100 shadow-sm object-cover"
                  onError={(e) => { e.target.onerror = null; e.target.src = 'https://via.placeholder.com/100?text=CM'; }}
                />
                <h4 className="font-bold text-gray-900 mt-3 text-sm">Shri. Pinarayi Vijayan</h4>
                <p className="text-xs text-gray-500 mb-3">Hon'ble Chief Minister of Kerala</p>
                <p className="text-xs text-gray-700 italic">"Our government is committed to a corruption-free Kerala. This AI-powered portal empowers citizens to report grievances fearlessly."</p>
                <a href="#" className="text-xs text-vacb-600 font-bold mt-2 inline-block hover:underline">Read Full Message</a>
              </div>
            </div>

            {/* Director Message */}
            <div className="bg-white border border-gray-200 rounded-lg shadow-sm overflow-hidden text-center">
              <div className="bg-vacb-800 text-white p-2 font-bold text-sm">
                Director's Message
              </div>
              <div className="p-4">
                <div className="w-24 h-24 rounded-full mx-auto border-4 border-gray-100 shadow-sm bg-gray-200 flex items-center justify-center">
                  <Users className="h-10 w-10 text-gray-400" />
                </div>
                <h4 className="font-bold text-gray-900 mt-3 text-sm">Director of Vigilance</h4>
                <p className="text-xs text-gray-500 mb-3">VACB, Kerala</p>
                <p className="text-xs text-gray-700 italic">"Technology is our strongest ally in the fight against corruption. C3MS ensures transparency and accountability at every step."</p>
              </div>
            </div>

            {/* Live Stats */}
            <div className="bg-white border border-gray-200 rounded-lg shadow-sm overflow-hidden">
              <div className="bg-vacb-800 text-white p-2 font-bold text-sm flex items-center gap-2">
                <BarChart className="h-4 w-4" /> Live Statistics
              </div>
              <div className="p-4 space-y-3">
                <div className="flex justify-between items-center border-b border-gray-100 pb-2">
                  <span className="text-xs text-gray-600 font-medium">Complaints Received (2023)</span>
                  <span className="text-sm font-bold text-vacb-700">14,592</span>
                </div>
                <div className="flex justify-between items-center border-b border-gray-100 pb-2">
                  <span className="text-xs text-gray-600 font-medium">Cases Resolved</span>
                  <span className="text-sm font-bold text-green-600">12,840</span>
                </div>
                <div className="flex justify-between items-center border-b border-gray-100 pb-2">
                  <span className="text-xs text-gray-600 font-medium">Active Investigations</span>
                  <span className="text-sm font-bold text-orange-500">1,752</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-xs text-gray-600 font-medium">Avg. Resolution Time</span>
                  <span className="text-sm font-bold text-vacb-700">18 Days</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Features Grid (Govt Style) */}
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200 mt-8">
          <h3 className="text-xl font-bold text-vacb-800 mb-6 border-b-2 border-red-600 pb-2 inline-block">System Features</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <div className="flex flex-col items-center text-center p-4 border border-gray-100 rounded-lg hover:bg-vacb-50 transition-colors">
              <div className="bg-vacb-100 p-3 rounded-full mb-3">
                <Smartphone className="h-8 w-8 text-vacb-700" />
              </div>
              <h4 className="font-bold text-gray-900 text-sm mb-2">Multi-Channel Intake</h4>
              <p className="text-xs text-gray-600">Submit via Web, Mobile App, WhatsApp, or Toll-Free IVR.</p>
            </div>
            <div className="flex flex-col items-center text-center p-4 border border-gray-100 rounded-lg hover:bg-vacb-50 transition-colors">
              <div className="bg-vacb-100 p-3 rounded-full mb-3">
                <BrainCircuit className="h-8 w-8 text-vacb-700" />
              </div>
              <h4 className="font-bold text-gray-900 text-sm mb-2">AI-Powered Triage</h4>
              <p className="text-xs text-gray-600">NLP engine automatically categorizes and prioritizes complaints.</p>
            </div>
            <div className="flex flex-col items-center text-center p-4 border border-gray-100 rounded-lg hover:bg-vacb-50 transition-colors">
              <div className="bg-vacb-100 p-3 rounded-full mb-3">
                <Lock className="h-8 w-8 text-vacb-700" />
              </div>
              <h4 className="font-bold text-gray-900 text-sm mb-2">Blockchain Secured</h4>
              <p className="text-xs text-gray-600">Immutable audit logs and end-to-end encryption for anonymity.</p>
            </div>
            <div className="flex flex-col items-center text-center p-4 border border-gray-100 rounded-lg hover:bg-vacb-50 transition-colors">
              <div className="bg-vacb-100 p-3 rounded-full mb-3">
                <Globe className="h-8 w-8 text-vacb-700" />
              </div>
              <h4 className="font-bold text-gray-900 text-sm mb-2">Multilingual Support</h4>
              <p className="text-xs text-gray-600">Full support for Malayalam, English, and Hindi processing.</p>
            </div>
          </div>
        </div>

        {/* Important Links & Downloads */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-8">
          <div className="bg-white border border-gray-200 rounded-lg shadow-sm overflow-hidden">
            <div className="bg-vacb-800 text-white p-3 font-bold flex items-center gap-2">
              <Download className="h-5 w-5" /> Downloads & Forms
            </div>
            <ul className="divide-y divide-gray-100 text-sm p-2">
              <li><a href="#" className="flex items-center gap-2 p-2 hover:bg-gray-50 text-vacb-700"><FileText className="h-4 w-4 text-red-500" /> Complaint Registration Form (Offline) PDF</a></li>
              <li><a href="#" className="flex items-center gap-2 p-2 hover:bg-gray-50 text-vacb-700"><FileText className="h-4 w-4 text-red-500" /> Vigilance Manual 2023</a></li>
              <li><a href="#" className="flex items-center gap-2 p-2 hover:bg-gray-50 text-vacb-700"><FileText className="h-4 w-4 text-red-500" /> Guidelines for Whistleblowers</a></li>
              <li><a href="#" className="flex items-center gap-2 p-2 hover:bg-gray-50 text-vacb-700"><FileText className="h-4 w-4 text-red-500" /> Annual Report 2022-23</a></li>
            </ul>
          </div>
          <div className="bg-white border border-gray-200 rounded-lg shadow-sm overflow-hidden">
            <div className="bg-vacb-800 text-white p-3 font-bold flex items-center gap-2">
              <ExternalLink className="h-5 w-5" /> Related Websites
            </div>
            <ul className="divide-y divide-gray-100 text-sm p-2 grid grid-cols-2 gap-2">
              <li><a href="#" className="flex items-center gap-2 p-2 hover:bg-gray-50 text-vacb-700">Kerala Government</a></li>
              <li><a href="#" className="flex items-center gap-2 p-2 hover:bg-gray-50 text-vacb-700">Kerala Police</a></li>
              <li><a href="#" className="flex items-center gap-2 p-2 hover:bg-gray-50 text-vacb-700">CBI India</a></li>
              <li><a href="#" className="flex items-center gap-2 p-2 hover:bg-gray-50 text-vacb-700">CVC India</a></li>
              <li><a href="#" className="flex items-center gap-2 p-2 hover:bg-gray-50 text-vacb-700">Kerala High Court</a></li>
              <li><a href="#" className="flex items-center gap-2 p-2 hover:bg-gray-50 text-vacb-700">Information Commission</a></li>
            </ul>
          </div>
        </div>

      </main>

      {/* Footer */}
      <footer className="bg-vacb-900 text-white mt-12 border-t-4 border-red-600">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
            <div className="col-span-1 md:col-span-2">
              <div className="flex items-center gap-3 mb-4">
                <img src="https://upload.wikimedia.org/wikipedia/commons/thumb/5/5b/Emblem_of_Kerala.svg/120px-Emblem_of_Kerala.svg.png" alt="Emblem" className="h-12 w-auto grayscale brightness-200" onError={(e) => { e.target.onerror = null; e.target.style.display = 'none'; }} />
                <div>
                  <h3 className="text-lg font-bold">Vigilance & Anti-Corruption Bureau</h3>
                  <p className="text-sm text-vacb-200">Government of Kerala</p>
                </div>
              </div>
              <p className="text-xs text-vacb-200 leading-relaxed max-w-md">
                C3MS is a secure platform for citizens to report corruption. Hosted at Kerala State Data Centre. Compliant with IT Act 2000 & Data Protection Guidelines.
              </p>
              <div className="mt-4 flex gap-2">
                <span className="bg-vacb-800 px-2 py-1 rounded text-xs border border-vacb-700">ISO 27001:2013</span>
                <span className="bg-vacb-800 px-2 py-1 rounded text-xs border border-vacb-700">W3C WCAG 2.0</span>
              </div>
            </div>
            
            <div>
              <h4 className="text-sm font-bold mb-4 uppercase tracking-wider border-b border-vacb-700 pb-2">Contact Us</h4>
              <ul className="space-y-3 text-sm text-vacb-200">
                <li className="flex items-start gap-2">
                  <MapPin className="h-4 w-4 mt-0.5 flex-shrink-0" />
                  <span>VACB Directorate, PMG, Vikas Bhavan P.O, Thiruvananthapuram - 695033</span>
                </li>
                <li className="flex items-center gap-2">
                  <PhoneCall className="h-4 w-4 flex-shrink-0" />
                  <span>1064 (Toll Free) / 0471-2305060</span>
                </li>
                <li className="flex items-center gap-2">
                  <Mail className="h-4 w-4 flex-shrink-0" />
                  <span>director.vacb@kerala.gov.in</span>
                </li>
              </ul>
            </div>

            <div>
              <h4 className="text-sm font-bold mb-4 uppercase tracking-wider border-b border-vacb-700 pb-2">Policies</h4>
              <ul className="space-y-2 text-sm text-vacb-200">
                <li><a href="#" className="hover:text-white hover:underline">Privacy Policy</a></li>
                <li><a href="#" className="hover:text-white hover:underline">Terms of Use</a></li>
                <li><a href="#" className="hover:text-white hover:underline">Copyright Policy</a></li>
                <li><a href="#" className="hover:text-white hover:underline">Hyperlinking Policy</a></li>
                <li><a href="#" className="hover:text-white hover:underline">Accessibility Statement</a></li>
                <li><a href="#" className="hover:text-white hover:underline">Help</a></li>
              </ul>
            </div>
          </div>
        </div>
        <div className="bg-black py-4 text-center text-xs text-gray-400">
          <p>Content Owned, Maintained and Updated by Vigilance & Anti-Corruption Bureau, Government of Kerala.</p>
          <p className="mt-1">Designed & Developed by National Informatics Centre (NIC) / Kerala State IT Mission.</p>
          <p className="mt-2">Last Updated: {new Date().toLocaleDateString('en-IN')}</p>
        </div>
      </footer>

      {/* Dummy Chatbot Bubble */}
      <div className="fixed bottom-6 right-6 z-50">
        {isChatOpen ? (
          <div className="bg-white w-80 rounded-lg shadow-2xl border border-gray-200 overflow-hidden flex flex-col h-96 animate-in slide-in-from-bottom-5">
            <div className="bg-vacb-700 text-white p-3 flex justify-between items-center">
              <div className="flex items-center gap-2">
                <Bot className="h-5 w-5" />
                <span className="font-bold text-sm">VACB Sahayi (സഹായി)</span>
              </div>
              <button onClick={() => setIsChatOpen(false)} className="text-white hover:text-gray-200 focus:outline-none">
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="flex-1 p-4 overflow-y-auto bg-gray-50 space-y-4 text-sm">
              <div className="flex gap-2">
                <div className="bg-vacb-100 p-2 rounded-lg rounded-tl-none text-gray-800 max-w-[85%]">
                  Namaskaram! Welcome to VACB Kerala. How can I help you today? (നമസ്കാരം! ഞാൻ എങ്ങനെ സഹായിക്കണം?)
                </div>
              </div>
              <div className="flex gap-2">
                <div className="bg-vacb-100 p-2 rounded-lg rounded-tl-none text-gray-800 max-w-[85%]">
                  You can ask me about:
                  <ul className="list-disc ml-4 mt-1 space-y-1 text-xs">
                    <li>How to file a complaint</li>
                    <li>Track existing complaint</li>
                    <li>Contact details</li>
                  </ul>
                </div>
              </div>
            </div>
            <div className="p-3 bg-white border-t border-gray-200 flex gap-2">
              <input 
                type="text" 
                placeholder="Type your message..." 
                className="flex-1 border border-gray-300 rounded-full px-3 py-1.5 text-sm focus:outline-none focus:border-vacb-500 focus:ring-1 focus:ring-vacb-500"
              />
              <button className="bg-vacb-600 text-white p-1.5 rounded-full hover:bg-vacb-700 transition-colors">
                <Send className="h-4 w-4 m-0.5" />
              </button>
            </div>
          </div>
        ) : (
          <button 
            onClick={() => setIsChatOpen(true)}
            className="bg-vacb-600 text-white p-4 rounded-full shadow-lg hover:bg-vacb-700 hover:scale-105 transition-all flex items-center justify-center group relative"
          >
            <MessageSquare className="h-6 w-6" />
            <span className="absolute -top-10 right-0 bg-white text-vacb-800 text-xs font-bold px-3 py-1.5 rounded shadow-md border border-gray-200 whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity">
              Chat with us!
            </span>
            <span className="absolute -top-2 -right-2 bg-red-500 text-white text-[10px] font-bold h-5 w-5 rounded-full flex items-center justify-center border-2 border-white animate-bounce">
              1
            </span>
          </button>
        )}
      </div>
    </div>
  );
}
