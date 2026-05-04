import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../services/api';
import { StatusBadge, SeverityBadge } from '../components/Badges';
import { Filter, Search, AlertCircle, BrainCircuit } from 'lucide-react';

export default function OfficerDashboard() {
  const [complaints, setComplaints] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('All');

  useEffect(() => {
    const fetchComplaints = async () => {
      const data = await api.getComplaints();
      setComplaints(data);
      setLoading(false);
    };
    fetchComplaints();
  }, []);

  const filteredComplaints = complaints.filter(c => {
    if (filter === 'All') return true;
    if (filter === 'Action Required') return ['Submitted', 'Under Review', 'Escalated'].includes(c.status);
    return c.status === filter;
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Investigator Workspace</h1>
          <p className="text-gray-500 text-sm">Manage assigned cases and AI-flagged anomalies.</p>
        </div>
        <div className="flex items-center space-x-2">
          <span className="text-sm text-gray-500 flex items-center">
            <BrainCircuit className="h-4 w-4 mr-1 text-purple-500" /> AI Triage Active
          </span>
        </div>
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="card p-4 border-l-4 border-l-vacb-500">
          <div className="text-sm text-gray-500">Total Assigned</div>
          <div className="text-2xl font-bold">{complaints.length}</div>
        </div>
        <div className="card p-4 border-l-4 border-l-red-500">
          <div className="text-sm text-gray-500">Critical / Escalated</div>
          <div className="text-2xl font-bold text-red-600">
            {complaints.filter(c => c.severity === 'Critical' || c.status === 'Escalated').length}
          </div>
        </div>
        <div className="card p-4 border-l-4 border-l-yellow-500">
          <div className="text-sm text-gray-500">SLA Warning (&lt;5 days)</div>
          <div className="text-2xl font-bold text-yellow-600">3</div>
        </div>
        <div className="card p-4 border-l-4 border-l-green-500">
          <div className="text-sm text-gray-500">Resolved (30d)</div>
          <div className="text-2xl font-bold text-green-600">
            {complaints.filter(c => c.status === 'Resolved').length}
          </div>
        </div>
      </div>

      {/* Main Table Area */}
      <div className="card">
        <div className="p-4 border-b border-gray-200 flex flex-col sm:flex-row justify-between items-center gap-4 bg-gray-50">
          <div className="flex items-center space-x-2 w-full sm:w-auto">
            <Filter className="h-5 w-5 text-gray-400" />
            <select 
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              className="input-field py-1.5 text-sm w-full sm:w-auto"
            >
              <option value="All">All Complaints</option>
              <option value="Action Required">Action Required</option>
              <option value="Investigation In Progress">In Progress</option>
              <option value="Resolved">Resolved</option>
            </select>
          </div>
          <div className="relative w-full sm:w-64">
            <input type="text" placeholder="Search ID, Dept..." className="input-field py-1.5 pl-8 text-sm w-full" />
            <Search className="h-4 w-4 text-gray-400 absolute left-2.5 top-2.5" />
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-gray-50 text-gray-600 uppercase text-xs">
              <tr>
                <th className="px-4 py-3">ID & Date</th>
                <th className="px-4 py-3">Department / Location</th>
                <th className="px-4 py-3">Category</th>
                <th className="px-4 py-3">AI Score</th>
                <th className="px-4 py-3">Severity</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {loading ? (
                <tr><td colSpan="7" className="text-center py-8 text-gray-500">Loading cases...</td></tr>
              ) : filteredComplaints.map((c) => (
                <tr key={c.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3">
                    <div className="font-mono font-medium text-vacb-700">{c.id}</div>
                    <div className="text-xs text-gray-500">{c.date}</div>
                  </td>
                  <td className="px-4 py-3">
                    <div className="font-medium text-gray-900">{c.department}</div>
                    <div className="text-xs text-gray-500 truncate max-w-[150px]">{c.location}</div>
                  </td>
                  <td className="px-4 py-3">{c.category}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center">
                      <span className={`font-bold ${c.aiScore > 85 ? 'text-red-600' : c.aiScore > 70 ? 'text-yellow-600' : 'text-green-600'}`}>
                        {c.aiScore}
                      </span>
                      <span className="text-xs text-gray-400 ml-1">/100</span>
                    </div>
                  </td>
                  <td className="px-4 py-3"><SeverityBadge severity={c.severity} /></td>
                  <td className="px-4 py-3"><StatusBadge status={c.status} /></td>
                  <td className="px-4 py-3 text-right">
                    <Link to={`/officer/complaint/${c.id}`} className="text-vacb-600 hover:text-vacb-900 font-medium">
                      Review
                    </Link>
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