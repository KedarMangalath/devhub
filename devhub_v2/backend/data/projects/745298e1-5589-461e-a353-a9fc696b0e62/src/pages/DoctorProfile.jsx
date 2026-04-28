import React, { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { Star, MapPin, Clock, Award, ShieldCheck } from 'lucide-react'
import AppShell from '../components/layout/AppShell'
import Button from '../components/ui/Button'
import Badge from '../components/ui/Badge'
import { getDoctorById, testimonials } from '../mockData'

// Helper to generate mock dates for the calendar
const generateUpcomingDates = () => {
  const dates = []
  const today = new Date()
  for (let i = 0; i < 14; i++) {
    const d = new Date(today)
    d.setDate(today.getDate() + i)
    // Skip weekends for realism
    if (d.getDay() !== 0 && d.getDay() !== 6) {
      dates.push({
        id: i,
        dayName: d.toLocaleDateString('en-US', { weekday: 'short' }),
        dayNumber: d.getDate(),
        month: d.toLocaleDateString('en-US', { month: 'short' }),
        fullDate: d.toISOString(),
      })
    }
  }
  return dates.slice(0, 7) // Return next 7 available weekdays
}

const mockTimeSlots = [
  '09:00 AM', '09:30 AM', '10:00 AM', '10:30 AM', 
  '11:00 AM', '01:00 PM', '01:30 PM', '02:00 PM', 
  '03:00 PM', '03:30 PM', '04:00 PM'
]

export default function DoctorProfile() {
  const { id } = useParams()
  const [doctor, setDoctor] = useState(null)
  const [reviews, setReviews] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  
  // Local state for booking workflow
  const [availableDates] = useState(generateUpcomingDates())
  const [selectedDate, setSelectedDate] = useState(availableDates[0]?.id)
  const [selectedTime, setSelectedTime] = useState(null)

  useEffect(() => {
    // Simulate instant local data retrieval
    const docData = getDoctorById ? getDoctorById(id) : null
    const docReviews = testimonials ? testimonials.filter(t => t.doctor_id === id) : []
    
    setDoctor(docData)
    setReviews(docReviews)
    setIsLoading(false)
  }, [id])

  if (isLoading) {
    return (
      <AppShell>
        <div className="flex items-center justify-center min-h-[60vh]">
          <div className="animate-pulse flex flex-col items-center">
            <div className="w-12 h-12 bg-slate-200 rounded-full mb-4"></div>
            <div className="h-4 w-32 bg-slate-200 rounded mb-2"></div>
            <div className="h-3 w-24 bg-slate-200 rounded"></div>
          </div>
        </div>
      </AppShell>
    )
  }

  if (!doctor) {
    return (
      <AppShell>
        <div className="max-w-3xl mx-auto px-4 py-16 text-center">
          <div className="w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <ShieldCheck className="w-8 h-8 text-slate-400" />
          </div>
          <h2 className="text-2xl font-display font-bold text-slate-900 mb-2">Doctor Not Found</h2>
          <p className="text-slate-500 mb-6">We couldn't find the medical professional you're looking for.</p>
          <Link to="/doctors">
            <Button variant="primary">Return to Directory</Button>
          </Link>
        </div>
      </AppShell>
    )
  }

  return (
    <AppShell>
      <div className="bg-slate-50 min-h-screen pb-32">
        {/* Cover Banner */}
        <div className="h-32 md:h-48 bg-gradient-to-r from-sky-600 to-indigo-700 w-full"></div>

        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 -mt-16 md:-mt-24 relative z-10">
          
          {/* Header Card */}
          <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 md:p-8 mb-6">
            <div className="flex flex-col md:flex-row gap-6 items-start">
              <img 
                src={doctor.avatar || `https://picsum.photos/seed/${doctor.id}/300/300`} 
                alt={doctor.name} 
                className="w-32 h-32 md:w-40 md:h-40 rounded-2xl object-cover border-4 border-white shadow-md shrink-0 bg-slate-100"
              />
              
              <div className="flex-1 w-full">
                <div className="flex flex-col md:flex-row md:justify-between md:items-start gap-4 mb-4">
                  <div>
                    <div className="flex items-center gap-3 mb-2">
                      <h1 className="text-2xl md:text-3xl font-display font-bold text-slate-900">
                        {doctor.name}
                      </h1>
                      <ShieldCheck className="w-6 h-6 text-sky-500" />
                    </div>
                    <Badge variant="info" className="mb-3 text-sm px-3 py-1">
                      {doctor.specialty_name || 'Specialist'}
                    </Badge>
                    <div className="flex flex-wrap items-center gap-4 text-sm text-slate-600 font-medium">
                      <span className="flex items-center gap-1.5">
                        <Award className="w-4 h-4 text-slate-400" />
                        {doctor.education || 'Board Certified'}
                      </span>
                      <span className="flex items-center gap-1.5">
                        <MapPin className="w-4 h-4 text-slate-400" />
                        Medical Center, NY
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 bg-amber-50 px-3 py-2 rounded-xl border border-amber-100 shrink-0">
                    <Star className="w-5 h-5 fill-amber-500 text-amber-500" />
                    <div>
                      <div className="font-bold text-amber-900 leading-none">{doctor.rating || '4.9'}</div>
                      <div className="text-xs text-amber-700 mt-0.5">{doctor.reviews_count || '120'} reviews</div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Quick Stats Grid */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-8 pt-8 border-t border-slate-100">
              <div className="bg-slate-50 rounded-xl p-4 text-center">
                <div className="text-slate-500 text-xs font-medium uppercase tracking-wider mb-1">Experience</div>
                <div className="text-lg font-bold text-slate-900">{doctor.experience_years || '10+'} Years</div>
              </div>
              <div className="bg-slate-50 rounded-xl p-4 text-center">
                <div className="text-slate-500 text-xs font-medium uppercase tracking-wider mb-1">Patients</div>
                <div className="text-lg font-bold text-slate-900">2,000+</div>
              </div>
              <div className="bg-slate-50 rounded-xl p-4 text-center">
                <div className="text-slate-500 text-xs font-medium uppercase tracking-wider mb-1">Languages</div>
                <div className="text-lg font-bold text-slate-900 truncate">
                  {(doctor.languages || ['English']).join(', ')}
                </div>
              </div>
              <div className="bg-slate-50 rounded-xl p-4 text-center">
                <div className="text-slate-500 text-xs font-medium uppercase tracking-wider mb-1">Consultation</div>
                <div className="text-lg font-bold text-emerald-600">${doctor.consultation_fee || '150'}</div>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            
            {/* Left Column: Bio & Reviews */}
            <div className="lg:col-span-2 space-y-6">
              {/* About Section */}
              <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 md:p-8">
                <h3 className="text-lg font-display font-bold text-slate-900 mb-4">About {doctor.name}</h3>
                <p className="text-slate-600 leading-relaxed font-body">
                  {doctor.bio || `${doctor.name} is a dedicated medical professional committed to providing exceptional patient care. With extensive experience in their field, they focus on comprehensive diagnosis and personalized treatment plans.`}
                </p>
              </div>

              {/* Reviews Section */}
              <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 md:p-8">
                <div className="flex items-center justify-between mb-6">
                  <h3 className="text-lg font-display font-bold text-slate-900">Patient Reviews</h3>
                  <span className="text-sm font-medium text-sky-600 cursor-pointer hover:underline">View all</span>
                </div>
                
                {reviews.length > 0 ? (
                  <div className="space-y-6">
                    {reviews.slice(0, 3).map((review) => (
                      <div key={review.id} className="border-b border-slate-100 last:border-0 pb-6 last:pb-0">
                        <div className="flex items-center justify-between mb-2">
                          <div className="font-medium text-slate-900">{review.author}</div>
                          <div className="flex items-center gap-1">
                            {[...Array(5)].map((_, i) => (
                              <Star 
                                key={i} 
                                className={`w-3.5 h-3.5 ${i < Math.floor(review.rating) ? 'fill-amber-400 text-amber-400' : 'fill-slate-200 text-slate-200'}`} 
                              />
                            ))}
                          </div>
                        </div>
                        <p className="text-sm text-slate-600 italic">"{review.text}"</p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-8 bg-slate-50 rounded-xl border border-slate-100">
                    <Star className="w-8 h-8 text-slate-300 mx-auto mb-2" />
                    <p className="text-slate-500 text-sm">No reviews available yet.</p>
                  </div>
                )}
              </div>
            </div>

            {/* Right Column: Booking Calendar */}
            <div className="lg:col-span-1">
              <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 sticky top-24">
                <h3 className="text-lg font-display font-bold text-slate-900 mb-1">Book Appointment</h3>
                <p className="text-sm text-slate-500 mb-6">Select a date and time</p>

                {/* Date Selector */}
                <div className="mb-6">
                  <div className="flex gap-2 overflow-x-auto pb-2 no-scrollbar -mx-2 px-2">
                    {availableDates.map((date) => (
                      <button
                        key={date.id}
                        onClick={() => {
                          setSelectedDate(date.id)
                          setSelectedTime(null) // Reset time when date changes
                        }}
                        className={`flex flex-col items-center justify-center min-w-[4.5rem] py-3 rounded-xl border transition-all ${
                          selectedDate === date.id
                            ? 'bg-sky-600 border-sky-600 text-white shadow-md'
                            : 'bg-white border-slate-200 text-slate-600 hover:border-sky-300 hover:bg-sky-50'
                        }`}
                      >
                        <span className={`text-xs font-medium mb-1 ${selectedDate === date.id ? 'text-sky-100' : 'text-slate-400'}`}>
                          {date.dayName}
                        </span>
                        <span className="text-lg font-bold leading-none mb-1">{date.dayNumber}</span>
                        <span className={`text-[10px] uppercase tracking-wider ${selectedDate === date.id ? 'text-sky-100' : 'text-slate-400'}`}>
                          {date.month}
                        </span>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Time Selector */}
                <div>
                  <div className="flex items-center gap-2 mb-3 text-sm font-medium text-slate-700">
                    <Clock className="w-4 h-4 text-slate-400" />
                    Available Times
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    {mockTimeSlots.map((time, idx) => (
                      <button
                        key={idx}
                        onClick={() => setSelectedTime(time)}
                        className={`py-2.5 px-3 text-sm font-medium rounded-lg border transition-all ${
                          selectedTime === time
                            ? 'bg-sky-50 border-sky-600 text-sky-700 ring-1 ring-sky-600'
                            : 'bg-white border-slate-200 text-slate-600 hover:border-sky-300 hover:bg-sky-50'
                        }`}
                      >
                        {time}
                      </button>
                    ))}
                  </div>
                </div>

              </div>
            </div>

          </div>
        </div>
      </div>

      {/* Sticky Bottom Bar for Mobile/Desktop CTA */}
      <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-slate-200 p-4 shadow-[0_-4px_6px_-1px_rgba(0,0,0,0.05)] z-40">
        <div className="max-w-4xl mx-auto flex items-center justify-between gap-4">
          <div className="hidden sm:block">
            <div className="text-sm text-slate-500 font-medium">Consultation Fee</div>
            <div className="text-xl font-bold text-slate-900">${doctor.consultation_fee || '150'}</div>
          </div>
          
          <div className="flex-1 sm:flex-none flex items-center gap-3">
            <div className="sm:hidden flex-1">
              <div className="text-xs text-slate-500 font-medium">Fee</div>
              <div className="text-lg font-bold text-slate-900">${doctor.consultation_fee || '150'}</div>
            </div>
            <Link 
              to={`/book/${doctor.id}`} 
              className={`flex-1 sm:flex-none ${!selectedTime ? 'pointer-events-none' : ''}`}
            >
              <Button 
                variant="primary" 
                size="lg" 
                className="w-full sm:w-auto px-8 shadow-md"
                disabled={!selectedTime}
              >
                {selectedTime ? 'Continue to Book' : 'Select a Time'}
              </Button>
            </Link>
          </div>
        </div>
      </div>
    </AppShell>
  )
}