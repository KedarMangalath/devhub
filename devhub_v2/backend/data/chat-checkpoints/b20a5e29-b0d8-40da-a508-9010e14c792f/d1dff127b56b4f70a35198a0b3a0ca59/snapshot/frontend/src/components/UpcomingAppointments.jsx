import { Video, Calendar, Clock } from 'lucide-react'
import { Link } from 'react-router-dom'

export default function UpcomingAppointments({ appointments = [] }) {
  if (!appointments || appointments.length === 0) {
    return (
      <div className="bg-white rounded-xl shadow-sm p-8 text-center border border-gray-100">
        <p className="text-gray-500">No upcoming appointments found.</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {appointments.map((appointment) => {
        const doctorName = appointment.doctor?.user?.full_name || appointment.doctor_name || 'Doctor'
        const isVideo = appointment.type === 'video'
        const isScheduled = appointment.status === 'scheduled'

        return (
          <div 
            key={appointment.id} 
            className="bg-white rounded-xl shadow-sm p-5 border border-gray-100 flex flex-col md:flex-row md:items-center justify-between gap-4 hover:shadow-md transition-shadow"
          >
            <div className="flex-1">
              <h4 className="text-lg font-bold text-gray-900">Dr. {doctorName}</h4>
              <p className="text-sm text-gray-500 mb-3">
                {appointment.doctor?.specialty || 'Consultation'}
              </p>
              
              <div className="flex flex-wrap items-center gap-4 text-sm text-gray-700">
                <div className="flex items-center gap-1.5 bg-blue-50 px-2.5 py-1 rounded-md text-blue-700 font-medium">
                  <Calendar className="w-4 h-4" />
                  <span>{appointment.date ? new Date(appointment.date).toLocaleDateString() : 'TBD'}</span>
                </div>
                <div className="flex items-center gap-1.5 bg-blue-50 px-2.5 py-1 rounded-md text-blue-700 font-medium">
                  <Clock className="w-4 h-4" />
                  <span>{appointment.time || 'TBD'}</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className={`px-2.5 py-1 rounded-md text-xs font-bold uppercase tracking-wider ${
                    isScheduled ? 'bg-green-100 text-green-800' :
                    appointment.status === 'completed' ? 'bg-gray-100 text-gray-600' :
                    'bg-red-100 text-red-800'
                  }`}>
                    {appointment.status || 'Unknown'}
                  </span>
                </div>
              </div>
            </div>

            {isScheduled && isVideo && (
              <div className="mt-2 md:mt-0 shrink-0">
                <Link
                  to={`/teleconsultation/${appointment.id}`}
                  className="inline-flex items-center justify-center gap-2 px-5 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-semibold text-sm w-full md:w-auto shadow-sm hover:shadow"
                >
                  <Video className="w-4 h-4" />
                  Join Call
                </Link>
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}