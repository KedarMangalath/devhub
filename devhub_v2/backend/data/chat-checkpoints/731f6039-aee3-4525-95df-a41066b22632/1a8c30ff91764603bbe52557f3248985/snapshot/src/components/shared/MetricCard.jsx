import { TrendingUp, TrendingDown } from 'lucide-react'
import { cn } from '../../utils/cn'

export default function MetricCard({ 
  title, 
  value, 
  trend, 
  icon: Icon, 
  className 
}) {
  // Handle both object { value: '12%', positive: true } and string "+12%" formats
  const isPositive = typeof trend === 'object' 
    ? trend.positive 
    : !String(trend).trim().startsWith('-');
    
  const trendValue = typeof trend === 'object' 
    ? trend.value 
    : trend;

  return (
    <div className={cn(
      "bg-white border border-slate-200 rounded-lg shadow-sm p-5 flex flex-col transition-shadow hover:shadow-md",
      className
    )}>
      <div className="flex items-start justify-between mb-4">
        <h3 className="text-sm font-medium text-slate-500 tracking-wide">
          {title}
        </h3>
        {Icon && (
          <div className="p-2.5 bg-[#1d4ed8]/10 rounded-full flex-shrink-0">
            <Icon className="w-5 h-5 text-[#1d4ed8]" strokeWidth={2.5} />
          </div>
        )}
      </div>
      
      <div className="flex items-end justify-between mt-auto">
        <p className="text-3xl font-bold text-slate-900 font-display">
          {value}
        </p>
        
        {trend && (
          <div 
            className={cn(
              "flex items-center text-sm font-semibold px-2 py-1 rounded-full",
              isPositive 
                ? "text-blue-700 bg-blue-50" 
                : "text-red-700 bg-red-50"
            )}
            title={isPositive ? "Trending up" : "Trending down"}
          >
            {isPositive ? (
              <TrendingUp className="w-4 h-4 mr-1.5" strokeWidth={2.5} />
            ) : (
              <TrendingDown className="w-4 h-4 mr-1.5" strokeWidth={2.5} />
            )}
            <span>{trendValue}</span>
          </div>
        )}
      </div>
    </div>
  )
}