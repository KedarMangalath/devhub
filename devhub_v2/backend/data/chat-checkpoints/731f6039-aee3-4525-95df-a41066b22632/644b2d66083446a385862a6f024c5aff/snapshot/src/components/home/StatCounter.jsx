import React from 'react';
import { dashboardMetrics } from '../../mockData';
import { ShieldCheck, Clock, FileText, Database } from 'lucide-react';

const getIcon = (name, index) => {
  const lowerName = name?.toLowerCase() || '';
  if (lowerName.includes('rate')) return <ShieldCheck className="w-6 h-6 text-blue-700" />;
  if (lowerName.includes('time') || lowerName.includes('avg')) return <Clock className="w-6 h-6 text-blue-700" />;
  if (lowerName.includes('case') || lowerName.includes('processed')) return <FileText className="w-6 h-6 text-blue-700" />;
  if (lowerName.includes('audit') || lowerName.includes('log')) return <Database className="w-6 h-6 text-blue-700" />;

  const icons = [
    <ShieldCheck className="w-6 h-6 text-blue-700" />,
    <Clock className="w-6 h-6 text-blue-700" />,
    <FileText className="w-6 h-6 text-blue-700" />,
    <Database className="w-6 h-6 text-blue-700" />
  ];
  return icons[index % icons.length];
};

export default function StatCounter() {
  const defaultMetrics = [
    { id: 'stat-1', metric_name: 'Resolution Rate', value: '98%' },
    { id: 'stat-2', metric_name: 'Avg. Resolution Time', value: '15 Days' },
    { id: 'stat-3', metric_name: 'Cases Processed', value: '10,000+' },
    { id: 'stat-4', metric_name: 'Immutable Audit Logs', value: '100%' },
  ];

  const displayData = Array.isArray(dashboardMetrics) && dashboardMetrics.length >= 4 
    ? dashboardMetrics.slice(0, 4) 
    : defaultMetrics;

  return (
    <section className="bg-slate-50 py-12 sm:py-16 border-y border-slate-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {displayData.map((stat, index) => (
            <div 
              key={stat.id || index} 
              className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm flex flex-col items-center text-center hover:shadow-md transition-shadow duration-200"
            >
              <div className="p-3 bg-blue-50 rounded-full mb-4 ring-4 ring-blue-50/50">
                {getIcon(stat.metric_name, index)}
              </div>
              <dt className="order-2 mt-2 text-sm font-medium text-slate-600">
                {stat.metric_name}
              </dt>
              <dd className="order-1 text-3xl font-extrabold text-slate-900 tracking-tight">
                {stat.value}
              </dd>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}