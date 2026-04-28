import { useState, useEffect } from 'react'
import { getAppointments, getPrescriptions } from '../api/endpoints.js'
import { useAuth } from '../hooks/useAuth.jsx'
import Navbar from '../components/Navbar.jsx'
import DashboardSidebar from '../components/DashboardSidebar.jsx'
import UpcomingAppointments from '../components/UpcomingAppointments.jsx'
import PrescriptionCard from '../components/PrescriptionCard.jsx'

export default function PatientDashboard() {
  const { user, isAuthenticated, loading } = useAuth()
  const [appointments, setAppointments] = useState([])
  const [prescriptions, setPrescriptions] = useState([])
  const [activeTab, setActiveTab] = useState('appointments')
  const [dataLoading, setDataLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (isAuthenticated) {
      fetchDashboardData()
    }
  }, [isAuthenticated])

  const fetchDashboardData = async () => {
    try {
      setDataLoading(true)
      setError(null)
      const [apptsData, presData] = await Promise.all([
        getAppointments(),
        getPrescriptions()
      ])
      setAppointments(apptsData)
      setPrescriptions(presData)
    } catch (err) {
      console.error('Error fetching dashboard data:', err)
      setError('Failed to load your health records. Please try refreshing the page.')
    } finally {
      setDataLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex flex-col">
        <Navbar />
        <div className="flex-1 flex items-center justify-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
        </div>
      </div>
    )
  }

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-gray-50 flex flex-col">
        <Navbar />
        <div className="flex-1 flex items-center justify-center p-6">
          <div className="bg-white p-8 rounded-xl shadow-sm border border-gray-200 text-center max-w-md w-full">
            <h2 className="text-2xl font-bold text-gray-900 mb-2">Access Denied</h2>
            <p className="text-gray-600 mb-6">Please log in to view your secure patient dashboard and medical records.</p>
            <a href="/login" className="inline-block bg-blue-600 text-white px-6 py-2.5 rounded-lg font-medium hover:bg-blue-700 transition-colors w-full">
              Go to Login
            </a>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <Navbar />
      
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex flex-col md:flex-row gap-8">
          <DashboardSidebar activeTab={activeTab} onTabChange={setActiveTab} />
          
          <div className="flex-1">
            <div className="mb-6">
              <h1 className="text-2xl font-bold text-gray-900">
                Welcome back, {user?.full_name || 'Patient'}
              </h1>
              <p className="text-gray-600 mt-1">
                Manage your appointments, prescriptions, and account settings.
              </p>
            </div>

            {error && (
              <div className="mb-6 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
                {error}
              </div>
            )}

            {dataLoading ? (
              <div className="flex justify-center py-12 bg-white rounded-xl shadow-sm border border-gray-200">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
              </div>
            ) : (
              <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                {activeTab === 'appointments' && (
                  <div>
                    <h2 className="text-xl font-semibold text-gray-800 mb-6">Your Appointments</h2>
                    <UpcomingAppointments appointments={appointments} />
                  </div>
                )}

                {activeTab === 'prescriptions' && (
                  <div>
                    <h2 className="text-xl font-semibold text-gray-800 mb-6">Your Prescriptions</h2>
                    {prescriptions.length > 0 ? (
                      <div className="grid grid-cols-1 gap-6">
                        {prescriptions.map((prescription) => (
                          <PrescriptionCard key={prescription.id} prescription={prescription} />
                        ))}
                      </div>
                    ) : (
                      <div className="text-center py-12 bg-gray-50 rounded-lg border border-gray-100">
                        <p className="text-gray-500">No prescriptions found in your medical record.</p>
                      </div>
                    )}
                  </div>
                )}

                {activeTab === 'settings' && (
                  <div>
                    <h2 className="text-xl font-semibold text-gray-800 mb-6">Account Settings</h2>
                    <div className="space-y-6 max-w-2xl">
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Full Name</label>
                        <input 
                          type="text" 
                          disabled 
                          value={user?.full_name || ''} 
                          className="block w-full rounded-md border-gray-300 bg-gray-50 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm px-4 py-2.5 border" 
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Email Address</label>
                        <input 
                          type="email" 
                          disabled 
                          value={user?.email || ''} 
                          className="block w-full rounded-md border-gray-300 bg-gray-50 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm px-4 py-2.5 border" 
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Account Role</label>
                        <input 
                          type="text" 
                          disabled 
                          value={user?.role || 'Patient'} 
                          className="block w-full rounded-md border-gray-300 bg-gray-50 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm px-4 py-2.5 border capitalize" 
                        />
                      </div>
                      <div className="pt-4 border-t border-gray-100">
                        <button className="bg-blue-600 text-white px-5 py-2.5 rounded-lg hover:bg-blue-700 transition-colors font-medium text-sm shadow-sm">
                          Request Profile Update
                        </button>
                        <p className="mt-2 text-xs text-gray-500">
                          For security reasons, profile updates require administrative approval.
                        </p>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  )
}