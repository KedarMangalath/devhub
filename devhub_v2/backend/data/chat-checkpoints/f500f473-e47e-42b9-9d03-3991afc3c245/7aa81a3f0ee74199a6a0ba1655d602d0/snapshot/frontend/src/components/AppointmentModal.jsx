import React, { useState } from 'react';
import axios from 'axios';
import { X, Calendar, Clock, User, Mail, FileText } from 'lucide-react';

export default function AppointmentModal({ doctor, onClose, apiBase }) {
  const [formData, setFormData] = useState({
    patient_name: '',
    patient_email: '',
    date: '',
    time: '',
    reason: ''
  });
  const [status, setStatus] = useState('idle'); // idle, submitting, success, error

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setStatus('submitting');
    try {
      await axios.post(`${apiBase}/appointments/`, {
        ...formData,
        doctor: doctor.id
      });
      setStatus('success');
      setTimeout(() => {
        onClose();
      }, 2000);
    } catch (error) {
      console.error("Booking error:", error);
      setStatus('error');
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100 flex justify-between items-center bg-gray-50">
          <h3 className="text-lg font-bold text-gray-900">Book Appointment</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X className="h-5 w-5" />
          </button>
        </div>
        
        <div className="p-6">
          {status === 'success' ? (
            <div className="text-center py-8">
              <div className="h-16 w-16 bg-green-100 text-green-600 rounded-full flex items-center justify-center mx-auto mb-4">
                <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7"></path></svg>
              </div>
              <h4 className="text-xl font-bold text-gray-900 mb-2">Booking Confirmed!</h4>
              <p className="text-gray-500">Your appointment with {doctor.name} has been scheduled.</p>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="flex items-center gap-4 mb-6 p-3 bg-brand-50 rounded-xl">
                <img src={doctor.image_url} alt={doctor.name} className="w-12 h-12 rounded-full object-cover" />
                <div>
                  <p className="font-semibold text-gray-900">{doctor.name}</p>
                  <p className="text-sm text-brand-600">{doctor.specialty}</p>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Patient Name</label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <User className="h-4 w-4 text-gray-400" />
                  </div>
                  <input required type="text" name="patient_name" value={formData.patient_name} onChange={handleChange} className="pl-10 w-full border border-gray-300 rounded-lg py-2 px-3 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent" placeholder="John Doe" />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Email Address</label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <Mail className="h-4 w-4 text-gray-400" />
                  </div>
                  <input required type="email" name="patient_email" value={formData.patient_email} onChange={handleChange} className="pl-10 w-full border border-gray-300 rounded-lg py-2 px-3 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent" placeholder="john@example.com" />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Date</label>
                  <div className="relative">
                    <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                      <Calendar className="h-4 w-4 text-gray-400" />
                    </div>
                    <input required type="date" name="date" value={formData.date} onChange={handleChange} className="pl-10 w-full border border-gray-300 rounded-lg py-2 px-3 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent" />
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Time</label>
                  <div className="relative">
                    <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                      <Clock className="h-4 w-4 text-gray-400" />
                    </div>
                    <input required type="time" name="time" value={formData.time} onChange={handleChange} className="pl-10 w-full border border-gray-300 rounded-lg py-2 px-3 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent" />
                  </div>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Reason for Visit</label>
                <div className="relative">
                  <div className="absolute top-3 left-3 pointer-events-none">
                    <FileText className="h-4 w-4 text-gray-400" />
                  </div>
                  <textarea required name="reason" value={formData.reason} onChange={handleChange} rows="3" className="pl-10 w-full border border-gray-300 rounded-lg py-2 px-3 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent" placeholder="Briefly describe your symptoms..."></textarea>
                </div>
              </div>

              {status === 'error' && (
                <p className="text-red-500 text-sm">Something went wrong. Please try again.</p>
              )}

              <button 
                type="submit" 
                disabled={status === 'submitting'}
                className="w-full bg-brand-600 text-white rounded-lg py-3 font-semibold hover:bg-brand-700 transition-colors disabled:opacity-70 mt-4"
              >
                {status === 'submitting' ? 'Booking...' : 'Confirm Appointment'}
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
