import { useState, useMemo } from 'react'
import { Search, Filter, Sparkles } from 'lucide-react'
import AppShell from '../components/layout/AppShell'
import DoctorCard from '../components/domain/DoctorCard'
import Button from '../components/ui/Button'
import { doctors, specialties } from '../mockData'

export default function DoctorDirectory() {
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedSpecialty, setSelectedSpecialty] = useState('all')

  const filteredDoctors = useMemo(() => {
    return doctors.filter(doctor => {
      const matchesSearch = 
        doctor.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        doctor.specialty_name.toLowerCase().includes(searchQuery.toLowerCase())
      
      const matchesSpecialty = 
        selectedSpecialty === 'all' || doctor.specialty_id === selectedSpecialty
      
      return matchesSearch && matchesSpecialty
    })
  }, [searchQuery, selectedSpecialty])

  return (
    <AppShell>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 w-full animate-in fade-in duration-500">
        
        {/* Directory Header */}
        <div className="mb-8">
          <h1 className="text-3xl md:text-4xl font-display font-bold text-slate-900 tracking-tight mb-3">
            Find a Specialist
          </h1>
          <p className="text-slate-600 max-w-2xl text-lg">
            Book appointments with top-rated medical professionals. Available today for online video consultations or in-person clinic visits.
          </p>
        </div>

        {/* AI Suggestion Banner */}
        <div className="bg-gradient-to-r from-sky-50 via-white to-indigo-50 border border-sky-100/50 rounded-2xl p-6 mb-10 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-6 shadow-sm relative overflow-hidden group">
          <div className="absolute top-0 right-0 -mt-4 -mr-4 w-24 h-24 bg-sky-200/20 rounded-full blur-2xl group-hover:bg-sky-300/30 transition-colors duration-700"></div>
          
          <div className="flex items-start gap-5 relative z-10">
            <div className="bg-white p-3.5 rounded-xl shadow-sm border border-sky-50 text-sky-600 shrink-0">
              <Sparkles className="w-6 h-6" />
            </div>
            <div>
              <h3 className="text-lg font-display font-semibold text-slate-900 mb-1.5">
                Not sure who to see? Let AI triage you.
              </h3>
              <p className="text-slate-600 text-sm leading-relaxed max-w-xl">
                Describe your symptoms to our intelligent health assistant. We'll instantly match you with the right specialist and suggest available times.
              </p>
            </div>
          </div>
          <Button variant="primary" className="shrink-0 whitespace-nowrap relative z-10 shadow-sky-200/50 shadow-lg">
            Start AI Triage
          </Button>
        </div>

        {/* Search and Filter Bar */}
        <div className="mb-10 space-y-6">
          <div className="relative max-w-2xl">
            <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
              <Search className="h-5 w-5 text-slate-400" />
            </div>
            <input
              type="text"
              className="block w-full pl-11 pr-4 py-3.5 border border-slate-200 rounded-xl leading-5 bg-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500 sm:text-sm transition-all shadow-sm hover:border-slate-300"
              placeholder="Search by doctor name, condition, or specialty..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>

          <div className="flex items-center gap-2.5 overflow-x-auto pb-2 no-scrollbar -mx-4 px-4 sm:mx-0 sm:px-0">
            <button
              onClick={() => setSelectedSpecialty('all')}
              className={`whitespace-nowrap px-4 py-2 rounded-full text-sm font-medium transition-all duration-200 ${
                selectedSpecialty === 'all'
                  ? 'bg-slate-800 text-white shadow-md shadow-slate-200'
                  : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-50 hover:border-slate-300'
              }`}
            >
              All Specialists
            </button>
            {specialties.map((specialty) => (
              <button
                key={specialty.id}
                onClick={() => setSelectedSpecialty(specialty.id)}
                className={`whitespace-nowrap px-4 py-2 rounded-full text-sm font-medium transition-all duration-200 ${
                  selectedSpecialty === specialty.id
                    ? 'bg-sky-600 text-white shadow-md shadow-sky-200'
                    : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-50 hover:border-slate-300'
                }`}
              >
                {specialty.name}
              </button>
            ))}
          </div>
        </div>

        {/* Doctor List Grid */}
        {filteredDoctors.length > 0 ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
            {filteredDoctors.map(doctor => (
              <DoctorCard key={doctor.id} doctor={doctor} />
            ))}
          </div>
        ) : (
          <div className="text-center py-20 bg-white rounded-2xl border border-slate-200 shadow-sm flex flex-col items-center justify-center">
            <div className="w-16 h-16 bg-slate-50 rounded-full flex items-center justify-center mb-5 border border-slate-100">
              <Filter className="w-8 h-8 text-slate-400" />
            </div>
            <h3 className="text-xl font-display font-semibold text-slate-900 mb-2">No doctors found</h3>
            <p className="text-slate-500 max-w-md mx-auto mb-8">
              We couldn't find any medical professionals matching your current search and filter criteria. Try adjusting your terms to see more results.
            </p>
            <Button 
              variant="outline" 
              onClick={() => {
                setSearchQuery('')
                setSelectedSpecialty('all')
              }}
              className="min-w-[160px]"
            >
              Clear all filters
            </Button>
          </div>
        )}
      </div>
    </AppShell>
  )
}