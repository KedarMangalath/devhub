import { useState, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { complaints } from '../mockData'
import Navbar from '../components/layout/Navbar'
import UserComplaintsList from '../components/history/UserComplaintsList'
import Footer from '../components/layout/Footer'
import { 
  ShieldCheck, 
  Lock, 
  FilePlus, 
  BarChart3, 
  CheckCircle2, 
  Clock, 
  AlertTriangle, 
  Search, 
  Filter, 
  ChevronRight, 
  Shield, 
  Activity, 
  FileText,
  HelpCircle,
  Server,
  Key
} from 'lucide-react'

export default function History() {
  // Local state for page-level tabs
  const [activeTab, setActiveTab] = useState('all')

  // Calculate summary statistics from mock data
  const stats = useMemo(() => {
    const total = complaints.length
    const resolved = complaints.filter(c => c.status?.toLowerCase() === 'resolved').length
    const investigating = complaints.filter(c => 
      ['investigating', 'in progress', 'pending'].includes(c.status?.toLowerCase())
    ).length
    const highRisk = complaints.filter(c => 
      ['high risk', 'action required'].includes(c.status?.toLowerCase())
    ).length

    return { total, resolved, investigating, highRisk }
  }, [])

  // Filter complaints based on active tab
  const filteredComplaints = useMemo(() => {
    return complaints.filter(complaint => {
      const status = complaint.status?.toLowerCase() || ''
      if (activeTab === 'all') return true
      if (activeTab === 'active') {
        return ['investigating', 'in progress', 'pending', 'high risk', 'action required'].includes(status)
      }
      if (activeTab === 'resolved') {
        return status === 'resolved'
      }
      return true
    })
  }, [activeTab])

  return (
    <div className="min-h-screen flex flex-col bg-[#F8FAFC] font-body text-slate-900 selection:bg-emerald-500/30">
      {/* Section 1: Navbar (Imported) */}
      <Navbar />

      <main className="flex-grow flex flex-col">
        
        {/* Section 2: SecureHeader (Hero) */}
        <section className="relative isolate overflow-hidden bg-slate-950 pt-24 pb-32 sm:pt-32 sm:pb-40 border-b border-slate-800">
          {/* Background Image with Overlay */}
          <img
            src="https://images.unsplash.com/photo-1589829085413-56de8ae18c73?w=800&q=80"
            alt="Abstract representation of secure data and justice"
            className="absolute inset-0 -z-20 h-full w-full object-cover opacity-20 mix-blend-luminosity"
          />
          <div className="absolute inset-0 -z-10 bg-gradient-to-t from-slate-950 via-slate-950/80 to-transparent" />
          
          {/* Emerald Glow Effect */}
          <div className="absolute left-1/2 top-0 -z-10 -translate-x-1/2 blur-3xl xl:-top-6" aria-hidden="true">
            <div
              className="aspect-[1155/678] w-[72.1875rem] bg-gradient-to-tr from-[#059669] to-[#0f172a] opacity-30"
              style={{
                clipPath: 'polygon(74.1% 44.1%, 100% 61.6%, 97.5% 26.9%, 85.5% 0.1%, 80.7% 2%, 72.5% 32.5%, 60.2% 62.4%, 52.4% 68.1%, 47.5% 58.3%, 45.2% 34.5%, 27.5% 76.7%, 0.1% 64.9%, 17.9% 100%, 27.6% 76.8%, 76.1% 97.7%, 74.1% 44.1%)',
              }}
            />
          </div>

          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 relative z-10">
            <div className="mx-auto max-w-3xl text-center">
              <div className="mb-6 inline-flex items-center rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1.5 text-sm font-medium text-emerald-300 backdrop-blur-sm">
                <Lock className="mr-2 h-4 w-4" />
                End-to-End Encrypted Portal
              </div>
              <h1 className="font-display text-4xl font-bold tracking-tight text-white sm:text-5xl lg:text-6xl mb-6">
                Track Your Submitted Reports with <span className="text-transparent bg-clip-text bg-gradient-to-r from-emerald-400 to-cyan-400">Blockchain-Verified Transparency</span>
              </h1>
              <p className="mt-6 text-lg leading-8 text-slate-300 font-body max-w-2xl mx-auto">
                Monitor the real-time status of your complaints, review AI credibility assessments, and access immutable audit trails ensuring your voice is heard and protected.
              </p>
              <div className="mt-10 flex items-center justify-center gap-x-6">
                <Link
                  to="/report"
                  className="group inline-flex items-center justify-center rounded-lg bg-emerald-600 px-6 py-3 text-sm font-semibold text-white shadow-sm hover:bg-emerald-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-600 transition-all duration-200"
                >
                  <FilePlus className="mr-2 h-5 w-5 transition-transform group-hover:-translate-y-0.5" />
                  File a New Report
                </Link>
                <Link
                  to="/analytics"
                  className="group inline-flex items-center justify-center rounded-lg border border-slate-700 bg-slate-800/50 px-6 py-3 text-sm font-semibold text-white shadow-sm hover:bg-slate-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-600 backdrop-blur-sm transition-all duration-200"
                >
                  <BarChart3 className="mr-2 h-5 w-5 text-slate-400 group-hover:text-white transition-colors" />
                  View Department Analytics
                </Link>
              </div>
            </div>
          </div>
        </section>

        {/* Section 3: Trust & Security Banner */}
        <section className="bg-emerald-900/20 border-b border-emerald-900/30 py-4">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex flex-wrap items-center justify-center gap-x-8 gap-y-4 text-sm font-medium text-emerald-700 dark:text-emerald-400">
              <div className="flex items-center gap-2">
                <ShieldCheck className="h-5 w-5" />
                <span>Zero-Knowledge Proof Identity Protection</span>
              </div>
              <div className="hidden sm:block w-1 h-1 rounded-full bg-emerald-500/50"></div>
              <div className="flex items-center gap-2">
                <Server className="h-5 w-5" />
                <span>State Data Centre Hosted</span>
              </div>
              <div className="hidden sm:block w-1 h-1 rounded-full bg-emerald-500/50"></div>
              <div className="flex items-center gap-2">
                <Key className="h-5 w-5" />
                <span>Cryptographic Audit Trails</span>
              </div>
            </div>
          </div>
        </section>

        {/* Section 4: Stats Overview */}
        <section className="py-12 bg-white border-b border-slate-200">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
              {/* Stat Card 1 */}
              <div className="bg-slate-50 rounded-2xl p-6 border border-slate-100 shadow-sm flex items-start justify-between">
                <div>
                  <p className="text-sm font-medium text-slate-500 mb-1">Total Reports Filed</p>
                  <p className="font-display text-3xl font-bold text-slate-900">{stats.total}</p>
                </div>
                <div className="p-3 bg-blue-100 text-blue-600 rounded-xl">
                  <FileText className="h-6 w-6" />
                </div>
              </div>
              {/* Stat Card 2 */}
              <div className="bg-slate-50 rounded-2xl p-6 border border-slate-100 shadow-sm flex items-start justify-between">
                <div>
                  <p className="text-sm font-medium text-slate-500 mb-1">Active Investigations</p>
                  <p className="font-display text-3xl font-bold text-slate-900">{stats.investigating}</p>
                </div>
                <div className="p-3 bg-amber-100 text-amber-600 rounded-xl">
                  <Clock className="h-6 w-6" />
                </div>
              </div>
              {/* Stat Card 3 */}
              <div className="bg-slate-50 rounded-2xl p-6 border border-slate-100 shadow-sm flex items-start justify-between">
                <div>
                  <p className="text-sm font-medium text-slate-500 mb-1">Successfully Resolved</p>
                  <p className="font-display text-3xl font-bold text-slate-900">{stats.resolved}</p>
                </div>
                <div className="p-3 bg-emerald-100 text-emerald-600 rounded-xl">
                  <CheckCircle2 className="h-6 w-6" />
                </div>
              </div>
              {/* Stat Card 4 */}
              <div className="bg-slate-50 rounded-2xl p-6 border border-slate-100 shadow-sm flex items-start justify-between">
                <div>
                  <p className="text-sm font-medium text-slate-500 mb-1">High Risk Alerts</p>
                  <p className="font-display text-3xl font-bold text-slate-900">{stats.highRisk}</p>
                </div>
                <div className="p-3 bg-rose-100 text-rose-600 rounded-xl">
                  <AlertTriangle className="h-6 w-6" />
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Section 5: HistoryTabs & Controls */}
        <section className="pt-12 pb-6 bg-[#F8FAFC]">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-8">
              <div>
                <h2 className="font-display text-2xl font-bold text-slate-900">My Report History</h2>
                <p className="text-sm text-slate-500 mt-1">Manage and track the status of your submissions.</p>
              </div>
              
              {/* Inline Tabs */}
              <div className="inline-flex bg-slate-200/50 p-1 rounded-xl border border-slate-200">
                <button
                  onClick={() => setActiveTab('all')}
                  className={`px-4 py-2 text-sm font-medium rounded-lg transition-all duration-200 ${
                    activeTab === 'all' 
                      ? 'bg-white text-slate-900 shadow-sm border border-slate-200/50' 
                      : 'text-slate-600 hover:text-slate-900 hover:bg-slate-200/50'
                  }`}
                >
                  All Reports
                </button>
                <button
                  onClick={() => setActiveTab('active')}
                  className={`px-4 py-2 text-sm font-medium rounded-lg transition-all duration-200 flex items-center gap-2 ${
                    activeTab === 'active' 
                      ? 'bg-white text-slate-900 shadow-sm border border-slate-200/50' 
                      : 'text-slate-600 hover:text-slate-900 hover:bg-slate-200/50'
                  }`}
                >
                  <Activity className="w-4 h-4 text-amber-500" />
                  Active
                </button>
                <button
                  onClick={() => setActiveTab('resolved')}
                  className={`px-4 py-2 text-sm font-medium rounded-lg transition-all duration-200 flex items-center gap-2 ${
                    activeTab === 'resolved' 
                      ? 'bg-white text-slate-900 shadow-sm border border-slate-200/50' 
                      : 'text-slate-600 hover:text-slate-900 hover:bg-slate-200/50'
                  }`}
                >
                  <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                  Resolved
                </button>
              </div>
            </div>
          </div>
        </section>

        {/* Section 6: UserComplaintsList (Imported Component) */}
        <section className="pb-16 bg-[#F8FAFC]">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            {/* We pass the filtered complaints down to the imported component */}
            <UserComplaintsList complaints={filteredComplaints} />
            
            {filteredComplaints.length === 0 && (
              <div className="text-center py-16 bg-white rounded-2xl border border-slate-200 mt-6">
                <div className="mx-auto w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center mb-4">
                  <Search className="w-8 h-8 text-slate-400" />
                </div>
                <h3 className="text-lg font-medium text-slate-900 font-display">No reports found</h3>
                <p className="text-slate-500 mt-1 max-w-sm mx-auto">
                  We couldn't find any reports matching your current filter criteria.
                </p>
                <button 
                  onClick={() => setActiveTab('all')}
                  className="mt-6 text-emerald-600 font-medium hover:text-emerald-700"
                >
                  Clear filters
                </button>
              </div>
            )}
          </div>
        </section>

        {/* Section 7: Blockchain Verification Info */}
        <section className="py-16 bg-white border-t border-slate-200">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="bg-slate-950 rounded-3xl overflow-hidden shadow-xl border border-slate-800 relative">
              {/* Decorative background pattern */}
              <div className="absolute inset-0 opacity-10 bg-[radial-gradient(#059669_1px,transparent_1px)] [background-size:20px_20px]"></div>
              
              <div className="relative p-8 sm:p-12 lg:flex lg:items-center lg:justify-between gap-12">
                <div className="lg:w-1/2">
                  <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/20 text-emerald-400 text-sm font-medium mb-6 border border-emerald-500/30">
                    <Shield className="w-4 h-4" />
                    Immutable Records
                  </div>
                  <h2 className="font-display text-3xl font-bold text-white mb-4">
                    How Your Data is Secured
                  </h2>
                  <p className="text-slate-400 text-lg mb-8 leading-relaxed">
                    Every report submitted through Vigilance C3MS is cryptographically hashed and anchored to a private blockchain network. This ensures that once a complaint is filed, it cannot be altered, deleted, or hidden by any authority.
                  </p>
                  
                  <ul className="space-y-4">
                    <li className="flex items-start gap-3">
                      <div className="mt-1 bg-emerald-500/20 p-1 rounded text-emerald-400">
                        <CheckCircle2 className="w-4 h-4" />
                      </div>
                      <div>
                        <strong className="text-slate-200 block">SHA-256 Hashing</strong>
                        <span className="text-slate-400 text-sm">Evidence files are hashed before upload, proving they haven't been tampered with.</span>
                      </div>
                    </li>
                    <li className="flex items-start gap-3">
                      <div className="mt-1 bg-emerald-500/20 p-1 rounded text-emerald-400">
                        <CheckCircle2 className="w-4 h-4" />
                      </div>
                      <div>
                        <strong className="text-slate-200 block">Decentralized Storage</strong>
                        <span className="text-slate-400 text-sm">Metadata is distributed across State Data Centre nodes to prevent single points of failure.</span>
                      </div>
                    </li>
                  </ul>
                </div>
                
                <div className="lg:w-1/2 mt-10 lg:mt-0">
                  <div className="bg-slate-900 rounded-2xl p-6 border border-slate-800 font-mono text-sm text-slate-300 shadow-2xl">
                    <div className="flex items-center gap-2 mb-4 pb-4 border-b border-slate-800">
                      <div className="w-3 h-3 rounded-full bg-rose-500"></div>
                      <div className="w-3 h-3 rounded-full bg-amber-500"></div>
                      <div className="w-3 h-3 rounded-full bg-emerald-500"></div>
                      <span className="ml-2 text-slate-500">blockchain_audit.log</span>
                    </div>
                    <div className="space-y-2 opacity-80">
                      <p><span className="text-emerald-400">[{new Date().toISOString().split('T')[0]}]</span> INFO: Initializing secure payload...</p>
                      <p><span className="text-emerald-400">[{new Date().toISOString().split('T')[0]}]</span> SUCCESS: ZK-Proof identity verified.</p>
                      <p><span className="text-emerald-400">[{new Date().toISOString().split('T')[0]}]</span> HASH: 0x8f2a9c11b3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8</p>
                      <p><span className="text-emerald-400">[{new Date().toISOString().split('T')[0]}]</span> TX_ID: 0x3a1b...7d22 anchored to ledger.</p>
                      <p className="text-emerald-400 mt-4 animate-pulse">_ Awaiting investigator assignment...</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Section 8: FAQ / Understanding Statuses */}
        <section className="py-16 bg-[#F8FAFC]">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="text-center mb-12">
              <h2 className="font-display text-3xl font-bold text-slate-900">Understanding Your Report Status</h2>
              <p className="mt-4 text-lg text-slate-600 max-w-2xl mx-auto">
                Our system uses standardized statuses to keep you informed at every step of the investigation process.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
              {/* Status 1 */}
              <div className="bg-white p-8 rounded-2xl border border-slate-200 shadow-sm hover:shadow-md transition-shadow">
                <div className="w-12 h-12 bg-blue-50 rounded-xl flex items-center justify-center mb-6 border border-blue-100">
                  <Clock className="w-6 h-6 text-blue-600" />
                </div>
                <h3 className="text-xl font-bold text-slate-900 mb-3 font-display">Pending Review</h3>
                <p className="text-slate-600 text-sm leading-relaxed">
                  Your report has been securely received and encrypted. It is currently in the queue for initial AI credibility assessment and assignment to a human investigator.
                </p>
              </div>

              {/* Status 2 */}
              <div className="bg-white p-8 rounded-2xl border border-slate-200 shadow-sm hover:shadow-md transition-shadow">
                <div className="w-12 h-12 bg-amber-50 rounded-xl flex items-center justify-center mb-6 border border-amber-100">
                  <Search className="w-6 h-6 text-amber-600" />
                </div>
                <h3 className="text-xl font-bold text-slate-900 mb-3 font-display">Investigating</h3>
                <p className="text-slate-600 text-sm leading-relaxed">
                  An officer has been assigned. Field work, evidence verification, or departmental audits are actively taking place. You may receive secure messages requesting more info.
                </p>
              </div>

              {/* Status 3 */}
              <div className="bg-white p-8 rounded-2xl border border-slate-200 shadow-sm hover:shadow-md transition-shadow">
                <div className="w-12 h-12 bg-emerald-50 rounded-xl flex items-center justify-center mb-6 border border-emerald-100">
                  <CheckCircle2 className="w-6 h-6 text-emerald-600" />
                </div>
                <h3 className="text-xl font-bold text-slate-900 mb-3 font-display">Resolved</h3>
                <p className="text-slate-600 text-sm leading-relaxed">
                  The investigation is complete. Action has been taken (e.g., suspension, fund recovery, or policy change). A final closing report is available in your dashboard.
                </p>
              </div>
            </div>

            <div className="mt-12 bg-slate-50 rounded-2xl p-6 border border-slate-200 flex flex-col sm:flex-row items-center justify-between gap-6">
              <div className="flex items-center gap-4">
                <div className="bg-white p-3 rounded-full shadow-sm border border-slate-200">
                  <HelpCircle className="w-6 h-6 text-slate-600" />
                </div>
                <div>
                  <h4 className="font-bold text-slate-900">Need further assistance?</h4>
                  <p className="text-sm text-slate-500">Our support team is available 24/7 for technical issues.</p>
                </div>
              </div>
              <button className="px-6 py-2.5 bg-white border border-slate-300 text-slate-700 font-medium rounded-lg hover:bg-slate-50 transition-colors shadow-sm whitespace-nowrap">
                Contact Support
              </button>
            </div>
          </div>
        </section>

      </main>

      {/* Section 9: Footer (Imported) */}
      <Footer />
    </div>
  )
}