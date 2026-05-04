import { Link } from 'react-router-dom'
import { Shield, Twitter, Facebook, Mail } from 'lucide-react'

export default function Footer() {
  const currentYear = new Date().getFullYear()

  return (
    <footer className="bg-slate-950 text-slate-300 py-12 border-t border-slate-800 mt-auto">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8 mb-12">
          
          {/* Brand Column */}
          <div className="col-span-1 md:col-span-1">
            <Link to="/" className="flex items-center gap-2 text-white mb-4 group">
              <Shield className="h-7 w-7 text-emerald-500 group-hover:text-emerald-400 transition-colors" />
              <span className="font-display font-bold text-2xl tracking-tight">C3MS</span>
            </Link>
            <p className="text-sm text-slate-400 leading-relaxed font-body">
              Empowering citizens to securely report, track, and combat corruption with AI-driven transparency and blockchain verification.
            </p>
          </div>

          {/* Quick Links */}
          <div>
            <h3 className="font-display font-semibold text-white mb-4 tracking-wide text-sm uppercase">Platform</h3>
            <ul className="space-y-3">
              <li>
                <Link to="/" className="text-sm text-slate-400 hover:text-emerald-400 transition-colors font-body">Home</Link>
              </li>
              <li>
                <Link to="/explore" className="text-sm text-slate-400 hover:text-emerald-400 transition-colors font-body">Public Directory</Link>
              </li>
              <li>
                <Link to="/report" className="text-sm text-slate-400 hover:text-emerald-400 transition-colors font-body">File a Complaint</Link>
              </li>
              <li>
                <Link to="/dashboard" className="text-sm text-slate-400 hover:text-emerald-400 transition-colors font-body">Investigator Portal</Link>
              </li>
            </ul>
          </div>

          {/* Legal & Info */}
          <div>
            <h3 className="font-display font-semibold text-white mb-4 tracking-wide text-sm uppercase">Information</h3>
            <ul className="space-y-3">
              <li>
                <Link to="/about" className="text-sm text-slate-400 hover:text-emerald-400 transition-colors font-body">About C3MS</Link>
              </li>
              <li>
                <Link to="/privacy" className="text-sm text-slate-400 hover:text-emerald-400 transition-colors font-body">Privacy Policy</Link>
              </li>
              <li>
                <Link to="/terms" className="text-sm text-slate-400 hover:text-emerald-400 transition-colors font-body">Terms of Service</Link>
              </li>
              <li>
                <Link to="/contact" className="text-sm text-slate-400 hover:text-emerald-400 transition-colors font-body">Contact Support</Link>
              </li>
            </ul>
          </div>

          {/* Connect */}
          <div>
            <h3 className="font-display font-semibold text-white mb-4 tracking-wide text-sm uppercase">Connect</h3>
            <p className="text-sm text-slate-400 mb-4 font-body">
              Stay updated with our latest transparency initiatives and system updates.
            </p>
            <div className="flex gap-4">
              <a href="https://twitter.com" target="_blank" rel="noopener noreferrer" className="bg-slate-800 p-2 rounded-full text-slate-400 hover:text-white hover:bg-emerald-600 transition-all" aria-label="Twitter">
                <Twitter className="h-4 w-4" />
              </a>
              <a href="https://facebook.com" target="_blank" rel="noopener noreferrer" className="bg-slate-800 p-2 rounded-full text-slate-400 hover:text-white hover:bg-emerald-600 transition-all" aria-label="Facebook">
                <Facebook className="h-4 w-4" />
              </a>
              <a href="mailto:support@vigilance.kerala.gov.in" className="bg-slate-800 p-2 rounded-full text-slate-400 hover:text-white hover:bg-emerald-600 transition-all" aria-label="Email">
                <Mail className="h-4 w-4" />
              </a>
            </div>
          </div>

        </div>

        {/* Bottom Bar */}
        <div className="pt-8 border-t border-slate-800 flex flex-col md:flex-row justify-between items-center gap-4">
          <p className="text-sm text-slate-500 font-body text-center md:text-left">
            &copy; {currentYear} Vigilance & Anti-Corruption Bureau, Government of Kerala. All rights reserved.
          </p>
          <div className="flex items-center gap-2 text-sm text-slate-500 font-body">
            <span>Secured by</span>
            <Shield className="h-4 w-4 text-emerald-500/70" />
            <span>Blockchain Audit Trail</span>
          </div>
        </div>
      </div>
    </footer>
  )
}