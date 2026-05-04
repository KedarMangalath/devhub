import React from 'react';

export const StatusBadge = ({ status }) => {
  const colors = {
    'Submitted': 'bg-blue-100 text-blue-800 border-blue-200',
    'Under Review': 'bg-purple-100 text-purple-800 border-purple-200',
    'Investigation In Progress': 'bg-yellow-100 text-yellow-800 border-yellow-200',
    'Escalated': 'bg-red-100 text-red-800 border-red-200',
    'Resolved': 'bg-green-100 text-green-800 border-green-200',
    'Closed': 'bg-gray-100 text-gray-800 border-gray-200',
  };
  const colorClass = colors[status] || 'bg-gray-100 text-gray-800 border-gray-200';
  
  return (
    <span className={`px-2.5 py-0.5 rounded-full text-xs font-medium border ${colorClass}`}>
      {status}
    </span>
  );
};

export const SeverityBadge = ({ severity }) => {
  const colors = {
    'Low': 'bg-blue-50 text-blue-700',
    'Medium': 'bg-yellow-50 text-yellow-700',
    'High': 'bg-orange-50 text-orange-700',
    'Critical': 'bg-red-50 text-red-700',
  };
  const colorClass = colors[severity] || 'bg-gray-50 text-gray-700';
  
  return (
    <span className={`px-2 py-1 rounded text-xs font-semibold ${colorClass}`}>
      {severity}
    </span>
  );
};