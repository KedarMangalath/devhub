import React, { useState } from 'react'
import { Link } from 'react-router-dom'
import { Activity, Calendar, Clock, FileText } from 'lucide-react'
import AppShell from '../components/layout/AppShell'
import AppointmentCard from '../components/domain/AppointmentCard'
import AIInsightCard from '../components/domain/AIInsightCard'
import { patient_profile, getPatientAppointments, ai_insights } from '../mockData'

const QuickAction = ({ icon: Icon, label, to, colorClass, bgClass }) => (
  <Link 
    to={to} 
    className="flex flex-col items-center justify-center p-5 bg-white rounded-2xl border border-slate-200 hover:border-sky-300 hover:shadow-md transition-all duration-300 group"
  >
    <div className={`w-12 h-12 rounded-full ${bgClass} flex items-center justify-center mb-3 group-hover:scale-110 transition-transform duration-300`}>
      <Icon className={`w-6 h-6 ${colorClass}`} />
    </div>
    <span className="text-sm font-semibold text-slate-700 group-hover:text-slate-900">{label}</span>
  </Link>
)

export default function PatientDashboard() {
  const [activeTab, setActiveTab] = useState('appointments')
  
  // Fetch and sort mock data
  const appointments = getPatientAppointments(patient_profile.id) || []
  const upcoming = appointments
    .filter(a => a.status === 'upcoming')
    .sort((a, b) => new Date(a.date) - new Date(b.date))
  const past = appointments
    .filter(a => a.status === 'completed')
    .sort((a, b) => new Date(b.date) - new Date(a.date))
    
  const nextAppointment = upcoming[0]
  const firstName = patient_profile.name.split(' ')[0]

  return (
    <AppShell>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 w-full animate-in fade-in duration-500">
        
        {/* Dashboard Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 mb-10">
          <div>
            <h1 className="text-3xl font-display font-bold text-slate-900 tracking-tight">
              Good morning, {firstName}
            </h1>
            <p className="text-slate-500 mt-1.5 text-lg">
              Here's your health overview for today.
            </p>
          </div>
          
          <div className="flex items-center gap-4 bg-white p-3.5 rounded-2xl border border-slate-200 shadow-sm">
            <div className="w-12 h-12 rounded-full bg-emerald-50 flex items-center justify-center border border-emerald-100 shrink-0">
              <Activity className="w-6 h-6 text-emerald-600" />
            </div>
            <div className="pr-4">
              <p className="text-sm font-medium text-slate-500 mb-0.5">Overall Health Score</p>
              <div className="flex items-baseline gap-2">
                <span className="text-2xl font-display font-bold text-slate-900 leading-none">
                  {patient_profile.health_score}
                </span>
                <span className="text-sm font-semibold text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-md">
                  Excellent
                </span>
              </div>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          
          {/* Left Column (Main Content) */}
          <div className="lg:col-span-2 space-y-10">
            
            {/* Next Appointment Section */}
            <section>
              <div className="flex items-center justify-between mb-5">
                <h2 className="text-xl font-display font-semibold text-slate-900 flex items-center gap-2">
                  <Calendar className="w-5 h-5 text-sky-600" />
                  Next Appointment
                </h2>
                <Link to="/appointments" className="text-sm font-semibold text-sky-600 hover:text-sky-700 transition-colors">
                  View all
                </Link>
              </div>
              
              {nextAppointment ? (
                <AppointmentCard appointment={nextAppointment} showSummary={false} />
              ) : (
                <div className="bg-white rounded-2xl border border-slate-200 p-10 text-center shadow-sm">
                  <div className="w-16 h-16 bg-slate-50 rounded-full flex items-center justify-center mx-auto mb-4 border border-slate-100">
                    <Calendar className="w-8 h-8 text-slate-300" />
                  </div>
                  <h3 className="text-lg font-semibold text-slate-900 mb-2">No upcoming appointments</h3>
                  <p className="text-slate-500 mb-6 max-w-sm mx-auto">
                    You're all caught up! Schedule a check-up or consult with a specialist if you need care.
                  </p>
                  <Link 
                    to="/doctors" 
                    className="inline-flex items-center justify-center px-6 py-2.5 bg-sky-600 text-white rounded-xl font-medium hover:bg-sky-700 transition-colors shadow-sm"
                  >
                    Book an Appointment
                  </Link>
                </div>
              )}
            </section>

            {/* Quick Actions */}
            <section>
              <h2 className="text-xl font-display font-semibold text-slate-900 mb-5">Quick Actions</h2>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <QuickAction 
                  icon={Calendar} 
                  label="Book Visit" 
                  to="/doctors" 
                  colorClass="text-sky-600" 
                  bgClass="bg-sky-50" 
                />
                <QuickAction 
                  icon={FileText} 
                  label="History" 
                  to="/history" 
                  colorClass="text-indigo-600" 
                  bgClass="bg-indigo-50" 
                />
                <QuickAction 
                  icon={Activity} 
                  label="Vitals" 
                  to="/dashboard" 
                  colorClass="text-rose-600" 
                  bgClass="bg-rose-50" 
                />
                <QuickAction 
                  icon={Clock} 
                  label="Recent" 
                  to="/appointments" 
                  colorClass="text-emerald-600" 
                  bgClass="bg-emerald-50" 
                />
              </div>
            </section>

            {/* Activity Timeline */}
            <section>
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-xl font-display font-semibold text-slate-900">Recent Activity</h2>
              </div>
              
              <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
                <div className="flex space-x-6 border-b border-slate-100 mb-6">
                  <button
                    onClick={() => setActiveTab('appointments')}
                    className={`pb-3 text-sm font-semibold border-b-2 transition-colors ${
                      activeTab === 'appointments' 
                        ? 'border-sky-600 text-sky-700' 
                        : 'border-transparent text-slate-500 hover:text-slate-700'
                    }`}
                  >
                    Past Visits
                  </button>
                  <button
                    onClick={() => setActiveTab('labs')}
                    className={`pb-3 text-sm font-semibold border-b-2 transition-colors ${
                      activeTab === 'labs' 
                        ? 'border-sky-600 text-sky-700' 
                        : 'border-transparent text-slate-500 hover:text-slate-700'
                    }`}
                  >
                    Lab Results
                  </button>
                </div>

                {activeTab === 'appointments' && (
                  <div className="relative border-l-2 border-slate-100 ml-4 space-y-8 pb-2">
                    {past.slice(0, 3).map((app) => {
                      const dateObj = new Date(app.date)
                      const dateStr = !isNaN(dateObj.getTime()) 
                        ? dateObj.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) 
                        : 'Recent'
                        
                      return (
                        <div key={app.id} className="relative pl-8 group">
                          <div className="absolute -left-[21px] top-0 w-10 h-10 rounded-full bg-white border-2 border-slate-100 flex items-center justify-center shadow-sm group-hover:border-sky-200 transition-colors">
                            <Clock className="w-4 h-4 text-slate-400 group-hover:text-sky-600 transition-colors" />
                          </div>
                          <div className="bg-slate-50/50 p-4 rounded-xl border border-slate-100 group-hover:border-slate-200 group-hover:bg-white transition-all">
                            <div className="flex justify-between items-start mb-1.5">
                              <h4 className="font-semibold text-slate-900">Completed Consultation</h4>
                              <span className="text-xs font-medium text-slate-500 bg-white border border-slate-200 px-2 py-1 rounded-md shadow-sm">
                                {dateStr}
                              </span>
                            </div>
                            <p className="text-sm text-slate-600 mb-3">
                              Follow-up visit. {app.ai_summary ? 'AI-generated summary and transcript available.' : 'Notes available.'}
                            </p>
                            <Link to="/history" className="inline-flex items-center text-sm font-semibold text-sky-600 hover:text-sky-700">
                              View details
                            </Link>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                )}

                {activeTab === 'labs' && (
                  <div className="py-8 text-center">
                    <FileText className="w-12 h-12 text-slate-300 mx-auto mb-3" />
                    <p className="text-slate-500 font-medium">No recent lab results available.</p>
                  </div>
                )}
              </div>
            </section>
            
          </div>

          {/* Right Column (Sidebar) */}
          <div className="lg:col-span-1 space-y-8">
            
            {/* AI Insights Panel */}
            <section>
              <div className="flex items-center justify-between mb-5">
                <h2 className="text-xl font-display font-semibold text-slate-900 flex items-center gap-2">
                  <Activity className="w-5 h-5 text-emerald-500" />
                  AI Insights
                </h2>
                <span className="bg-sky-100 text-sky-700 text-xs font-bold px-2.5 py-1 rounded-full">
                  {ai_insights.length} New
                </span>
              </div>
              
              <div className="space-y-4">
                {ai_insights.slice(0, 3).map(insight => (
                  <AIInsightCard key={insight.id} insight={insight} />
                ))}
              </div>
              
              {ai_insights.length > 3 && (
                <button className="w-full mt-4 py-3 text-sm font-semibold text-slate-600 bg-white border border-slate-200 rounded-xl hover:bg-slate-50 hover:text-slate-900 transition-colors shadow-sm">
                  View all insights
                </button>
              )}
            </section>

          </div>
        </div>
      </div>
    </AppShell>
  )
}