import { useState } from 'react'
import { Search } from 'lucide-react'

export default function HeroSearch({ onSearch }) {
  const [query, setQuery] = useState('')

  const handleSubmit = (e) => {
    e.preventDefault()
    if (onSearch) {
      onSearch(query)
    }
  }

  return (
    <div className="relative bg-blue-600 text-white overflow-hidden">
      <div className="absolute inset-0 opacity-20">
        <img
          src="https://picsum.photos/seed/omnia-hero/1920/800"
          alt="Medical professionals"
          className="w-full h-full object-cover"
        />
        <div className="absolute inset-0 bg-blue-900 mix-blend-multiply"></div>
      </div>

      <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-24 lg:py-32">
        <div className="text-center max-w-3xl mx-auto">
          <h1 className="text-4xl font-extrabold tracking-tight sm:text-5xl lg:text-6xl">
            Find and Book the Best Doctors
          </h1>
          <p className="mt-6 text-xl text-blue-100 max-w-2xl mx-auto">
            Access top-rated specialists, secure teleconsultations, and manage your digital health records all in one place.
          </p>

          <div className="mt-10 max-w-2xl mx-auto">
            <form 
              onSubmit={handleSubmit} 
              className="w-full flex flex-col sm:flex-row shadow-xl rounded-lg overflow-hidden bg-white"
            >
              <div className="relative flex-grow">
                <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                  <Search className="h-6 w-6 text-gray-400" aria-hidden="true" />
                </div>
                <input
                  type="text"
                  name="search"
                  id="search"
                  className="block w-full pl-12 pr-4 py-4 text-gray-900 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 sm:text-lg border-0"
                  placeholder="Search doctors, specialties, or symptoms..."
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                />
              </div>
              <button
                type="submit"
                className="w-full sm:w-auto px-10 py-4 bg-blue-900 text-white text-lg font-semibold hover:bg-blue-800 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-blue-500 transition-colors"
              >
                Search
              </button>
            </form>
            <div className="mt-4 flex flex-wrap justify-center gap-2 text-sm text-blue-200">
              <span>Popular:</span>
              <button onClick={() => onSearch('Cardiologist')} className="hover:text-white underline decoration-blue-400 underline-offset-2">Cardiologist</button>
              <button onClick={() => onSearch('Dermatologist')} className="hover:text-white underline decoration-blue-400 underline-offset-2">Dermatologist</button>
              <button onClick={() => onSearch('Pediatrician')} className="hover:text-white underline decoration-blue-400 underline-offset-2">Pediatrician</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}