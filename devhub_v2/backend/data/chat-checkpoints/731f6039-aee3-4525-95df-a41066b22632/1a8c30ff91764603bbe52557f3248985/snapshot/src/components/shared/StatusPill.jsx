import { cn } from '../../utils/cn'

export default function StatusPill({ type = 'status', value, className }) {
  if (!value) return null;

  const normalizedValue = value.toLowerCase();

  const severityColors = {
    critical: 'bg-red-50 text-red-700 border-red-200',
    high: 'bg-amber-50 text-amber-700 border-amber-200',
    medium: 'bg-yellow-50 text-yellow-700 border-yellow-200',
    low: 'bg-blue-50 text-blue-700 border-blue-200',
  };

  const statusColors = {
    pending: 'bg-slate-100 text-slate-700 border-slate-200',
    'under investigation': 'bg-blue-50 text-blue-700 border-blue-200',
    'in progress': 'bg-blue-50 text-blue-700 border-blue-200',
    resolved: 'bg-blue-50 text-blue-700 border-blue-200',
    rejected: 'bg-red-50 text-red-700 border-red-200',
  };

  const colorMap = type === 'severity' ? severityColors : statusColors;
  const colorClasses = colorMap[normalizedValue] || 'bg-gray-100 text-gray-700 border-gray-200';

  return (
    <span
      className={cn(
        'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border',
        colorClasses,
        className
      )}
    >
      {value}
    </span>
  );
}