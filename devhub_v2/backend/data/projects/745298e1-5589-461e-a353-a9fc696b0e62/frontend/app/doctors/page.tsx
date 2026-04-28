"use client";

import { useEffect, useState } from 'react';
import axios from 'axios';
import { Star, MapPin } from 'lucide-react';

interface Doctor {
  id: string;
  name: string;
  specialty: string;
  imageUrl: string;
  rating: number;
}

export default function DoctorsPage() {
  const [doctors, setDoctors] = useState<Doctor[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    axios.get('http://localhost:3001/api/doctors')
      .then(res => {
        setDoctors(res.data);
        setLoading(false);
      })
      .catch(err => console.error(err));
  }, []);

  if (loading) return <div className="flex items-center justify-center h-full">Loading doctors...</div>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-800">Our Specialists</h1>
        <p className="text-slate-500">Find and book an appointment with our top-rated doctors.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {doctors.map((doctor) => (
          <div key={doctor.id} className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden hover:shadow-md transition-shadow">
            <div className="p-6 flex flex-col items-center text-center">
              <img 
                src={doctor.imageUrl} 
                alt={doctor.name} 
                className="w-24 h-24 rounded-full object-cover mb-4 border-4 border-slate-50"
              />
              <h3 className="text-lg font-bold text-slate-800">{doctor.name}</h3>
              <p className="text-omnia-600 font-medium text-sm mb-2">{doctor.specialty}</p>
              
              <div className="flex items-center space-x-1 mb-4">
                <Star className="w-4 h-4 text-yellow-400 fill-current" />
                <span className="text-sm font-medium text-slate-700">{doctor.rating}</span>
                <span className="text-sm text-slate-400">(120+ reviews)</span>
              </div>

              <button className="w-full py-2.5 bg-slate-900 text-white rounded-xl font-medium hover:bg-slate-800 transition-colors">
                View Profile
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
