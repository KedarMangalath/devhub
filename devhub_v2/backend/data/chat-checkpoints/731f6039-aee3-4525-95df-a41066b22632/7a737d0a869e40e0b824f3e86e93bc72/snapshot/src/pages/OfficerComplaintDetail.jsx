import { useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import Navbar from '../components/shared/Navbar'
import StatusPill from '../components/shared/StatusPill'
import AIPanel from '../components/officer/AIPanel'
import EvidenceGallery from '../components/officer/EvidenceGallery'
import { complaints } from '../mockData'
import { ArrowLeft, Save, CheckCircle } from 'lucide-react'

export default function OfficerComplaintDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  
  // Find complaint or fallback to first for demo purposes if accessed directly without valid ID
  const complaintData = complaints.find(c => c.id === id) || complaints[0]

  // Local state for interactive elements
  const [currentStatus, setCurrentStatus] = useState(complaintData.status)
  const [notes, setNotes] = useState('')
  const [isSaving, setIsSaving] = useState(false)
  const [showSuccess, setShowSuccess] = useState(false)

  const handleSaveNotes = () => {
    if (!notes.trim() && currentStatus === complaintData.status) return
    
    setIsSaving(true)
    // Simulate network request
    setTimeout(() => {
      setIsSaving(false)
      setShowSuccess(true)
      setTimeout(() => setShowSuccess(false), 3000)
    }, 800)
  }

  const handleMarkInProgress = () => {
    setCurrentStatus('In Progress')
    setIsSaving(true)
    setTimeout(() => {
      setIsSaving(false)
      setShowSuccess(true)
      setTimeout(() => setShowSuccess(false), 3000)
    }, 800)
  }

  const formatDate = (dateString) => {
    return new Intl.DateTimeFormat('en-IN', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    }).format(new Date(dateString))
  }

  return (
    <div className="min-h-screen bg-[#F8FAFC] font-sans text-[#0F172A]">
      <Navbar />
      
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header Section */}
        <div className="mb-8">
          <Link 
            to="/officer" 
            className="inline-flex items-center text-sm font-medium text-slate-500 hover:text-vacb-700 transition-colors mb-4 focus:outline-none focus:ring-2 focus:ring-vacb-700 focus:ring-offset-2 rounded-md px-1 -ml-1"
          >
            <ArrowLeft className="w-4 h-4 mr-1.5" />
            Back to Dashboard
          </Link>
          
          <div className="flex flex-col md:flex-row md:items-start justify-between gap-4 bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
            <div className="flex-1">
              <div className="flex flex-wrap items-center gap-3 mb-3">
                <h1 className="text-2xl font-bold text-slate-900 leading-tight">
                  {complaintData.title}
                </h1>
                <StatusPill value={currentStatus} />
                <StatusPill type="severity" value={complaintData.severity} />
              </div>
              <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-sm text-slate-500">
                <span className="flex items-center gap-1.5">
                  <span className="font-semibold text-slate-700">ID:</span> 
                  <span className="font-mono bg-slate-100 px-1.5 py-0.5 rounded text-slate-600">{complaintData.id}</span>
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="font-semibold text-slate-700">Tracking:</span> 
                  <span className="font-mono bg-slate-100 px-1.5 py-0.5 rounded text-slate-600">{complaintData.tracking_id}</span>
                </span>
                <span>Filed on {formatDate(complaintData.date_filed)}</span>
              </div>
            </div>
            
            <div className="flex flex-col items-end gap-2 shrink-0">
              <div className={`px-3 py-1.5 rounded-md text-sm font-medium border flex items-center gap-2 ${
                complaintData.sla_status === 'Warning' 
                  ? 'bg-amber-50 text-amber-700 border-amber-200' 
                  : complaintData.sla_status === 'Breached'
                  ? 'bg-red-50 text-red-700 border-red-200'
                  : 'bg-vacb-50 text-vacb-700 border-vacb-200'
              }`}>
                <span className="relative flex h-2 w-2">
                  {complaintData.sla_status === 'Warning' && (
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75"></span>
                  )}
                  <span className={`relative inline-flex rounded-full h-2 w-2 ${
                    complaintData.sla_status === 'Warning' ? 'bg-amber-500' : 
                    complaintData.sla_status === 'Breached' ? 'bg-red-500' : 'bg-vacb-500'
                  }`}></span>
                </span>
                SLA: {complaintData.sla_status}
              </div>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Left Column - Main Content */}
          <div className="lg:col-span-2 space-y-8">
            
            {/* Description Card */}
            <section className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
              <div className="px-6 py-4 border-b border-slate-100 bg-slate-50/50">
                <h2 className="text-lg font-semibold text-slate-900">Complaint Details</h2>
              </div>
              <div className="p-6">
                <p className="text-slate-700 leading-relaxed whitespace-pre-wrap mb-6">
                  {complaintData.description}
                </p>
                
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-6 py-4 border-t border-slate-100">
                  <div>
                    <p className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-1">Category</p>
                    <p className="text-sm font-semibold text-slate-900">{complaintData.category}</p>
                  </div>
                  <div>
                    <p className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-1">District</p>
                    <p className="text-sm font-semibold text-slate-900">{complaintData.district}</p>
                  </div>
                  <div>
                    <p className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-1">Complainant</p>
                    <p className="text-sm font-semibold text-slate-900">
                      {complaintData.complainant_anonymous ? 'Anonymous Citizen' : 'Verified Citizen'}
                    </p>
                  </div>
                </div>
              </div>
            </section>

            {/* Evidence Gallery */}
            <section className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
              <div className="px-6 py-4 border-b border-slate-100 bg-slate-50/50 flex justify-between items-center">
                <h2 className="text-lg font-semibold text-slate-900">Attached Evidence</h2>
                <span className="text-xs font-medium bg-slate-100 text-slate-600 px-2 py-1 rounded-full">
                  Immutable Records
                </span>
              </div>
              <div className="p-6">
                <EvidenceGallery complaintId={complaintData.id} />
              </div>
            </section>

            {/* Investigation Actions */}
            <section className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
              <div className="px-6 py-4 border-b border-slate-100 bg-slate-50/50">
                <h2 className="text-lg font-semibold text-slate-900">Investigation Actions</h2>
              </div>
              <div className="p-6">
                <label htmlFor="notes" className="block text-sm font-medium text-slate-700 mb-2">
                  Officer Notes (Internal)
                </label>
                <textarea
                  id="notes"
                  rows={4}
                  className="w-full rounded-lg border border-slate-300 px-4 py-3 text-sm focus:border-vacb-700 focus:ring-1 focus:ring-vacb-700 outline-none transition-shadow resize-y"
                  placeholder="Enter findings, requested documents, or next steps..."
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                />
                
                <div className="mt-6 flex flex-col sm:flex-row items-center justify-between gap-4">
                  <div className="flex items-center h-6">
                    {showSuccess && (
                      <span className="flex items-center text-sm font-medium text-vacb-700 animate-in fade-in slide-in-from-bottom-2">
                        <CheckCircle className="w-4 h-4 mr-1.5" />
                        Updates saved to blockchain ledger
                      </span>
                    )}
                  </div>
                  
                  <div className="flex items-center gap-3 w-full sm:w-auto">
                    {currentStatus === 'Pending' && (
                      <button
                        onClick={handleMarkInProgress}
                        disabled={isSaving}
                        className="flex-1 sm:flex-none px-4 py-2.5 bg-white border border-slate-300 text-slate-700 text-sm font-semibold rounded-lg hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-slate-500 transition-colors disabled:opacity-50"
                      >
                        Mark In Progress
                      </button>
                    )}
                    <button
                      onClick={handleSaveNotes}
                      disabled={isSaving || (!notes.trim() && currentStatus === complaintData.status)}
                      className="flex-1 sm:flex-none inline-flex items-center justify-center px-5 py-2.5 bg-vacb-700 text-white text-sm font-semibold rounded-lg hover:bg-vacb-800 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-vacb-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {isSaving ? (
                        <span className="inline-flex items-center">
                          <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                          </svg>
                          Saving...
                        </span>
                      ) : (
                        <span className="inline-flex items-center">
                          <Save className="w-4 h-4 mr-2" />
                          Save Updates
                        </span>
                      )}
                    </button>
                  </div>
                </div>
              </div>
            </section>

          </div>

          {/* Right Column - Sidebar */}
          <div className="space-y-8">
            <AIPanel 
              summary={complaintData.ai_summary} 
              credibilityScore={complaintData.credibility_score} 
            />

            {/* Department Info Card */}
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
              <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider mb-4">
                Routing Information
              </h3>
              <div className="space-y-4">
                <div>
                  <p className="text-xs text-slate-500 mb-1">Assigned Department</p>
                  <p className="text-sm font-medium text-slate-900 bg-slate-50 p-2 rounded border border-slate-100">
                    {complaintData.department_id === 'DEPT-001' ? 'Revenue Department' : 
                     complaintData.department_id === 'DEPT-002' ? 'Public Works Department (PWD)' : 
                     'Local Self Government (LSGD)'}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-slate-500 mb-1">Jurisdiction</p>
                  <p className="text-sm font-medium text-slate-900">{complaintData.district} District</p>
                </div>
                <div className="pt-4 border-t border-slate-100">
                  <p className="text-xs text-slate-500 mb-2">Blockchain Verification</p>
                  <div className="flex items-center gap-2 text-xs font-mono text-vacb-700 bg-vacb-50 p-2 rounded border border-vacb-100 break-all">
                    <CheckCircle className="w-3.5 h-3.5 shrink-0" />
                    0x8f3a9b...2c1f4e
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}