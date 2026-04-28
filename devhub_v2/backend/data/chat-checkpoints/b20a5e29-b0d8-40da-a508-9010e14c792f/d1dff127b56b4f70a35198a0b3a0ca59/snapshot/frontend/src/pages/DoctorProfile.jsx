import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getDoctor, getDoctorSlots, createAppointment } from '../api/endpoints.js'
import Navbar from '../components/Navbar.jsx'
import DoctorInfo from '../components/DoctorInfo.jsx'
import TimeSlotPicker from '../components/TimeSlotPicker.jsx'
import BookingModal from '../components/BookingModal.jsx'
import Footer from '../components/Footer.jsx'

export default function DoctorProfile() {
  const { id } = useParams()
  const navigate = useNavigate()
  
  const [doctor, setDoctor] = useState(null)
  const [slots, setSlots] = useState([])
  const [selectedSlot, setSelectedSlot] = useState(null)
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    const fetchDoctorData = async () => {
      try {
        setLoading(true)
        setError(null)
        const [doctorData, slotsData] = await Promise.all([
          getDoctor(id),
          getDoctorSlots(id)
        ])
        setDoctor(doctorData)
        setSlots(slotsData)
      } catch (err) {
        console.error('Error fetching doctor details:', err)
        setError('Failed to load doctor profile. Please try again later.')
      } finally {
        setLoading(false)
      }
    }

    if (id) {
      fetchDoctorData()
    }
  }, [id])

  const handleSelectSlot = (slotDatetime) => {
    setSelectedSlot(slotDatetime)
    setIsModalOpen(true)
  }

  const handleConfirmBooking = async (bookingData) => {
    try {
      await createAppointment({
        doctor_id: parseInt(id, 10),
        datetime: selectedSlot,
        ...bookingData
      })
      setIsModalOpen(false)
      navigate('/dashboard')
    } catch (err) {
      console.error('Failed to book appointment:', err)
      alert('Failed to book appointment. Please ensure you are logged in and try again.')
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen flex flex-col bg-gray-50">
        <Navbar />
        <main className="flex-grow flex items-center justify-center">
          <div className="flex flex-col items-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mb-4"></div>
            <p className="text-gray-500 font-medium">Loading doctor profile...</p>
          </div>
        </main>
        <Footer />
      </div>
    )
  }

  if (error || !doctor) {
    return (
      <div className="min-h-screen flex flex-col bg-gray-50">
        <Navbar />
        <main className="flex-grow flex items-center justify-center px-4">
          <div className="text-center bg-white p-8 rounded-2xl shadow-sm border border-gray-100 max-w-md w-full">
            <h2 className="text-2xl font-bold text-gray-900 mb-2">Profile Not Found</h2>
            <p className="text-gray-600 mb-6">{error || 'The doctor you are looking for does not exist.'}</p>
            <button 
              onClick={() => navigate('/doctors')}
              className="w-full px-4 py-2 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 transition-colors"
            >
              Back to Directory
            </button>
          </div>
        </main>
        <Footer />
      </div>
    )
  }

  return (
    <div className="min-h-screen flex flex-col bg-gray-50">
      <Navbar />
      
      <main className="flex-grow max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 w-full">
        <DoctorInfo doctor={doctor} />
        
        <div className="mt-8 bg-white rounded-2xl shadow-sm border border-gray-100 p-6 md:p-8">
          <div className="mb-6">
            <h2 className="text-2xl font-bold text-gray-900">Book an Appointment</h2>
            <p className="text-gray-500 mt-1">Select an available time slot to schedule your consultation.</p>
          </div>
          
          <TimeSlotPicker 
            slots={slots} 
            selectedSlot={selectedSlot} 
            onSelectSlot={handleSelectSlot} 
          />
        </div>
      </main>

      <BookingModal 
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        doctor={doctor}
        slot={selectedSlot}
        onConfirm={handleConfirmBooking}
      />

      <Footer />
    </div>
  )
}