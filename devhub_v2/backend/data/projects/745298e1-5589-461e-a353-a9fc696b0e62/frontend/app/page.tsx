"use client";

import { useEffect, useState } from 'react';
import axios from 'axios';
import { Users, CalendarCheck, ActivitySquare } from 'lucide-react';
import { format } from 'date-fns';

interface Stats {
  doctorCount: number;
  patientCount: number;
  appointmentCount: number;
  recentAppointments: any[];
}

export default function Dashboard() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    axios.get('http://localhost:3001/api/stats')
      .then(res => {
        setStats(res.data);
        setLoading(false);
      })
      .catch(err => console.error(err));
  }, []);

  if (loading) return <div className="flex items-center justify-center h-full">Loading dashboard...</div>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-800">Welcome back, Alex</h1>
        <p className="text-slate-500">Here is what's happening with your health today.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm flex items-center space-x-4">
          <div className="p-3 bg-blue-50 text-blue-600 rounded-xl">
            <Users className="w-6 h-6" />
          </div>
          <div>
            <p className="text-sm text-slate-500 font-medium">Available Doctors</p>
            <p className="text-2xl font-bold text-slate-800">{stats?.doctorCount}</p>
          </div>
        </div>
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm flex items-center space-x-4">
          <div className="p-3 bg-omnia-50 text-omnia-600 rounded-xl">
            <CalendarCheck className="w-6 h-6" />
          </div>
          <div>
            <p className="text-sm text-slate-500 font-medium">Total Appointments</p>
            <p className="text-2xl font-bold text-slate-800">{stats?.appointmentCount}</p>
          </div>
        </div>
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm flex items-center space-x-4">
          <div className="p-3 bg-purple-50 text-purple-600 rounded-xl">
            <ActivitySquare className="w-6 h-6" />
          </div>
          <div>
            <p className="text-sm text-slate-500 font-medium">Registered Patients</p>
            <p className="text-2xl font-bold text-slate-800">{stats?.patientCount}</p>
          </div>
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-200">
          <h2 className="text-lg font-semibold text-slate-800">Recent Appointments</h2>
        </div>
        <div className="divide-y divide-slate-100">
          {stats?.recentAppointments.map((apt) => (
            <div key={apt.id} className="px-6 py-4 flex items-center justify-between hover:bg-slate-50 transition-colors">
              <div className="flex items-center space-x-4">
                <img src={apt.doctor.imageUrl} alt={apt.doctor.name} className="w-10 h-10 rounded-full object-cover" />
                <div>
                  <p className="font-medium text-slate-800">{apt.doctor.name}</p>
                  <p className="text-sm text-slate-500">{apt.doctor.specialty}</p>
                </div>
              </div>
              <div className="text-right">
                <p className="font-medium text-slate-800">{format(new Date(apt.date), 'MMM dd, yyyy')}</p>
                <p className="text-sm text-slate-500">{format(new Date(apt.date), 'h:mm a')}</p>
              </div>
              <div>
                <span className={`px-3 py-1 rounded-full text-xs font-medium ${
                  apt.status === 'SCHEDULED' ? 'bg-blue-50 text-blue-600' : 'bg-green-50 text-green-600'
                }`}>
                  {apt.status}
                </span>
              </div>
            </div>
          ))}
          {stats?.recentAppointments.length === 0 && (
            <div className="p-6 text-center text-slate-500">No recent appointments found.</div>
          )}
        </div>
      </div>
    </div>
  );
}
