import React from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import LandingPage from './pages/LandingPage'
import PatientDashboard from './pages/PatientDashboard'
import DoctorDirectory from './pages/DoctorDirectory'
import DoctorProfile from './pages/DoctorProfile'
import BookingWorkflow from './pages/BookingWorkflow'
import MedicalHistory from './pages/MedicalHistory'
import AppShell from './components/layout/AppShell'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Public Landing Page */}
        <Route path="/" element={<LandingPage />} />

        {/* Main Application Routes wrapped in AppShell for navigation/layout */}
        <Route element={<AppShell />}>
          <Route path="/dashboard" element={<PatientDashboard />} />
          <Route path="/doctors" element={<DoctorDirectory />} />
          <Route path="/doctors/:id" element={<DoctorProfile />} />
          <Route path="/book/:id" element={<BookingWorkflow />} />
          <Route path="/history" element={<MedicalHistory />} />
        </Route>

        {/* 404 / Catch-all Route */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}