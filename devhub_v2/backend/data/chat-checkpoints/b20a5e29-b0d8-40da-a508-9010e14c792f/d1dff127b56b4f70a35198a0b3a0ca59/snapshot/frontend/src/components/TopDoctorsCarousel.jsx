import { Star } from 'lucide-react'
import { Link } from 'react-router-dom'

export default function TopDoctorsCarousel({ doctors = [] }) {
  if (!doctors || doctors.length === 0) {
    return (
      <div className="text-center py-10 bg-gray-50 rounded-2xl border border-gray-100 text-gray-500">
        No featured doctors available at the moment.
      </div>
    )
  }

  return (
    <div className="w-full relative">
      <div 
        className="flex overflow-x-auto gap-6 pb-6 pt-2 snap-x snap-mandatory" 
        style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}
      >
        {doctors.map((doctor) => (
          <Link
            key={doctor.id}
            to={`/doctors/${doctor.id}`}
            className="snap-start shrink-0 w-72 bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden hover:shadow-lg hover:border-blue-100 transition-all duration-200 group flex flex-col"
          >
            <div className="h-48 overflow-hidden relative bg-gray-100">
              <img
                src={`https://picsum.photos/seed/doctor-${doctor.id}/300/200`}
                alt={doctor.full_name || 'Doctor'}
                className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
              />
              <div className="absolute top-3 right-3 bg-white/90 backdrop-blur-sm px-2 py-1 rounded-lg flex items-center shadow-sm">
                <Star className="w-3.5 h-3.5 text-yellow-500 fill-yellow-500 mr-1" />
                <span className="text-xs font-bold text-gray-700">{doctor.rating || '4.8'}</span>
              </div>
            </div>
            
            <div className="p-5 flex flex-col flex-grow">
              <h3 className="font-bold text-lg text-gray-900 mb-1 truncate group-hover:text-blue-600 transition-colors">
                {doctor.full_name || 'Dr. Unknown'}
              </h3>
              <p className="text-sm text-blue-600 font-medium mb-3 truncate">
                {doctor.specialty || 'Specialist'}
              </p>
              
              <div className="mt-auto pt-4 border-t border-gray-50 flex items-center justify-between">
                <div className="text-sm text-gray-500">
                  <span className="font-semibold text-gray-700">{doctor.experience_years || 5}+</span> yrs exp
                </div>
                <span className="text-sm font-semibold text-blue-600 bg-blue-50 px-3 py-1.5 rounded-full group-hover:bg-blue-600 group-hover:text-white transition-colors">
                  Book
                </span>
              </div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  )
}