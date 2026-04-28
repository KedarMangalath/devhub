import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth.jsx'
import { createPrescription } from '../api/endpoints.js'
import Navbar from '../components/Navbar.jsx'
import VideoPlayerPlaceholder from '../components/VideoPlayerPlaceholder.jsx'
import ChatBox from '../components/ChatBox.jsx'
import EPrescriptionForm from '../components/EPrescriptionForm.jsx'

export default function TeleconsultationRoom() {
  const { id } = useParams()
  const { user } = useAuth()
  const isDoctor = user?.role === 'doctor'

  const handlePrescriptionSubmit = async (medications, instructions) => {
    await createPrescription({ appointment_id: id, medications, instructions })
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <Navbar />
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 py-8 flex flex-col md:flex-row gap-6">
        <div className="flex-1 flex flex-col gap-6">
          <VideoPlayerPlaceholder />
          {isDoctor && <EPrescriptionForm onSubmit={handlePrescriptionSubmit} />}
        </div>
        <div className="w-full md:w-96 flex-shrink-0">
          <ChatBox messages={[]} onSendMessage={() => {}} />
        </div>
      </main>
    </div>
  )
}