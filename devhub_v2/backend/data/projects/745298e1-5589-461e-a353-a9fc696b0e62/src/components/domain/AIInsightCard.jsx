import { Link } from 'react-router-dom'
import { Heart, Activity, AlertCircle, ArrowRight } from 'lucide-react'
import Card from '../ui/Card'
import Button from '../ui/Button'

export default function AIInsightCard({ insight }) {
  if (!insight) return null;

  const getIconConfig = (type) => {
    switch (type?.toLowerCase()) {
      case 'heart':
      case 'cardio':
        return { 
          Icon: Heart, 
          colorClass: 'text-rose-500', 
          bgClass: 'bg-rose-50' 
        };
      case 'alert':
      case 'warning':
        return { 
          Icon: AlertCircle, 
          colorClass: 'text-amber-500', 
          bgClass: 'bg-amber-50' 
        };
      case 'activity':
      case 'fitness':
      default:
        return { 
          Icon: Activity, 
          colorClass: 'text-sky-500', 
          bgClass: 'bg-sky-50' 
        };
    }
  };

  const { Icon, colorClass, bgClass } = getIconConfig(insight.type);

  const formattedDate = insight.date 
    ? new Intl.DateTimeFormat('en-US', { 
        month: 'short', 
        day: 'numeric', 
        year: 'numeric' 
      }).format(new Date(insight.date))
    : 'Recent';

  return (
    <Card hoverable className="flex flex-col h-full group">
      <div className="flex items-start justify-between mb-5">
        <div className={`p-2.5 rounded-xl ${bgClass} ${colorClass} transition-colors duration-300`}>
          <Icon className="w-5 h-5" />
        </div>
        <span className="text-xs font-medium text-slate-500 bg-slate-100/80 px-2.5 py-1 rounded-full border border-slate-200/60">
          {formattedDate}
        </span>
      </div>
      
      <div className="flex-1">
        <h3 className="text-lg font-semibold text-slate-900 mb-2 font-display tracking-tight">
          {insight.title}
        </h3>
        <p className="text-sm text-slate-600 leading-relaxed">
          {insight.description}
        </p>
      </div>
      
      <div className="mt-6 pt-5 border-t border-slate-100">
        <Link to="/doctors" className="block" tabIndex={-1}>
          <Button 
            className="w-full flex items-center justify-center gap-2 bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 hover:text-slate-900 hover:border-slate-300 shadow-sm transition-all"
          >
            Discuss with a doctor
            <ArrowRight className="w-4 h-4 text-slate-400 group-hover:text-primary-500 transition-colors" />
          </Button>
        </Link>
      </div>
    </Card>
  );
}