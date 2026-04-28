import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { getDoctors, getSpecialties } from '../api/endpoints.js'
import Navbar from '../components/Navbar.jsx'
import FilterSidebar from '../components/FilterSidebar.jsx'
import DoctorCard from '../components/DoctorCard.jsx'
import Footer from '../components/Footer.jsx'

export default function DoctorDirectory() {
  const [searchParams, setSearchParams] = useSearchParams()
  const selectedSpecialty = searchParams.get('specialty') || ''

  const [doctors, setDoctors] = useState([])
  const [specialties, setSpecialties] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    const fetchSpecialties = async () => {
      try {
        const data = await getSpecialties()
        setSpecialties(data)
      } catch (err) {
        console.error("Failed to fetch specialties", err)
      }
    }
    fetchSpecialties()
  }, [])

  useEffect(() => {
    const fetchDoctors = async () => {
      setLoading(true)
      setError(null)
      try {
        const params = selectedSpecialty ? { specialty: selectedSpecialty } : {}
        const data = await getDoctors(params)
        setDoctors(data)
      } catch (err) {
        console.error("Failed to fetch doctors", err)
        setError("Failed to load doctors. Please try again later.")
      } finally {
        setLoading(false)
      }
    }
    fetchDoctors()
  }, [selectedSpecialty])

  const handleSelectSpecialty = (specialtyName) => {
    if (specialtyName) {
      setSearchParams({ specialty: specialtyName })
    } else {
      setSearchParams({})
    }
  }

  return (
    <div className="min-h-screen flex flex-col bg-gray-50">
      <Navbar />
      
      <main className="flex-grow max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 w-full">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 tracking-tight">Find a Doctor</h1>
          <p className="mt-2 text-lg text-gray-600 max-w-2xl">
            Browse our network of top-rated healthcare professionals and book your consultation today.
          </p>
        </div>

        <div className="flex flex-col md:flex-row gap-8 items-start">
          <aside className="w-full md:w-64 shrink-0">
            <FilterSidebar 
              specialties={specialties} 
              selectedSpecialty={selectedSpecialty} 
              onSelectSpecialty={handleSelectSpecialty} 
            />
          </aside>

          <section className="flex-grow w-full">
            {loading ? (
              <div className="flex justify-center items-center h-64">
                <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600"></div>
              </div>
            ) : error ? (
              <div className="bg-red-50 text-red-700 p-4 rounded-xl border border-red-100 flex items-center">
                <p>{error}</p>
              </div>
            ) : doctors.length === 0 ? (
              <div className="bg-white p-12 rounded-xl border border-gray-200 text-center shadow-sm">
                <h3 className="text-lg font-medium text-gray-900 mb-2">No doctors found</h3>
                <p className="text-gray-500 mb-6">
                  We couldn't find any doctors matching the selected specialty.
                </p>
                <button 
                  onClick={() => handleSelectSpecialty('')}
                  className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                >
                  Clear filters
                </button>
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
                {doctors.map(doctor => (
                  <DoctorCard key={doctor.id} doctor={doctor} />
                ))}
              </div>
            )}
          </section>
        </div>
      </main>

      <Footer />
    </div>
  )
}