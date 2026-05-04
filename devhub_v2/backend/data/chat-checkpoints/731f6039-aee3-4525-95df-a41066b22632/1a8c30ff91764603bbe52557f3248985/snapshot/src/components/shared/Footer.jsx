import { Shield } from 'lucide-react'

export default function Footer() {
  return (
    <footer className="bg-white border-t border-slate-200 pt-12 pb-8 mt-auto">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mb-8">
          {/* Brand & About */}
          <div>
            <div className="flex items-center gap-2 mb-4">
              <Shield className="h-6 w-6 text-[#1d4ed8]" />
              <span className="text-lg font-bold text-[#0F172A] tracking-tight">
                C3MS Kerala
              </span>
            </div>
            <p className="text-sm text-[#64748B] leading-relaxed max-w-xs">
              Citizen-Centric Anti-Corruption System. Secure, transparent, and AI-powered grievance redressal for a corruption-free Kerala.
            </p>
          </div>

          {/* Emergency Contacts */}
          <div>
            <h3 className="text-sm font-semibold text-[#0F172A] uppercase tracking-wider mb-4">
              Emergency Contacts
            </h3>
            <ul className="space-y-3 text-sm text-[#64748B]">
              <li>
                <span className="block font-medium text-[#0F172A]">Vigilance Toll-Free</span>
                1064 / 1800-425-3222
              </li>
              <li>
                <span className="block font-medium text-[#0F172A]">WhatsApp Helpline</span>
                +91 94477 89100
              </li>
              <li>
                <span className="block font-medium text-[#0F172A]">Email Support</span>
                report@c3ms.kerala.gov.in
              </li>
            </ul>
          </div>

          {/* Quick Links */}
          <div>
            <h3 className="text-sm font-semibold text-[#0F172A] uppercase tracking-wider mb-4">
              Important Links
            </h3>
            <ul className="space-y-2 text-sm text-[#64748B]">
              <li>
                <a href="#" className="hover:text-[#1d4ed8] transition-colors">Privacy Policy</a>
              </li>
              <li>
                <a href="#" className="hover:text-[#1d4ed8] transition-colors">Terms of Service</a>
              </li>
              <li>
                <a href="#" className="hover:text-[#1d4ed8] transition-colors">Citizen Charter</a>
              </li>
              <li>
                <a href="#" className="hover:text-[#1d4ed8] transition-colors">Whistleblower Protection Act</a>
              </li>
            </ul>
          </div>
        </div>

        {/* Bottom Bar */}
        <div className="pt-8 border-t border-slate-200 flex flex-col md:flex-row justify-between items-center gap-4">
          <p className="text-sm text-[#64748B]">
            &copy; {new Date().getFullYear()} Government of Kerala. All rights reserved.
          </p>
          <div className="flex gap-4 text-sm text-[#64748B]">
            <span className="flex items-center gap-1.5">
              <span className="relative flex h-2.5 w-2.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#1d4ed8] opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-[#1d4ed8]"></span>
              </span>
              System Status: Operational
            </span>
          </div>
        </div>
      </div>
    </footer>
  )
}