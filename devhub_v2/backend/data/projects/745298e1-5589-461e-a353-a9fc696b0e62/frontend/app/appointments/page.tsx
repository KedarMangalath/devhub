"use client";

import { useEffect, useState } from 'react';
import axios from 'axios';
import { format } from 'date-fns';
import { Calendar as CalendarIcon, Clock } from 'lucide-react';

interface Doctor {
  id: string;
  name: string;
  specialty: string;
}

interface Appointment {
  id: string;
  date: string;
  status: string;
  doctor: Doctor;
}

export default function AppointmentsPage() {
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [doctors, setDoctors] = useState<Doctor[]>([]);
  const [loading, setLoading] = useState(true);

  // Form state
  const [selectedDoctor, setSelectedDoctor] = useState('');
  const [selectedDate, setSelectedDate] = useState('');
  const [selectedTime, setSelectedTime] = useState('');
  const [booking, setBooking] = useState(false);

  const fetchData = async () => {
    try {
      const [aptRes, docRes] = await Promise.all([
        axios.get('http://localhost:3001/api/appointments'),
        axios.get('http://localhost:3001/api/doctors')
      ]);
      setAppointments(aptRes.data);
      setDoctors(docRes.data);
      setLoading(false);
    } catch (error) {
      console.error(error);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleBook = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedDoctor || !selectedDate || !selectedTime) return;
    
    setBooking(true);
    try {
      const dateTime = new Date(`${selectedDate}T${selectedTime}`);
      await axios.post('http://localhost:3001/api/appointments', {
        doctorId: selectedDoctor,
        date: dateTime.toISOString()
      });
      
      // Reset form and refresh
      setSelectedDoctor('');
      setSelectedDate('');
      setSelectedTime('');
      await fetchData();
    } catch (error) {
      console.error('Failed to book', error);
    } finally {
      setBooking(false);
    }
  };

  if (loading) return <div className="flex items-center justify-center h-full">Loading appointments...</div>;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-slate-800">Appointments</h1>
        <p className="text-slate-500">Manage your upcoming and past consultations.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Booking Form */}
        <div className="lg:col-span-1">
          <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
            <h2 className="text-lg font-semibold text-slate-800 mb-4">Book New Appointment</h2>
            <form onSubmit={handleBook} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Select Doctor</label>
                <select 
                  value={selectedDoctor}
                  onChange={(e) => setSelectedDoctor(e.target.value)}
                  className="w-full border border-slate-300 rounded-xl px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-omnia-500"
                  required
                >
                  <option value="">Choose a specialist...</option>
                  {doctors.map(doc => (
                    <option key={doc.id} value={doc.id}>{doc.name} - {doc.specialty}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Date</label>
                <input 
                  type="date" 
                  value={selectedDate}
                  onChange={(e) => setSelectedDate(e.target.value)}
                  className="w-full border border-slate-300 rounded-xl px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-omnia-500"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Time</label>
                <input 
                  type="time" 
                  value={selectedTime}
                  onChange={(e) => setSelectedTime(e.target.value)}
                  className="w-full border border-slate-300 rounded-xl px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-omnia-500"
                  required
                />
              </div>
              <button 
                type="submit" 
                disabled={booking}
                className="w-full py-3 bg-omnia-600 text-white rounded-xl font-medium hover:bg-omnia-700 transition-colors disabled:opacity-50"
              >
                {booking ? 'Booking...' : 'Confirm Appointment'}
              </button>
            </form>
          </div>
        </div>

        {/* Appointments List */}
        <div className="lg:col-span-2">
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-200">
              <h2 className="text-lg font-semibold text-slate-800">Your Schedule</h2>
            </div>
            <div className="divide-y divide-slate-100">
              {appointments.map((apt) => (
                <div key={apt.id} className="p-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4 hover:bg-slate-50 transition-colors">
                  <div>
                    <h3 className="font-bold text-slate-800">{apt.doctor.name}</h3>
                    <p className="text-sm text-slate-500">{apt.doctor.specialty}</p>
                  </div>
                  <div className="flex items-center space-x-6">
                    <div className="flex items-center text-slate-600">
                      <CalendarIcon className="w-4 h-4 mr-2 text-slate-400" />
                      <span className="text-sm font-medium">{format(new Date(apt.date), 'MMM dd, yyyy')}</span>
                    </div>
                    <div className="flex items-center text-slate-600">
                      <Clock className="w-4 h-4 mr-2 text-slate-400" />
                      <span className="text-sm font-medium">{format(new Date(apt.date), 'h:mm a')}</span>
                    </div>
                    <span className={`px-3 py-1 rounded-full text-xs font-bold tracking-wide ${
                      apt.status === 'SCHEDULED' ? 'bg-blue-100 text-blue-700' : 'bg-green-100 text-green-700'
                    }`}>
                      {apt.status}
                    </span>
                  </div>
                </div>
              ))}
              {appointments.length === 0 && (
                <div className="p-8 text-center text-slate-500">
                  No appointments scheduled yet.
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
