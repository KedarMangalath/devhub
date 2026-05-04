import { useNavigate } from 'react-router-dom'
import StatusPill from '../shared/StatusPill'
import { AlertTriangle } from 'lucide-react'

export default function ComplaintDataGrid({ complaints = [] }) {
  const navigate = useNavigate();

  if (!complaints || complaints.length === 0) {
    return (
      <div className="bg-white rounded-lg shadow-sm border border-slate-200 p-12 text-center flex flex-col items-center justify-center">
        <div className="w-12 h-12 bg-slate-50 rounded-full flex items-center justify-center mb-4">
          <AlertTriangle className="w-6 h-6 text-slate-400" />
        </div>
        <h3 className="text-lg font-medium text-slate-900 mb-1">No complaints found</h3>
        <p className="text-slate-500 max-w-sm">
          There are currently no complaints matching your selected filters or criteria.
        </p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow-sm border border-slate-200 overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="bg-slate-50 border-b border-slate-200 text-xs uppercase tracking-wider text-slate-500 font-medium">
              <th className="px-6 py-4 whitespace-nowrap">Tracking ID</th>
              <th className="px-6 py-4">Title & Description</th>
              <th className="px-6 py-4 whitespace-nowrap">Department Ref</th>
              <th className="px-6 py-4 whitespace-nowrap">Severity</th>
              <th className="px-6 py-4 whitespace-nowrap">Status</th>
              <th className="px-6 py-4 whitespace-nowrap">SLA Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200">
            {complaints.map((complaint) => (
              <tr
                key={complaint.id}
                onClick={() => navigate(`/officer/complaint/${complaint.id}`)}
                className="hover:bg-slate-50 transition-colors cursor-pointer group"
              >
                <td className="px-6 py-4 whitespace-nowrap text-sm">
                  <span className="font-mono text-slate-500 group-hover:text-vacb-700 transition-colors">
                    {complaint.tracking_id}
                  </span>
                  <div className="text-xs text-slate-400 mt-1">
                    {new Date(complaint.date_filed).toLocaleDateString('en-IN', {
                      day: 'numeric',
                      month: 'short',
                      year: 'numeric'
                    })}
                  </div>
                </td>
                <td className="px-6 py-4">
                  <div className="max-w-md">
                    <div className="font-medium text-slate-900 truncate" title={complaint.title}>
                      {complaint.title}
                    </div>
                    <div className="text-sm text-slate-500 truncate mt-0.5" title={complaint.description}>
                      {complaint.description}
                    </div>
                  </div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-600">
                  <div className="font-medium text-slate-700">{complaint.department_id}</div>
                  <div className="text-xs text-slate-400 mt-0.5">{complaint.district}</div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <StatusPill type="severity" value={complaint.severity} />
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <StatusPill type="status" value={complaint.status} />
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm">
                  {complaint.sla_status === 'Warning' ? (
                    <div className="flex items-center text-amber-600 font-medium bg-amber-50 px-2.5 py-1 rounded-md inline-flex border border-amber-100">
                      <AlertTriangle className="w-4 h-4 mr-1.5" />
                      Action Required
                    </div>
                  ) : (
                    <div className="flex items-center text-vacb-600 font-medium px-2.5 py-1">
                      {complaint.sla_status || 'On Track'}
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}