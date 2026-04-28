import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import { AuthProvider } from './hooks/useAuth'
import Home from './pages/Home'
import DoctorDirectory from './pages/DoctorDirectory'
import DoctorProfile from './pages/DoctorProfile'
import PatientDashboard from './pages/PatientDashboard'
import TeleconsultationRoom from './pages/TeleconsultationRoom'
import Pharmacy from './pages/Pharmacy'
import Login from './pages/Login'

export default function App() {
  return (
    <AuthProvider>
      <Router>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/doctors" element={<DoctorDirectory />} />
          <Route path="/doctors/:id" element={<DoctorProfile />} />
          <Route path="/dashboard" element={<PatientDashboard />} />
          <Route path="/consultation/:id" element={<TeleconsultationRoom />} />
          <Route path="/medicines" element={<Pharmacy />} />
          <Route path="/login" element={<Login />} />
        </Routes>
      </Router>
    </AuthProvider>
  )
}