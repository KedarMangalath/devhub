import { Activity } from 'lucide-react'

export default function Footer() {
  return (
    <footer className="bg-slate-900 text-slate-300 py-12 border-t border-slate-800 mt-auto">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
          <div className="col-span-1 md:col-span-1">
            <div className="flex items-center gap-2 mb-4">
              <Activity className="h-6 w-6 text-blue-500" />
              <span className="text-xl font-bold text-white">Omnia</span>
            </div>
            <p className="text-sm text-slate-400 leading-relaxed">
              Secure health-tech platform for doctor discovery, teleconsultations, and digital health records.
            </p>
          </div>
          
          <div>
            <h3 className="text-sm font-semibold text-white uppercase tracking-wider mb-4">Platform</h3>
            <ul className="space-y-3 text-sm">
              <li><a href="/doctors" className="hover:text-blue-400 transition-colors">Find a Doctor</a></li>
              <li><a href="/dashboard" className="hover:text-blue-400 transition-colors">Patient Dashboard</a></li>
              <li><a href="/pharmacy" className="hover:text-blue-400 transition-colors">Online Pharmacy</a></li>
            </ul>
          </div>

          <div>
            <h3 className="text-sm font-semibold text-white uppercase tracking-wider mb-4">Company</h3>
            <ul className="space-y-3 text-sm">
              <li><a href="#" className="hover:text-blue-400 transition-colors">About Us</a></li>
              <li><a href="#" className="hover:text-blue-400 transition-colors">Careers</a></li>
              <li><a href="#" className="hover:text-blue-400 transition-colors">Contact Support</a></li>
            </ul>
          </div>

          <div>
            <h3 className="text-sm font-semibold text-white uppercase tracking-wider mb-4">Legal</h3>
            <ul className="space-y-3 text-sm">
              <li><a href="#" className="hover:text-blue-400 transition-colors">Privacy Policy</a></li>
              <li><a href="#" className="hover:text-blue-400 transition-colors">Terms of Service</a></li>
              <li><a href="#" className="hover:text-blue-400 transition-colors">HIPAA Compliance</a></li>
            </ul>
          </div>
        </div>
        
        <div className="mt-12 pt-8 border-t border-slate-800 flex flex-col md:flex-row justify-between items-center gap-4">
          <p className="text-sm text-slate-500">
            &copy; {new Date().getFullYear()} Omnia Health. All rights reserved.
          </p>
          <div className="flex space-x-6 text-sm text-slate-500">
            <span>Emergency: 911</span>
            <span>Support: 1-800-OMNIA-HLTH</span>
          </div>
        </div>
      </div>
    </footer>
  )
}