import { departments } from '../../mockData'
import StatusPill from '../shared/StatusPill'
import { TrendingUp, TrendingDown, Minus } from 'lucide-react'

export default function RiskProfileTable() {
  // Sort departments by active complaints descending to show highest risk first
  const sortedDepartments = [...departments].sort((a, b) => b.active_complaints - a.active_complaints);

  const getResolutionRate = (active, resolved) => {
    const total = active + resolved;
    if (total === 0) return 0;
    return Math.round((resolved / total) * 100);
  };

  const renderTrend = (dept) => {
    // Mock trend logic based on data for stable but realistic visualization
    if (dept.risk_level === 'High' || dept.active_complaints > 80) {
      return (
        <div className="flex items-center justify-center gap-1 text-red-600 bg-red-50 px-2 py-1 rounded-md w-fit mx-auto">
          <TrendingUp className="w-4 h-4" />
          <span className="text-xs font-medium">+12%</span>
        </div>
      );
    } else if (dept.risk_level === 'Low' || dept.active_complaints < 30) {
      return (
        <div className="flex items-center justify-center gap-1 text-vacb-600 bg-vacb-50 px-2 py-1 rounded-md w-fit mx-auto">
          <TrendingDown className="w-4 h-4" />
          <span className="text-xs font-medium">-5%</span>
        </div>
      );
    }
    return (
      <div className="flex items-center justify-center gap-1 text-slate-500 bg-slate-50 px-2 py-1 rounded-md w-fit mx-auto">
        <Minus className="w-4 h-4" />
        <span className="text-xs font-medium">0%</span>
      </div>
    );
  };

  return (
    <div className="bg-white rounded-lg shadow-sm border border-slate-200 overflow-hidden flex flex-col h-full">
      <div className="px-6 py-5 border-b border-slate-200 flex items-center justify-between bg-slate-50/50">
        <div>
          <h3 className="text-lg font-semibold text-slate-900">Department Risk Profiles</h3>
          <p className="text-sm text-slate-500 mt-1">Current active complaints and risk assessment by department.</p>
        </div>
      </div>
      
      <div className="overflow-x-auto flex-1">
        <table className="w-full text-left text-sm text-slate-600 whitespace-nowrap">
          <thead className="bg-slate-50 text-slate-700 border-b border-slate-200 sticky top-0 z-10">
            <tr>
              <th className="px-6 py-3.5 font-semibold">Department Name</th>
              <th className="px-6 py-3.5 font-semibold text-right">Active Complaints</th>
              <th className="px-6 py-3.5 font-semibold text-right">Resolution Rate</th>
              <th className="px-6 py-3.5 font-semibold">Risk Level</th>
              <th className="px-6 py-3.5 font-semibold text-center">30-Day Trend</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {sortedDepartments.map((dept) => {
              const resolutionRate = getResolutionRate(dept.active_complaints, dept.total_resolved);
              
              return (
                <tr key={dept.id} className="hover:bg-slate-50 transition-colors group">
                  <td className="px-6 py-4">
                    <div className="font-medium text-slate-900">{dept.name}</div>
                    <div className="text-xs text-slate-400 mt-0.5">{dept.id}</div>
                  </td>
                  <td className="px-6 py-4 text-right font-medium text-slate-900">
                    {dept.active_complaints}
                  </td>
                  <td className="px-6 py-4 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <span className="font-medium text-slate-700">{resolutionRate}%</span>
                      <div className="w-16 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                        <div 
                          className={`h-full rounded-full ${
                            resolutionRate >= 80 ? 'bg-vacb-500' : 
                            resolutionRate >= 60 ? 'bg-yellow-500' : 'bg-red-500'
                          }`}
                          style={{ width: `${resolutionRate}%` }}
                        />
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <StatusPill type="severity" value={dept.risk_level} />
                  </td>
                  <td className="px-6 py-4">
                    {renderTrend(dept)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}