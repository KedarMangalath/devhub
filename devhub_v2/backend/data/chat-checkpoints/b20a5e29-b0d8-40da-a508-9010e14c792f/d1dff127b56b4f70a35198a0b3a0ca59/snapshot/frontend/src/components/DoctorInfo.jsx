import React from 'react'
import { Star, Award, MapPin } from 'lucide-react'

const DoctorInfo = ({ doctor }) => {
  if (!doctor) return null

  const doctorName = doctor.user?.full_name || doctor.full_name || 'Unknown Doctor'
  const specialtyName = doctor.specialty?.name || doctor.specialty || 'General Practice'
  const imageUrl = doctor.image_url || `https://picsum.photos/seed/doctor-${doctor.id || 'default'}/300/200`
  const rating = doctor.rating || '4.9'
  const reviewsCount = doctor.reviews_count || Math.floor(Math.random() * 200) + 50
  const experience = doctor.experience_years || 10
  const address = doctor.clinic_address || 'Omnia Medical Center, Suite 400'
  const bio = doctor.bio || `Dr. ${doctorName} is a highly respected specialist in ${specialtyName} with over ${experience} years of clinical experience. Dedicated to providing compassionate, patient-centered care, they utilize the latest medical advancements to ensure optimal health outcomes for all patients.`

  return (
    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6 md:p-8 mb-8">
      <div className="flex flex-col md:flex-row gap-8">
        <div className="flex-shrink-0 mx-auto md:mx-0">
          <img
            src={imageUrl}
            alt={`Dr. ${doctorName}`}
            className="w-48 h-48 md:w-56 md:h-56 rounded-2xl object-cover shadow-sm border border-gray-50"
          />
        </div>

        <div className="flex-grow flex flex-col justify-center">
          <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-4 gap-4">
            <div>
              <h1 className="text-3xl font-bold text-gray-900 mb-1">
                Dr. {doctorName}
              </h1>
              <p className="text-lg text-blue-600 font-medium">
                {specialtyName}
              </p>
            </div>
            <div className="flex items-center bg-yellow-50 px-4 py-2 rounded-xl border border-yellow-100">
              <Star className="w-5 h-5 text-yellow-500 fill-current mr-2" />
              <div className="flex flex-col">
                <span className="font-bold text-yellow-700 leading-none">{rating} Rating</span>
                <span className="text-yellow-600 text-xs mt-1 leading-none">{reviewsCount} reviews</span>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
            <div className="flex items-center text-gray-700 bg-gray-50 p-3 rounded-xl">
              <Award className="w-5 h-5 mr-3 text-blue-500 flex-shrink-0" />
              <span className="font-medium">{experience} Years Experience</span>
            </div>
            <div className="flex items-center text-gray-700 bg-gray-50 p-3 rounded-xl">
              <MapPin className="w-5 h-5 mr-3 text-blue-500 flex-shrink-0" />
              <span className="font-medium truncate">{address}</span>
            </div>
          </div>

          <div className="border-t border-gray-100 pt-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-3">About the Doctor</h3>
            <p className="text-gray-600 leading-relaxed">
              {bio}
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

export default DoctorInfo