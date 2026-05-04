import { useState, useEffect } from 'react';
import { getComplaints, updateComplaintStatus } from '../services/api';
import { BrainCircuit, ShieldAlert, UserX } from 'lucide-react';

export default function AdminComplaints() {
  const [complaints, setComplaints] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchComplaints = async () => {
    const data = await getComplaints();
    setComplaints(data);
    setLoading(false);
  };

  useEffect(() => {
    fetchComplaints();
  }, []);

  const handleStatusChange = async (id, newStatus) => {
    await updateComplaintStatus(id, newStatus);
    fetchComplaints();
  };

  const getPriorityColor = (pri) => {
    if (pri === 'Critical') return 'bg-red-100 text-red-800';
    if (pri === 'High') return 'bg-orange-100 text-orange-800';
    if (pri === 'Medium') return 'bg-yellow-100 text-yellow-800';
    return 'bg-green-100 text-green-800';
  };

  if (loading) return <div className="p-8">Loading records...</div>;

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-gray-900">Complaint Registry</h1>
        <span className="px-3 py-1 bg-vacb-100 text-vacb-800 rounded-full text-sm font-medium">
          {complaints.length} Total Records
        </span>
      </div>

      <div className="bg-white shadow-sm border border-gray-200 rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">ID / Date</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Details</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">AI Analysis</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {complaints.map((c) => (
                <tr key={c.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="text-sm font-mono font-medium text-gray-900">{c.tracking_id}</div>
                    <div className="text-xs text-gray-500">{new Date(c.created_at).toLocaleDateString()}</div>
                    {c.is_anonymous === 1 && (
                      <div className="mt-1 flex items-center text-xs text-purple-600 bg-purple-50 w-max px-2 py-0.5 rounded">
                        <UserX size={12} className="mr-1"/> Anonymous
                      </div>
                    )}
                  </td>
                  <td className="px-6 py-4">
                    <div className="text-sm font-medium text-gray-900 mb-1">{c.title}</div>
                    <div className="text-sm text-gray-500 line-clamp-2 w-64" title={c.description}>{c.description}</div>
                    <div className="text-xs text-gray-400 mt-1">📍 {c.location}</div>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex flex-col gap-2">
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium w-max ${getPriorityColor(c.priority)}`}>
                        <ShieldAlert size={12} className="mr-1"/> {c.priority} Priority
                      </span>
                      <span className="inline-flex items-center text-xs text-gray-600">
                        <BrainCircuit size={12} className="mr-1 text-blue-500"/> 
                        Credibility: {c.credibility_score}/100
                      </span>
                      <span className="text-xs font-medium text-gray-700 bg-gray-100 px-2 py-1 rounded w-max">
                        {c.category}
                      </span>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <select
                      value={c.status}
                      onChange={(e) => handleStatusChange(c.id, e.target.value)}
                      className={`text-sm rounded-md border-gray-300 shadow-sm focus:border-vacb-500 focus:ring-vacb-500 ${
                        c.status === 'Resolved' ? 'bg-green-50 text-green-700' : 
                        c.status === 'Pending' ? 'bg-orange-50 text-orange-700' : 'bg-blue-50 text-blue-700'
                      }`}
                    >
                      <option value="Pending">Pending</option>
                      <option value="Under Investigation">Under Investigation</option>
                      <option value="Resolved">Resolved</option>
                      <option value="Dismissed">Dismissed</option>
                    </select>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}