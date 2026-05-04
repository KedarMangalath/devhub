import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { api } from '../services/api';
import { StatusBadge } from '../components/Badges';
import { Search, CheckCircle2, Clock, AlertTriangle, Link as LinkIcon } from 'lucide-react';

export default function TrackComplaint() {
  const [searchParams] = useSearchParams();
  const initialId = searchParams.get('id') || '';
  const isNew = searchParams.get('new') === 'true';
  
  const [trackingId, setTrackingId] = useState(initialId);
  const [complaint, setComplaint] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSearch = async (e) => {
    if (e) e.preventDefault();
    if (!trackingId.trim()) return;
    
    setLoading(true);
    setError('');
    try {
      const data = await api.getComplaintById(trackingId);
      if (data) {
        setComplaint(data);
      } else {
        setComplaint(null);
        setError('Complaint ID not found. Please check and try again.');
      }
    } catch (err) {
      setError('Error fetching data.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (initialId) {
      handleSearch();
    }
  }, [initialId]);

  return (
    <div className="max-w-4xl mx-auto">
      {isNew && (
        <div className="mb-8 bg-green-50 border border-green-200 text-green-800 rounded-lg p-4 flex items-start">
          <CheckCircle2 className="h-6 w-6 mr-3 flex-shrink-0 mt-0.5" />
          <div>
            <h3 className="font-bold text-lg">Complaint Submitted Successfully</h3>
            <p>Your complaint has been logged on the blockchain. Please save your Tracking ID: <strong className="font-mono bg-green-100 px-2 py-1 rounded">{initialId}</strong></p>
          </div>
        </div>
      )}

      <div className="card p-6 mb-8">
        <h2 className="text-xl font-bold text-gray-900 mb-4">Track Complaint Status</h2>
        <form onSubmit={handleSearch} className="flex gap-4">
          <div className="flex-grow">
            <input 
              type="text" 
              value={trackingId}
              onChange={(e) => setTrackingId(e.target.value)}
              placeholder="Enter C3MS Tracking ID (e.g., C3MS-8492)"
              className="input-field text-lg font-mono"
            />
          </div>
          <button type="submit" disabled={loading} className="btn-primary flex items-center">
            <Search className="h-5 w-5 mr-2" />
            Track
          </button>
        </form>
        {error && <p className="text-red-600 mt-3 text-sm">{error}</p>}
      </div>

      {loading && <div className="text-center py-12 text-gray-500">Searching blockchain ledger...</div>}

      {complaint && !loading && (
        <div className="space-y-6">
          <div className="card p-6">
            <div className="flex flex-col md:flex-row justify-between md:items-center border-b pb-4 mb-4">
              <div>
                <h3 className="text-2xl font-bold text-gray-900 font-mono">{complaint.id}</h3>
                <p className="text-gray-500">Filed on {complaint.date} • {complaint.department}</p>
              </div>
              <div className="mt-4 md:mt-0">
                <StatusBadge status={complaint.status} />
              </div>
            </div>
            
            <div className="mb-6">
              <h4 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-2">Subject</h4>
              <p className="text-gray-900">{complaint.category} at {complaint.location}</p>
            </div>

            <div>
              <h4 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-4">Blockchain Audit Trail</h4>
              <div className="relative border-l-2 border-gray-200 ml-3 space-y-6">
                {complaint.timeline.map((event, idx) => (
                  <div key={idx} className="relative pl-6">
                    <div className="absolute -left-1.5 top-1.5 w-3 h-3 bg-vacb-500 rounded-full ring-4 ring-white"></div>
                    <div className="bg-gray-50 rounded-md p-3 border border-gray-100">
                      <div className="flex justify-between items-start mb-1">
                        <span className="font-medium text-gray-900">{event.action}</span>
                        <span className="text-xs text-gray-500 flex items-center">
                          <Clock className="h-3 w-3 mr-1" /> {event.date}
                        </span>
                      </div>
                      <div className="flex justify-between items-center mt-2">
                        <span className="text-xs text-gray-600">Actor: {event.actor}</span>
                        <span className="text-xs font-mono text-gray-400 flex items-center" title="Blockchain Tx Hash">
                          <LinkIcon className="h-3 w-3 mr-1" /> 
                          {event.hash.substring(0, 10)}...{event.hash.substring(event.hash.length - 4)}
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {complaint.status === 'Resolved' && (
            <div className="bg-vacb-50 border border-vacb-200 rounded-lg p-4 flex items-start">
              <AlertTriangle className="h-5 w-5 text-vacb-600 mr-3 mt-0.5" />
              <div>
                <h4 className="font-medium text-vacb-900">Resolution Acknowledgment</h4>
                <p className="text-sm text-vacb-800 mt-1">This complaint has been marked as resolved. If you are not satisfied with the outcome, you have 7 days to raise a dispute.</p>
                <button className="mt-3 bg-white border border-vacb-300 text-vacb-700 px-3 py-1.5 rounded text-sm font-medium hover:bg-vacb-50">
                  Raise Dispute
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}