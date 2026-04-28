import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { CheckCircle, Calendar, Clock, CreditCard, FileText, ChevronRight, ChevronLeft } from 'lucide-react'
import AppShell from '../components/layout/AppShell'
import Button from '../components/ui/Button'
import Card from '../components/ui/Card'
import { getDoctorById } from '../mockData'

const steps = [
  { id: 1, name: 'Intake', icon: FileText },
  { id: 2, name: 'Schedule', icon: Calendar },
  { id: 3, name: 'Payment', icon: CreditCard },
  { id: 4, name: 'Confirmation', icon: CheckCircle },
]

const mockDates = [
  { id: 'd1', label: 'Today', date: 'May 20, 2024' },
  { id: 'd2', label: 'Tomorrow', date: 'May 21, 2024' },
  { id: 'd3', label: 'Wednesday', date: 'May 22, 2024' },
  { id: 'd4', label: 'Thursday', date: 'May 23, 2024' },
]

const mockTimes = [
  '09:00 AM', '09:30 AM', '10:00 AM', '11:00 AM', 
  '01:30 PM', '02:00 PM', '03:30 PM', '04:00 PM'
]

export default function BookingWorkflow() {
  const { id } = useParams()
  const navigate = useNavigate()
  const doctor = getDoctorById(id) || getDoctorById('doc_01') // Fallback for demo purposes

  const [step, setStep] = useState(1)
  const [formData, setFormData] = useState({
    symptoms: '',
    date: '',
    time: '',
    cardName: '',
    cardNumber: '',
    expiry: '',
    cvc: ''
  })

  const updateForm = (field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }))
  }

  const handleNext = () => setStep(prev => Math.min(prev + 1, 4))
  const handleBack = () => setStep(prev => Math.max(prev - 1, 1))

  const isStep1Valid = formData.symptoms.trim().length > 10
  const isStep2Valid = formData.date !== '' && formData.time !== ''
  const isStep3Valid = formData.cardName && formData.cardNumber.length >= 15 && formData.expiry && formData.cvc.length >= 3

  if (!doctor) {
    return (
      <AppShell>
        <div className="flex items-center justify-center h-full p-8">
          <p className="text-slate-500">Doctor not found.</p>
        </div>
      </AppShell>
    )
  }

  return (
    <AppShell>
      <div className="max-w-3xl mx-auto w-full px-4 sm:px-6 lg:px-8 py-8 md:py-12">
        
        {/* Header */}
        <div className="mb-8 text-center">
          <h1 className="text-3xl font-display font-bold text-slate-900 mb-2">Book Appointment</h1>
          <p className="text-slate-500 font-body">Complete the steps below to secure your consultation.</p>
        </div>

        {/* Stepper */}
        <div className="mb-10">
          <div className="flex items-center justify-between relative">
            <div className="absolute left-0 top-1/2 transform -translate-y-1/2 w-full h-1 bg-slate-100 -z-10 rounded-full"></div>
            <div 
              className="absolute left-0 top-1/2 transform -translate-y-1/2 h-1 bg-sky-500 -z-10 rounded-full transition-all duration-500 ease-in-out"
              style={{ width: `${((step - 1) / (steps.length - 1)) * 100}%` }}
            ></div>
            
            {steps.map((s) => {
              const Icon = s.icon
              const isActive = step === s.id
              const isCompleted = step > s.id

              return (
                <div key={s.id} className="flex flex-col items-center gap-2 bg-background px-2">
                  <div 
                    className={`w-10 h-10 rounded-full flex items-center justify-center border-2 transition-colors duration-300 ${
                      isActive 
                        ? 'border-sky-500 bg-sky-50 text-sky-600' 
                        : isCompleted 
                          ? 'border-sky-500 bg-sky-500 text-white'
                          : 'border-slate-200 bg-white text-slate-400'
                    }`}
                  >
                    <Icon className="w-5 h-5" />
                  </div>
                  <span className={`text-xs font-medium hidden sm:block ${
                    isActive || isCompleted ? 'text-slate-900' : 'text-slate-400'
                  }`}>
                    {s.name}
                  </span>
                </div>
              )
            })}
          </div>
        </div>

        {/* Main Content Card */}
        <Card className="p-0 overflow-hidden shadow-md border-slate-200/60">
          
          {/* Doctor Info Header (Visible on steps 1-3) */}
          {step < 4 && (
            <div className="bg-slate-50 border-b border-slate-100 p-6 flex items-center gap-4">
              <img 
                src={doctor.avatar} 
                alt={doctor.name} 
                className="w-16 h-16 rounded-full object-cover border-2 border-white shadow-sm"
              />
              <div>
                <h2 className="font-display font-semibold text-lg text-slate-900">{doctor.name}</h2>
                <p className="text-sm text-slate-500">{doctor.specialty_name} • ${doctor.consultation_fee} / visit</p>
              </div>
            </div>
          )}

          <div className="p-6 md:p-8">
            
            {/* STEP 1: Intake */}
            {step === 1 && (
              <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
                <div>
                  <h3 className="text-xl font-display font-semibold text-slate-900 mb-1">Reason for visit</h3>
                  <p className="text-sm text-slate-500 mb-4">Please describe your symptoms or the reason for your consultation to help the doctor prepare.</p>
                  <textarea
                    value={formData.symptoms}
                    onChange={(e) => updateForm('symptoms', e.target.value)}
                    placeholder="E.g., I've been experiencing mild chest pain and shortness of breath for the past two days..."
                    className="w-full h-40 p-4 rounded-xl border border-slate-200 focus:border-sky-500 focus:ring-2 focus:ring-sky-500/20 outline-none transition-all resize-none text-slate-700 font-body"
                  />
                  <p className="text-xs text-slate-400 mt-2 text-right">
                    {formData.symptoms.length} characters (minimum 10 required)
                  </p>
                </div>
                <div className="flex justify-end pt-4 border-t border-slate-100">
                  <Button 
                    onClick={handleNext} 
                    disabled={!isStep1Valid}
                    className="gap-2"
                  >
                    Continue to Schedule <ChevronRight className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            )}

            {/* STEP 2: Schedule */}
            {step === 2 && (
              <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
                <div>
                  <h3 className="text-xl font-display font-semibold text-slate-900 mb-4 flex items-center gap-2">
                    <Calendar className="w-5 h-5 text-sky-500" /> Select a Date
                  </h3>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    {mockDates.map((d) => (
                      <button
                        key={d.id}
                        onClick={() => updateForm('date', d.date)}
                        className={`p-3 rounded-xl border text-left transition-all ${
                          formData.date === d.date
                            ? 'border-sky-500 bg-sky-50 ring-1 ring-sky-500'
                            : 'border-slate-200 hover:border-sky-300 hover:bg-slate-50'
                        }`}
                      >
                        <div className={`text-sm font-semibold ${formData.date === d.date ? 'text-sky-700' : 'text-slate-900'}`}>
                          {d.label}
                        </div>
                        <div className={`text-xs mt-1 ${formData.date === d.date ? 'text-sky-600' : 'text-slate-500'}`}>
                          {d.date}
                        </div>
                      </button>
                    ))}
                  </div>
                </div>

                {formData.date && (
                  <div className="animate-in fade-in duration-300">
                    <h3 className="text-xl font-display font-semibold text-slate-900 mb-4 flex items-center gap-2">
                      <Clock className="w-5 h-5 text-sky-500" /> Available Times
                    </h3>
                    <div className="grid grid-cols-3 sm:grid-cols-4 gap-3">
                      {mockTimes.map((time) => (
                        <button
                          key={time}
                          onClick={() => updateForm('time', time)}
                          className={`py-2.5 px-3 rounded-lg border text-sm font-medium transition-all text-center ${
                            formData.time === time
                              ? 'border-sky-500 bg-sky-500 text-white shadow-sm'
                              : 'border-slate-200 text-slate-700 hover:border-sky-300 hover:bg-slate-50'
                          }`}
                        >
                          {time}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                <div className="flex justify-between pt-6 border-t border-slate-100">
                  <Button variant="ghost" onClick={handleBack} className="gap-2">
                    <ChevronLeft className="w-4 h-4" /> Back
                  </Button>
                  <Button 
                    onClick={handleNext} 
                    disabled={!isStep2Valid}
                    className="gap-2"
                  >
                    Continue to Payment <ChevronRight className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            )}

            {/* STEP 3: Payment */}
            {step === 3 && (
              <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
                
                <div className="bg-sky-50 rounded-xl p-5 border border-sky-100 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
                  <div>
                    <h4 className="font-semibold text-sky-900 mb-1">Appointment Summary</h4>
                    <p className="text-sm text-sky-700 flex items-center gap-2">
                      <Calendar className="w-4 h-4" /> {formData.date} at {formData.time}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm text-sky-700 mb-1">Total Due</p>
                    <p className="text-2xl font-display font-bold text-sky-900">${doctor.consultation_fee}</p>
                  </div>
                </div>

                <div>
                  <h3 className="text-xl font-display font-semibold text-slate-900 mb-4">Payment Details</h3>
                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-slate-700 mb-1.5">Name on Card</label>
                      <input
                        type="text"
                        value={formData.cardName}
                        onChange={(e) => updateForm('cardName', e.target.value)}
                        placeholder="John Doe"
                        className="w-full p-3 rounded-lg border border-slate-200 focus:border-sky-500 focus:ring-2 focus:ring-sky-500/20 outline-none transition-all"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-slate-700 mb-1.5">Card Number</label>
                      <div className="relative">
                        <CreditCard className="absolute left-3 top-1/2 transform -translate-y-1/2 text-slate-400 w-5 h-5" />
                        <input
                          type="text"
                          value={formData.cardNumber}
                          onChange={(e) => updateForm('cardNumber', e.target.value.replace(/\D/g, '').slice(0, 16))}
                          placeholder="0000 0000 0000 0000"
                          className="w-full p-3 pl-10 rounded-lg border border-slate-200 focus:border-sky-500 focus:ring-2 focus:ring-sky-500/20 outline-none transition-all font-mono"
                        />
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="block text-sm font-medium text-slate-700 mb-1.5">Expiry Date</label>
                        <input
                          type="text"
                          value={formData.expiry}
                          onChange={(e) => updateForm('expiry', e.target.value)}
                          placeholder="MM/YY"
                          maxLength={5}
                          className="w-full p-3 rounded-lg border border-slate-200 focus:border-sky-500 focus:ring-2 focus:ring-sky-500/20 outline-none transition-all font-mono"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-slate-700 mb-1.5">CVC</label>
                        <input
                          type="text"
                          value={formData.cvc}
                          onChange={(e) => updateForm('cvc', e.target.value.replace(/\D/g, '').slice(0, 4))}
                          placeholder="123"
                          className="w-full p-3 rounded-lg border border-slate-200 focus:border-sky-500 focus:ring-2 focus:ring-sky-500/20 outline-none transition-all font-mono"
                        />
                      </div>
                    </div>
                  </div>
                </div>

                <div className="flex justify-between pt-6 border-t border-slate-100">
                  <Button variant="ghost" onClick={handleBack} className="gap-2">
                    <ChevronLeft className="w-4 h-4" /> Back
                  </Button>
                  <Button 
                    onClick={handleNext} 
                    disabled={!isStep3Valid}
                    className="gap-2 bg-emerald-600 hover:bg-emerald-700 focus-visible:ring-emerald-500"
                  >
                    Confirm & Pay ${doctor.consultation_fee}
                  </Button>
                </div>
              </div>
            )}

            {/* STEP 4: Confirmation */}
            {step === 4 && (
              <div className="py-8 text-center animate-in zoom-in-95 duration-500">
                <div className="w-20 h-20 bg-emerald-100 rounded-full flex items-center justify-center mx-auto mb-6">
                  <CheckCircle className="w-10 h-10 text-emerald-600" />
                </div>
                <h2 className="text-3xl font-display font-bold text-slate-900 mb-3">Booking Confirmed!</h2>
                <p className="text-slate-500 mb-8 max-w-md mx-auto">
                  Your appointment with {doctor.name} has been successfully scheduled. We've sent a confirmation email with the details.
                </p>
                
                <div className="bg-slate-50 rounded-2xl p-6 max-w-sm mx-auto mb-8 text-left border border-slate-100">
                  <div className="flex items-center gap-3 mb-4 pb-4 border-b border-slate-200">
                    <Calendar className="w-5 h-5 text-slate-400" />
                    <div>
                      <p className="text-sm font-medium text-slate-900">{formData.date}</p>
                      <p className="text-sm text-slate-500">{formData.time}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <img src={doctor.avatar} alt={doctor.name} className="w-10 h-10 rounded-full object-cover" />
                    <div>
                      <p className="text-sm font-medium text-slate-900">{doctor.name}</p>
                      <p className="text-xs text-slate-500">{doctor.specialty_name}</p>
                    </div>
                  </div>
                </div>

                <Button 
                  onClick={() => navigate('/dashboard')}
                  size="lg"
                  className="w-full sm:w-auto"
                >
                  Go to Dashboard
                </Button>
              </div>
            )}

          </div>
        </Card>
      </div>
    </AppShell>
  )
}