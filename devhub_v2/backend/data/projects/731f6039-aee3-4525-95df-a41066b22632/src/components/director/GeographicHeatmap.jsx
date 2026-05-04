import React, { useState, useMemo } from 'react';
import { MapPin, AlertOctagon } from 'lucide-react';
import { departments } from '../../mockData';

const KERALA_DISTRICTS = [
  { id: 'KL-TVM', name: 'Thiruvananthapuram', complaints: 145, risk: 'High', trend: '+12%' },
  { id: 'KL-EKM', name: 'Ernakulam', complaints: 182, risk: 'High', trend: '+5%' },
  { id: 'KL-TSR', name: 'Thrissur', complaints: 110, risk: 'Medium', trend: '+8%' },
  { id: 'KL-KKD', name: 'Kozhikode', complaints: 98, risk: 'Medium', trend: '-2%' },
  { id: 'KL-KNR', name: 'Kannur', complaints: 92, risk: 'Medium', trend: '+3%' },
  { id: 'KL-MLP', name: 'Malappuram', complaints: 85, risk: 'Medium', trend: '-5%' },
  { id: 'KL-PKD', name: 'Palakkad', complaints: 76, risk: 'Low', trend: '-10%' },
  { id: 'KL-KLM', name: 'Kollam', complaints: 64, risk: 'Low', trend: '-1%' },
  { id: 'KL-ALP', name: 'Alappuzha', complaints: 55, risk: 'Low', trend: '-8%' },
  { id: 'KL-KTM', name: 'Kottayam', complaints: 48, risk: 'Low', trend: '-12%' },
  { id: 'KL-KSG', name: 'Kasaragod', complaints: 41, risk: 'Low', trend: '-4%' },
  { id: 'KL-PTA', name: 'Pathanamthitta', complaints: 34, risk: 'Low', trend: '-15%' },
  { id: 'KL-IDK', name: 'Idukki', complaints: 29, risk: 'Low', trend: '-20%' },
  { id: 'KL-WYD', name: 'Wayanad', complaints: 22, risk: 'Low', trend: '-25%' },
];

export default function GeographicHeatmap() {
  const [activeFilter, setActiveFilter] = useState('All');

  // Utilize imported departments data to calculate a global metric for context
  const totalDepartmentComplaints = useMemo(() => {
    return departments.reduce((acc, dept) => acc + dept.active_complaints, 0);
  }, []);

  const filteredDistricts = useMemo(() => {
    let filtered = KERALA_DISTRICTS;
    if (activeFilter !== 'All') {
      filtered = KERALA_DISTRICTS.filter(d => d.risk === activeFilter);
    }
    return filtered.sort((a, b) => b.complaints - a.complaints);
  }, [activeFilter]);

  const maxComplaints = Math.max(...KERALA_DISTRICTS.map(d => d.complaints));

  const getRiskStyles = (risk) => {
    switch (risk) {
      case 'High':
        return {
          bg: 'bg-red-50',
          border: 'border-red-200',
          text: 'text-red-700',
          bar: 'bg-red-500',
          icon: 'text-red-500'
        };
      case 'Medium':
        return {
          bg: 'bg-amber-50',
          border: 'border-amber-200',
          text: 'text-amber-700',
          bar: 'bg-amber-500',
          icon: 'text-amber-500'
        };
      case 'Low':
        return {
          bg: 'bg-vacb-50',
          border: 'border-vacb-200',
          text: 'text-vacb-700',
          bar: 'bg-vacb-500',
          icon: 'text-vacb-500'
        };
      default:
        return {
          bg: 'bg-slate-50',
          border: 'border-slate-200',
          text: 'text-slate-700',
          bar: 'bg-slate-500',
          icon: 'text-slate-500'
        };
    }
  };

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden flex flex-col h-full">
      <div className="p-6 border-b border-slate-200 bg-slate-50/50 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-slate-900 flex items-center gap-2">
            <MapPin className="w-5 h-5 text-vacb-700" />
            Geographic Risk Distribution
          </h2>
          <p className="text-sm text-slate-500 mt-1">
            Active complaints mapped across Kerala districts (Total Dept. Load: {totalDepartmentComplaints})
          </p>
        </div>
        
        <div className="flex bg-slate-100 p-1 rounded-lg self-start sm:self-auto">
          {['All', 'High', 'Medium', 'Low'].map((filter) => (
            <button
              key={filter}
              onClick={() => setActiveFilter(filter)}
              className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
                activeFilter === filter
                  ? 'bg-white text-slate-900 shadow-sm'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-200/50'
              }`}
            >
              {filter}
            </button>
          ))}
        </div>
      </div>

      <div className="p-6 flex-1 overflow-y-auto">
        {filteredDistricts.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-48 text-slate-500">
            <AlertOctagon className="w-8 h-8 mb-2 text-slate-300" />
            <p>No districts match the selected risk level.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {filteredDistricts.map((district) => {
              const styles = getRiskStyles(district.risk);
              const barWidth = `${(district.complaints / maxComplaints) * 100}%`;
              
              return (
                <div 
                  key={district.id}
                  className={`p-4 rounded-lg border transition-all hover:shadow-md ${styles.bg} ${styles.border}`}
                >
                  <div className="flex justify-between items-start mb-3">
                    <div>
                      <h3 className={`font-semibold ${styles.text} flex items-center gap-1.5`}>
                        {district.name}
                        {district.risk === 'High' && (
                          <AlertOctagon className="w-4 h-4" />
                        )}
                      </h3>
                      <span className="text-xs font-medium text-slate-500 uppercase tracking-wider mt-1 block">
                        {district.risk} Risk
                      </span>
                    </div>
                    <div className="text-right">
                      <div className={`text-xl font-bold ${styles.text}`}>
                        {district.complaints}
                      </div>
                      <div className={`text-xs font-medium ${district.trend.startsWith('+') ? 'text-red-600' : 'text-vacb-600'}`}>
                        {district.trend} this month
                      </div>
                    </div>
                  </div>
                  
                  <div className="mt-4">
                    <div className="flex justify-between text-xs text-slate-500 mb-1.5">
                      <span>Volume Intensity</span>
                      <span>{Math.round((district.complaints / maxComplaints) * 100)}%</span>
                    </div>
                    <div className="w-full bg-white/60 rounded-full h-2 overflow-hidden border border-slate-200/50">
                      <div 
                        className={`h-full rounded-full ${styles.bar} transition-all duration-1000 ease-out`}
                        style={{ width: barWidth }}
                      />
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}