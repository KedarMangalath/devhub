import { Link } from 'react-router-dom'
import { Star, Clock, DollarSign } from 'lucide-react'

export default function DoctorCard({ doctor }) {
  if (!doctor) return null;

  const name = doctor.user?.full_name || doctor.full_name || 'Unknown Doctor';
  const specialty = doctor.specialty?.name || doctor.specialty || 'General Practice';
  const experience = doctor.experience_years || 0;
  const fee = doctor.consultation_fee || 0;
  const rating = doctor.rating || '4.8';
  const doctorId = doctor.id || 'default';

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden hover:shadow-md transition-shadow duration-300 flex flex-col h-full">
      <div className="relative h-48 w-full bg-gray-100 shrink-0">
        <img
          src={`https://picsum.photos/seed/doctor-${doctorId}/300/200`}
          alt={name}
          className="w-full h-full object-cover"
          loading="lazy"
        />
        <div className="absolute top-3 right-3 bg-white/90 backdrop-blur-sm px-2 py-1 rounded-lg flex items-center gap-1 text-sm font-medium text-gray-700 shadow-sm">
          <Star className="w-4 h-4 text-yellow-400 fill-yellow-400" />
          <span>{rating}</span>
        </div>
      </div>

      <div className="p-5 flex flex-col flex-grow">
        <div className="mb-4">
          <h3 className="text-lg font-semibold text-gray-900 line-clamp-1" title={name}>
            {name}
          </h3>
          <p className="text-sm text-blue-600 font-medium mt-1">{specialty}</p>
        </div>

        <div className="space-y-3 mb-6 flex-grow">
          <div className="flex items-center text-sm text-gray-600">
            <Clock className="w-4 h-4 mr-3 text-gray-400 shrink-0" />
            <span>{experience} Years Experience</span>
          </div>
          <div className="flex items-center text-sm text-gray-600">
            <DollarSign className="w-4 h-4 mr-3 text-gray-400 shrink-0" />
            <span>${fee} Consultation Fee</span>
          </div>
        </div>

        <Link
          to={`/doctors/${doctorId}`}
          className="w-full inline-flex justify-center items-center px-4 py-2.5 bg-blue-50 text-blue-700 text-sm font-semibold rounded-lg hover:bg-blue-600 hover:text-white transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 mt-auto"
        >
          View Profile
        </Link>
      </div>
    </div>
  )
}