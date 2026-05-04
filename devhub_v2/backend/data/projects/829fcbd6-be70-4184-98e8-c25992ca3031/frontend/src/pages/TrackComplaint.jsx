import { useState } from 'react';
import { trackComplaint } from '../services/api';
import { Search, Clock, CheckCircle, ShieldAlert, FileText } from 'lucide-react';

export default function TrackComplaint() {
  const [trackingId, setTrackingId] = useState('');
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!trackingId) return;
    setLoading(true); setError(''); setResult(null);
    try {
      const data = await trackComplaint(trackingId);
      setResult(data);
    } catch (err) {
      setError('Complaint not found or invalid Tracking ID.');
    } finally {
      setLoading(false);
    }
  };

  const getStatusIcon = (status) => {
    switch(status) {
      case 'Resolved': return <CheckCircle className="text-green-500" />;
      case 'Under Investigation': return <Search className="text-blue-500" />;
      default: return <Clock className="text-orange-500" />;
    }
  };

  return (
    <div className="max-w-3xl mx-auto">
      <div className="text-center mb-10">
        <h1 className="text-3xl font-bold text-gray-900">Track Your Complaint</h1>
        <p className="text-gray-600 mt-2">Enter your unique VACB Tracking ID to view real-time status and blockchain audit logs.</p>
      </div>

      <form onSubmit={handleSearch} className="flex gap-4 mb-10">
        <input 
          type="text" 
          placeholder="e.g., VACB-A1B2C3D4"
          className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-vacb-500 focus:border-vacb-500 text-lg uppercase"
          value={trackingId}
          onChange={e => setTrackingId(e.target.value)}
        />
        <button 
          type="submit"
          disabled={loading}
          className="px-8 py-3 bg-vacb-600 text-white rounded-lg font-medium hover:bg-vacb-700 disabled:opacity-50 flex items-center gap-2"
        >
          <Search size={20} /> {loading ? 'Searching...' : 'Track'}
        </button>
      </form>

      {error && (
        <div className="p-4 bg-red-50 text-red-700 rounded-lg text-center border border-red-200">
          {error}
        </div>
      )}

      {result && (
        <div className="space-y-6">
          <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-200">
            <div className="flex justify-between items-start mb-6">
              <div>
                <p className="text-sm text-gray-500 font-mono">{result.complaint.tracking_id}</p>
                <h2 className="text-xl font-bold text-gray-900 mt-1">{result.complaint.title}</h2>
                <span className="inline-block mt-2 px-3 py-1 bg-gray-100 text-gray-700 rounded-full text-sm">
                  {result.complaint.category}
                </span>
              </div>
              <div className="flex flex-col items-end">
                <div className="flex items-center gap-2 font-semibold text-lg">
                  {getStatusIcon(result.complaint.status)}
                  {result.complaint.status}
                </div>
                <p className="text-sm text-gray-500 mt-1">
                  Filed: {new Date(result.complaint.created_at).toLocaleDateString()}
                </p>
              </div>
            </div>
          </div>

          <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-200">
            <h3 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
              <ShieldAlert className="text-vacb-600" /> Blockchain Audit Trail
            </h3>
            <div className="space-y-4">
              {result.logs.map((log, idx) => (
                <div key={idx} className="flex gap-4 p-4 bg-gray-50 rounded-lg border border-gray-100">
                  <div className="mt-1"><FileText className="text-gray-400" size={20}/></div>
                  <div className="flex-1 overflow-hidden">
                    <div className="flex justify-between">
                      <p className="font-semibold text-gray-900">{log.action.replace('_', ' ')}</p>
                      <p className="text-sm text-gray-500">{new Date(log.timestamp).toLocaleString()}</p>
                    </div>
                    <p className="text-xs text-gray-400 font-mono mt-2 truncate" title={log.data_hash}>
                      Hash: {log.data_hash}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}