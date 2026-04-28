import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { getSpecialties, getDoctors } from '../api/endpoints.js'
import Navbar from '../components/Navbar.jsx'
import HeroSearch from '../components/HeroSearch.jsx'
import SpecialtyGrid from '../components/SpecialtyGrid.jsx'
import TopDoctorsCarousel from '../components/TopDoctorsCarousel.jsx'
import Footer from '../components/Footer.jsx'

export default function Home() {
  const [specialties, setSpecialties] = useState([])
  const [doctors, setDoctors] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    let isMounted = true

    const fetchHomeData = async () => {
      try {
        setIsLoading(true)
        const [specialtiesData, doctorsData] = await Promise.all([
          getSpecialties(),
          getDoctors({ limit: 10 })
        ])
        
        if (isMounted) {
          setSpecialties(specialtiesData)
          setDoctors(doctorsData)
        }
      } catch (error) {
        console.error('Failed to fetch home page data:', error)
      } finally {
        if (isMounted) {
          setIsLoading(false)
        }
      }
    }

    fetchHomeData()

    return () => {
      isMounted = false
    }
  }, [])

  const handleSearch = (query) => {
    if (query && query.trim() !== '') {
      navigate(`/doctors?search=${encodeURIComponent(query.trim())}`)
    } else {
      navigate('/doctors')
    }
  }

  return (
    <div className="min-h-screen flex flex-col bg-gray-50 font-sans">
      <Navbar />
      
      <main className="flex-grow">
        <HeroSearch onSearch={handleSearch} />
        
        {/* Specialties Section */}
        <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16 lg:py-24">
          <div className="mb-10 text-center sm:text-left">
            <h2 className="text-3xl font-extrabold text-gray-900 tracking-tight sm:text-4xl">
              Browse by Specialty
            </h2>
            <p className="mt-4 text-lg text-gray-500 max-w-2xl">
              Find experienced doctors across all major medical specialties. Select a category to see available specialists.
            </p>
          </div>
          
          {isLoading ? (
            <div className="flex justify-center items-center py-20">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
            </div>
          ) : (
            <SpecialtyGrid specialties={specialties} />
          )}
        </section>

        {/* Top Doctors Section */}
        <section className="bg-white py-16 lg:py-24 border-t border-gray-200">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="mb-10 flex flex-col sm:flex-row sm:justify-between sm:items-end gap-4">
              <div className="max-w-2xl">
                <h2 className="text-3xl font-extrabold text-gray-900 tracking-tight sm:text-4xl">
                  Top Rated Doctors
                </h2>
                <p className="mt-4 text-lg text-gray-500">
                  Book appointments with our most highly recommended healthcare professionals.
                </p>
              </div>
              <button 
                onClick={() => navigate('/doctors')}
                className="hidden sm:inline-flex items-center text-blue-600 hover:text-blue-800 font-semibold transition-colors"
              >
                View all doctors <span aria-hidden="true" className="ml-1">&rarr;</span>
              </button>
            </div>
            
            {isLoading ? (
              <div className="flex justify-center items-center py-20">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
              </div>
            ) : (
              <TopDoctorsCarousel doctors={doctors} />
            )}
            
            <div className="mt-10 sm:hidden flex justify-center">
              <button 
                onClick={() => navigate('/doctors')}
                className="inline-flex items-center px-6 py-3 border border-gray-300 shadow-sm text-base font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
              >
                View all doctors
              </button>
            </div>
          </div>
        </section>
      </main>

      <Footer />
    </div>
  )
}