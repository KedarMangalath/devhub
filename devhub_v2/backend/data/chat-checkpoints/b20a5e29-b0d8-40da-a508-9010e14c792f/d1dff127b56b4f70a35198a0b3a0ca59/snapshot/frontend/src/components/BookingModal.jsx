import { useState } from 'react'
import { X } from 'lucide-react'

export default function BookingModal({ isOpen, onClose, doctor, slot, onConfirm }) {
  const [consultationType, setConsultationType] = useState('video')
  const [notes, setNotes] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  if (!isOpen) return null

  const handleConfirm = async (e) => {
    e.preventDefault()
    setIsSubmitting(true)
    try {
      await onConfirm({
        consultation_type: consultationType,
        notes: notes
      })
    } finally {
      setIsSubmitting(false)
    }
  }

  const formatDateTime = (slotData) => {
    if (!slotData) return ''
    const dateStr = typeof slotData === 'string' ? slotData : slotData.start_time
    if (!dateStr) return ''
    
    const dateObj = new Date(dateStr)
    const date = dateObj.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })
    const time = dateObj.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })
    return `${date} at ${time}`
  }

  const doctorName = doctor?.user?.full_name || doctor?.full_name || 'Doctor'
  const doctorSpecialty = doctor?.specialty || 'Specialist'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50 p-4 backdrop-blur-sm">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-md overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        <div className="flex justify-between items-center p-5 border-b border-gray-100">
          <h2 className="text-xl font-semibold text-gray-800">Confirm Appointment</h2>
          <button 
            onClick={onClose} 
            className="text-gray-400 hover:text-gray-600 hover:bg-gray-100 p-1 rounded-full transition-colors"
            aria-label="Close modal"
          >
            <X size={24} />
          </button>
        </div>

        <form onSubmit={handleConfirm} className="p-5 space-y-5">
          <div className="bg-blue-50 p-4 rounded-lg border border-blue-100">
            <p className="font-semibold text-blue-900">Dr. {doctorName}</p>
            <p className="text-sm text-blue-700 mb-2">{doctorSpecialty}</p>
            <div className="flex items-center text-sm text-blue-800 font-medium bg-blue-100/50 inline-block px-2 py-1 rounded">
              {formatDateTime(slot)}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-3">
              Consultation Type
            </label>
            <div className="grid grid-cols-2 gap-3">
              <label className={`border rounded-lg p-3 flex items-center justify-center cursor-pointer transition-all ${consultationType === 'video' ? 'border-blue-500 bg-blue-50 ring-1 ring-blue-500' : 'border-gray-200 hover:bg-gray-50'}`}>
                <input
                  type="radio"
                  name="consultation_type"
                  value="video"
                  checked={consultationType === 'video'}
                  onChange={(e) => setConsultationType(e.target.value)}
                  className="sr-only"
                />
                <span className={`text-sm font-medium ${consultationType === 'video' ? 'text-blue-700' : 'text-gray-600'}`}>
                  Video Call
                </span>
              </label>
              <label className={`border rounded-lg p-3 flex items-center justify-center cursor-pointer transition-all ${consultationType === 'in-person' ? 'border-blue-500 bg-blue-50 ring-1 ring-blue-500' : 'border-gray-200 hover:bg-gray-50'}`}>
                <input
                  type="radio"
                  name="consultation_type"
                  value="in-person"
                  checked={consultationType === 'in-person'}
                  onChange={(e) => setConsultationType(e.target.value)}
                  className="sr-only"
                />
                <span className={`text-sm font-medium ${consultationType === 'in-person' ? 'text-blue-700' : 'text-gray-600'}`}>
                  In-Person
                </span>
              </label>
            </div>
          </div>

          <div>
            <label htmlFor="notes" className="block text-sm font-medium text-gray-700 mb-1">
              Reason for visit / Notes
            </label>
            <textarea
              id="notes"
              rows="3"
              className="w-full border border-gray-300 rounded-lg p-3 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-all resize-none"
              placeholder="Briefly describe your symptoms or reason for consultation..."
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              required
            ></textarea>
          </div>

          <div className="pt-2 flex gap-3">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2.5 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors font-medium"
              disabled={isSubmitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="flex-1 px-4 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium disabled:opacity-70 flex justify-center items-center"
              disabled={isSubmitting}
            >
              {isSubmitting ? 'Confirming...' : 'Confirm Booking'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}