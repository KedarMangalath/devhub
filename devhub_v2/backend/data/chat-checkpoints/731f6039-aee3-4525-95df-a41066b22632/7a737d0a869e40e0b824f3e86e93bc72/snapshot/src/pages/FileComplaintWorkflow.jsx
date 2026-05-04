import { useState } from 'react'
import Navbar from '../components/shared/Navbar'
import Footer from '../components/shared/Footer'
import StepIndicator from '../components/file-complaint/StepIndicator'
import DepartmentSelector from '../components/file-complaint/DepartmentSelector'
import ComplaintForm from '../components/file-complaint/ComplaintForm'
import EvidenceUploader from '../components/file-complaint/EvidenceUploader'
import ReviewSubmitCard from '../components/file-complaint/ReviewSubmitCard'
import { CheckCircle } from 'lucide-react'
import { Link } from 'react-router-dom'

export default function FileComplaintWorkflow() {
  const [step, setStep] = useState(1)
  const [formData, setFormData] = useState({
    departmentId: '',
    title: '',
    category: '',
    location: '',
    description: '',
    isAnonymous: false
  })
  const [files, setFiles] = useState([])
  const [trackingId, setTrackingId] = useState('')

  const steps = [
    'Select Department',
    'Provide Details',
    'Upload Evidence',
    'Review & Submit'
  ]

  const canProceed = () => {
    if (step === 1) return !!formData.departmentId
    if (step === 2) {
      return !!(
        formData.title?.trim() &&
        formData.category &&
        formData.location?.trim() &&
        formData.description?.trim()
      )
    }
    return true // Step 3 (Evidence) is optional, Step 4 is review
  }

  const handleNext = () => {
    if (canProceed() && step < 4) {
      setStep(step + 1)
      window.scrollTo({ top: 0, behavior: 'smooth' })
    }
  }

  const handleBack = () => {
    if (step > 1) {
      setStep(step - 1)
      window.scrollTo({ top: 0, behavior: 'smooth' })
    }
  }

  const handleSubmit = () => {
    // Generate a mock tracking ID for the success screen
    const randomChars = Math.random().toString(36).substring(2, 8).toUpperCase()
    setTrackingId(`TRK-${randomChars}`)
    setStep(5)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  // Helper to format department name for review step since we only store ID in this component's state
  const getDepartmentDisplayName = (id) => {
    if (!id) return 'Not Selected'
    // A simple mock mapping for the review screen to look realistic without importing the full list
    const mockMap = {
      'DEPT-001': 'Revenue Department',
      'DEPT-002': 'Public Works Department (PWD)',
      'DEPT-003': 'Local Self Government (LSGD)',
      'DEPT-006': 'Police Department'
    }
    return mockMap[id] || `Department (${id})`
  }

  return (
    <div className="min-h-screen flex flex-col bg-[#F8FAFC] font-sans text-[#0F172A] selection:bg-vacb-700/20 selection:text-vacb-700">
      <Navbar />
      
      <main className="flex-grow py-8 px-4 sm:px-6 lg:px-8 max-w-5xl mx-auto w-full flex flex-col">
        {step < 5 && (
          <div className="mb-8 animate-in fade-in slide-in-from-top-4 duration-500">
            <h1 className="text-3xl font-bold text-slate-900 tracking-tight">File a Grievance</h1>
            <p className="text-slate-500 mt-2 max-w-2xl">
              Submit your complaint securely. Our AI system will analyze the details and route it to the appropriate vigilance officer. Your identity will be protected if you choose to remain anonymous.
            </p>
            <div className="mt-8">
              <StepIndicator currentStep={step - 1} steps={steps} />
            </div>
          </div>
        )}

        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 md:p-8 mb-6 flex-grow flex flex-col relative overflow-hidden">
          {/* Step 1: Department Selection */}
          {step === 1 && (
            <div className="animate-in fade-in slide-in-from-right-4 duration-300">
              <DepartmentSelector 
                selectedId={formData.departmentId} 
                onSelect={(id) => setFormData({ ...formData, departmentId: id })} 
              />
            </div>
          )}

          {/* Step 2: Complaint Details */}
          {step === 2 && (
            <div className="animate-in fade-in slide-in-from-right-4 duration-300">
              <ComplaintForm 
                formData={formData} 
                onChange={setFormData} 
              />
            </div>
          )}

          {/* Step 3: Evidence Upload */}
          {step === 3 && (
            <div className="animate-in fade-in slide-in-from-right-4 duration-300">
              <EvidenceUploader 
                files={files} 
                onFilesChange={setFiles} 
              />
            </div>
          )}

          {/* Step 4: Review & Submit */}
          {step === 4 && (
            <div className="animate-in fade-in slide-in-from-right-4 duration-300">
              <ReviewSubmitCard 
                formData={{
                  ...formData,
                  district: formData.location,
                  incidentDate: new Date().toLocaleDateString('en-IN', { year: 'numeric', month: 'long', day: 'numeric' })
                }}
                departmentName={getDepartmentDisplayName(formData.departmentId)}
                files={files}
              />
            </div>
          )}

          {/* Step 5: Success Screen */}
          {step === 5 && (
            <div className="flex flex-col items-center justify-center text-center py-16 animate-in fade-in zoom-in duration-500 my-auto">
              <div className="w-24 h-24 bg-vacb-50 rounded-full flex items-center justify-center mb-6 ring-8 ring-vacb-50/50">
                <CheckCircle className="w-12 h-12 text-vacb-700" strokeWidth={2.5} />
              </div>
              <h2 className="text-3xl font-bold text-slate-900 mb-3 tracking-tight">Complaint Submitted Successfully</h2>
              <p className="text-slate-600 max-w-md mx-auto mb-10 leading-relaxed">
                Your grievance has been securely recorded on the blockchain and routed to the appropriate vigilance officer for review.
              </p>
              
              <div className="bg-slate-50 border border-slate-200 rounded-xl p-8 w-full max-w-md mb-10 shadow-sm">
                <p className="text-sm text-slate-500 uppercase tracking-wider font-semibold mb-3">Your Tracking ID</p>
                <div className="bg-white border border-slate-200 py-4 px-6 rounded-lg inline-block">
                  <p className="text-3xl font-mono font-bold text-vacb-700 tracking-widest">{trackingId}</p>
                </div>
                <p className="text-xs text-slate-400 mt-4">
                  Please save this ID. You will need it to check the status of your complaint.
                </p>
              </div>
              
              <div className="flex flex-col sm:flex-row gap-4 w-full max-w-md">
                <Link 
                  to="/track" 
                  className="flex-1 inline-flex justify-center items-center px-6 py-3.5 bg-vacb-700 text-white font-medium rounded-lg hover:bg-vacb-800 transition-colors shadow-sm focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-vacb-700"
                >
                  Track Status Now
                </Link>
                <Link 
                  to="/" 
                  className="flex-1 inline-flex justify-center items-center px-6 py-3.5 bg-white border border-slate-300 text-slate-700 font-medium rounded-lg hover:bg-slate-50 transition-colors shadow-sm focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-slate-500"
                >
                  Return to Home
                </Link>
              </div>
            </div>
          )}
        </div>

        {/* Bottom Navigation Bar */}
        {step < 5 && (
          <div className="flex items-center justify-between pt-2 pb-8">
            <button
              onClick={handleBack}
              disabled={step === 1}
              className={`px-6 py-2.5 rounded-lg font-medium transition-all duration-200 ${
                step === 1
                  ? 'text-slate-400 bg-slate-100 cursor-not-allowed'
                  : 'text-slate-700 bg-white border border-slate-300 hover:bg-slate-50 shadow-sm'
              }`}
            >
              Back
            </button>
            
            {step < 4 ? (
              <button
                onClick={handleNext}
                disabled={!canProceed()}
                className={`px-8 py-2.5 rounded-lg font-medium transition-all duration-200 shadow-sm ${
                  canProceed()
                    ? 'bg-vacb-700 text-white hover:bg-vacb-800 focus:ring-2 focus:ring-offset-2 focus:ring-vacb-700'
                    : 'bg-vacb-100 text-vacb-400 cursor-not-allowed'
                }`}
              >
                Next Step
              </button>
            ) : (
              <button
                onClick={handleSubmit}
                className="px-8 py-2.5 rounded-lg font-medium transition-all duration-200 shadow-sm bg-vacb-700 text-white hover:bg-vacb-800 focus:ring-2 focus:ring-offset-2 focus:ring-vacb-700"
              >
                Submit Complaint
              </button>
            )}
          </div>
        )}
      </main>
      
      <Footer />
    </div>
  )
}