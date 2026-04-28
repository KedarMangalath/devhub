import { Link } from 'react-router-dom'
import { Activity, Twitter, Linkedin, Github } from 'lucide-react'

export default function Footer() {
  const currentYear = new Date().getFullYear()

  return (
    <footer className="bg-white border-t border-slate-200 pt-16 pb-8 mt-auto">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-8 lg:gap-12 mb-12">
          
          {/* Brand & Mission */}
          <div className="lg:col-span-2">
            <Link to="/" className="flex items-center gap-2 text-sky-600 mb-4 inline-flex">
              <Activity className="h-7 w-7" />
              <span className="font-display font-bold text-2xl text-slate-900 tracking-tight">Omnia</span>
            </Link>
            <p className="text-slate-500 mb-6 max-w-sm leading-relaxed">
              Intelligent telemedicine powered by AI for a healthier tomorrow. 
              Experience seamless care, proactive insights, and top-tier specialists anywhere.
            </p>
            <div className="flex space-x-5">
              <a href="#" aria-label="Twitter" className="text-slate-400 hover:text-sky-600 transition-colors">
                <Twitter className="h-5 w-5" />
              </a>
              <a href="#" aria-label="LinkedIn" className="text-slate-400 hover:text-sky-600 transition-colors">
                <Linkedin className="h-5 w-5" />
              </a>
              <a href="#" aria-label="GitHub" className="text-slate-400 hover:text-sky-600 transition-colors">
                <Github className="h-5 w-5" />
              </a>
            </div>
          </div>

          {/* For Patients */}
          <div>
            <h3 className="font-display font-semibold text-slate-900 mb-4">For Patients</h3>
            <ul className="space-y-3 text-sm text-slate-500">
              <li>
                <Link to="/dashboard" className="hover:text-sky-600 transition-colors">Patient Dashboard</Link>
              </li>
              <li>
                <Link to="/directory" className="hover:text-sky-600 transition-colors">Find a Specialist</Link>
              </li>
              <li>
                <Link to="/booking" className="hover:text-sky-600 transition-colors">Book Appointment</Link>
              </li>
              <li>
                <Link to="/history" className="hover:text-sky-600 transition-colors">Medical History</Link>
              </li>
            </ul>
          </div>

          {/* Top Specialties */}
          <div>
            <h3 className="font-display font-semibold text-slate-900 mb-4">Top Specialties</h3>
            <ul className="space-y-3 text-sm text-slate-500">
              <li>
                <Link to="/directory" className="hover:text-sky-600 transition-colors">General Practice</Link>
              </li>
              <li>
                <Link to="/directory" className="hover:text-sky-600 transition-colors">Cardiology</Link>
              </li>
              <li>
                <Link to="/directory" className="hover:text-sky-600 transition-colors">Neurology</Link>
              </li>
              <li>
                <Link to="/directory" className="hover:text-sky-600 transition-colors">Pediatrics</Link>
              </li>
            </ul>
          </div>

          {/* Legal & Support */}
          <div>
            <h3 className="font-display font-semibold text-slate-900 mb-4">Legal & Support</h3>
            <ul className="space-y-3 text-sm text-slate-500">
              <li>
                <a href="#" className="hover:text-sky-600 transition-colors">Help Center</a>
              </li>
              <li>
                <a href="#" className="hover:text-sky-600 transition-colors">Privacy Policy</a>
              </li>
              <li>
                <a href="#" className="hover:text-sky-600 transition-colors">Terms of Service</a>
              </li>
              <li>
                <a href="#" className="hover:text-sky-600 transition-colors">Accessibility</a>
              </li>
            </ul>
          </div>
        </div>

        {/* Bottom Bar */}
        <div className="pt-8 border-t border-slate-100 flex flex-col md:flex-row justify-between items-center gap-4">
          <p className="text-sm text-slate-400">
            &copy; {currentYear} Omnia Health Inc. All rights reserved.
          </p>
          <div className="flex items-center gap-2 text-sm text-slate-500 bg-slate-50 px-3 py-1.5 rounded-full border border-slate-100">
            <span className="relative flex h-2.5 w-2.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500"></span>
            </span>
            All systems operational
          </div>
        </div>
      </div>
    </footer>
  )
}