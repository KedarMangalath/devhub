import { useState } from 'react'
import { Calendar, Clock, Video, FileText, ChevronDown, ChevronUp } from 'lucide-react'
import Card from '../ui/Card'
import Badge from '../ui/Badge'
import Button from '../ui/Button'
import { getDoctorById } from '../../mockData'

export default function AppointmentCard({ appointment, showSummary = false }) {
  const [isExpanded, setIsExpanded] = useState(false)

  if (!appointment) return null

  const doctor = getDoctorById(appointment.doctor_id)
  
  // Format date and time safely
  const dateObj = new Date(appointment.date)
  const formattedDate = !isNaN(dateObj.getTime()) 
    ? dateObj.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' })
    : 'Date TBD'
    
  const formattedTime = !isNaN(dateObj.getTime())
    ? dateObj.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })
    : 'Time TBD'

  const getStatusStyles = (status) => {
    switch (status?.toLowerCase()) {
      case 'upcoming':
        return 'bg-sky-50 text-sky-700 border-sky-200'
      case 'completed':
        return 'bg-emerald-50 text-emerald-700 border-emerald-200'
      case 'cancelled':
        return 'bg-slate-50 text-slate-600 border-slate-200'
      default:
        return 'bg-slate-50 text-slate-600 border-slate-200'
    }
  }

  return (
    <Card className="flex flex-col gap-5">
      {/* Header: Date, Time, and Status */}
      <div className="flex items-start justify-between">
        <div className="flex flex-col gap-1.5">
          <div className="flex items-center gap-2 text-slate-900 font-semibold">
            <Calendar className="w-4 h-4 text-sky-600" />
            <span>{formattedDate}</span>
          </div>
          <div className="flex items-center gap-2 text-slate-500 text-sm font-medium">
            <Clock className="w-4 h-4" />
            <span>{formattedTime}</span>
          </div>
        </div>
        <Badge className={getStatusStyles(appointment.status)}>
          {appointment.status ? appointment.status.charAt(0).toUpperCase() + appointment.status.slice(1) : 'Unknown'}
        </Badge>
      </div>

      {/* Body: Doctor Information */}
      <div className="flex items-center gap-4 p-3 bg-slate-50/50 rounded-xl border border-slate-100">
        {doctor?.avatar ? (
          <img 
            src={doctor.avatar} 
            alt={doctor.name} 
            className="w-12 h-12 rounded-full object-cover border border-slate-200 shadow-sm"
          />
        ) : (
          <div className="w-12 h-12 rounded-full bg-slate-200 flex items-center justify-center text-slate-400 font-bold">
            {doctor?.name?.charAt(0) || '?'}
          </div>
        )}
        
        <div className="flex-1 min-w-0">
          <h4 className="font-semibold text-slate-900 truncate">
            {doctor?.name || 'Unknown Provider'}
          </h4>
          <p className="text-sm text-slate-500 truncate">
            {doctor?.specialty_name || 'Specialist'}
          </p>
        </div>

        {appointment.status === 'upcoming' && (
          <Button 
            variant="outline" 
            className="rounded-full w-10 h-10 p-0 flex items-center justify-center shrink-0 border-sky-200 text-sky-600 hover:bg-sky-50 hover:text-sky-700"
            aria-label="Join Video Call"
          >
            <Video className="w-4 h-4" />
          </Button>
        )}
      </div>

      {/* Footer: AI Summary Toggle */}
      {showSummary && appointment.ai_summary && (
        <div className="pt-2 border-t border-slate-100">
          <button 
            onClick={() => setIsExpanded(!isExpanded)}
            className="flex items-center justify-between w-full text-sm font-medium text-slate-700 hover:text-sky-600 transition-colors group py-1"
          >
            <div className="flex items-center gap-2">
              <div className="p-1.5 bg-emerald-100 rounded-md group-hover:bg-emerald-200 transition-colors">
                <FileText className="w-3.5 h-3.5 text-emerald-700" />
              </div>
              <span>AI Visit Summary</span>
            </div>
            {isExpanded ? (
              <ChevronUp className="w-4 h-4 text-slate-400 group-hover:text-sky-600" />
            ) : (
              <ChevronDown className="w-4 h-4 text-slate-400 group-hover:text-sky-600" />
            )}
          </button>
          
          {/* Expandable Content */}
          <div 
            className={`grid transition-all duration-200 ease-in-out ${
              isExpanded ? 'grid-rows-[1fr] opacity-100 mt-3' : 'grid-rows-[0fr] opacity-0'
            }`}
          >
            <div className="overflow-hidden">
              <div className="p-4 bg-gradient-to-br from-emerald-50/50 to-teal-50/30 rounded-xl border border-emerald-100/50 text-sm text-slate-600 leading-relaxed">
                {appointment.ai_summary}
              </div>
            </div>
          </div>
        </div>
      )}
    </Card>
  )
}