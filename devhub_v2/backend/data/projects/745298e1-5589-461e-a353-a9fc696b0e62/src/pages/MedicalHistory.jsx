import { useState, useMemo } from 'react'
import { Filter, Download, FileText } from 'lucide-react'
import AppShell from '../components/layout/AppShell'
import AppointmentCard from '../components/domain/AppointmentCard'
import Button from '../components/ui/Button'
import { getPatientAppointments } from '../mockData'

export default function MedicalHistory() {
  const [filter, setFilter] = useState('all')
  
  // Fetch all appointments and filter out upcoming ones to only show history
  const allAppointments = getPatientAppointments()
  
  const historyAppointments = useMemo(() => {
    return allAppointments
      .filter(app => app.status !== 'upcoming')
      .sort((a, b) => new Date(b.date) - new Date(a.date))
  }, [allAppointments])

  // Apply the active tab filter
  const filteredAppointments = useMemo(() => {
    if (filter === 'all') return historyAppointments
    return historyAppointments.filter(app => app.status === filter)
  }, [historyAppointments, filter])

  const tabs = [
    { id: 'all', label: 'All History' },
    { id: 'completed', label: 'Completed' },
    { id: 'cancelled', label: 'Cancelled' }
  ]

  const handleDownload = () => {
    // Mock download action
    alert('Downloading medical records archive (ZIP)...')
  }

  return (
    <AppShell>
      <div className="max-w-4xl mx-auto w-full px-4 sm:px-6 lg:px-8 py-8 sm:py-12">
        
        {/* Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-6 mb-8">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <div className="p-2 bg-sky-100 text-sky-600 rounded-lg">
                <FileText className="w-6 h-6" />
              </div>
              <h1 className="text-3xl font-display font-bold text-slate-900 tracking-tight">
                Medical History
              </h1>
            </div>
            <p className="text-slate-500 text-base max-w-2xl">
              Review your past consultations, read AI-generated visit summaries, and access your medical records.
            </p>
          </div>
          
          <Button 
            variant="outline" 
            onClick={handleDownload}
            className="shrink-0 w-full sm:w-auto"
          >
            <Download className="w-4 h-4 mr-2" />
            Download Records
          </Button>
        </div>

        {/* Filters / Tabs */}
        <div className="flex items-center gap-2 mb-8 overflow-x-auto pb-2 no-scrollbar border-b border-slate-200">
          <div className="flex items-center text-slate-400 mr-2 shrink-0">
            <Filter className="w-4 h-4 mr-2" />
            <span className="text-sm font-medium">Filter:</span>
          </div>
          
          {tabs.map((tab) => {
            const isActive = filter === tab.id
            const count = tab.id === 'all' 
              ? historyAppointments.length 
              : historyAppointments.filter(a => a.status === tab.id).length

            return (
              <button
                key={tab.id}
                onClick={() => setFilter(tab.id)}
                className={`
                  whitespace-nowrap px-4 py-2.5 text-sm font-medium transition-all relative
                  ${isActive 
                    ? 'text-sky-600' 
                    : 'text-slate-500 hover:text-slate-800 hover:bg-slate-50 rounded-t-lg'
                  }
                `}
              >
                <div className="flex items-center gap-2">
                  {tab.label}
                  <span className={`
                    px-2 py-0.5 rounded-full text-xs
                    ${isActive ? 'bg-sky-100 text-sky-700' : 'bg-slate-100 text-slate-500'}
                  `}>
                    {count}
                  </span>
                </div>
                {isActive && (
                  <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-sky-600 rounded-t-full" />
                )}
              </button>
            )
          })}
        </div>

        {/* Appointment List */}
        <div className="space-y-5">
          {filteredAppointments.length > 0 ? (
            filteredAppointments.map((appointment) => (
              <AppointmentCard 
                key={appointment.id} 
                appointment={appointment} 
                showSummary={true} 
              />
            ))
          ) : (
            <div className="bg-white border border-slate-200 rounded-2xl p-12 text-center flex flex-col items-center justify-center">
              <div className="w-16 h-16 bg-slate-50 rounded-full flex items-center justify-center mb-4 border border-slate-100">
                <FileText className="w-8 h-8 text-slate-300" />
              </div>
              <h3 className="text-lg font-display font-semibold text-slate-900 mb-2">
                No records found
              </h3>
              <p className="text-slate-500 max-w-sm mx-auto mb-6">
                There are no {filter !== 'all' ? filter : ''} appointments in your medical history matching this filter.
              </p>
              {filter !== 'all' && (
                <Button variant="outline" onClick={() => setFilter('all')}>
                  Clear Filters
                </Button>
              )}
            </div>
          )}
        </div>

      </div>
    </AppShell>
  )
}