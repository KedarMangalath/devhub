import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../services/api';
import { StatusBadge, SeverityBadge } from '../components/Badges';
import { BrainCircuit, Shield, FileText, Clock, Link as LinkIcon, UserX, UserCheck, AlertTriangle, CheckCircle } from 'lucide-react';

export default function ComplaintDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [complaint, setComplaint] = useState(null);
  const [loading, setLoading] = useState(true);
  const [actionNote, setActionNote] = useState('');
  const [isUpdating, setIsUpdating] = useState(false);

  useEffect(() => {
    const fetchDetail = async () => {
      const data = await api.getComplaintById(id);
      setComplaint(data);
      setLoading(false);
    };
    fetchDetail();
  }, [id]);

  const handleStatusUpdate = async (newStatus) => {
    setIsUpdating(true);
    try {
      const result = await api.updateComplaintStatus(id, newStatus, actionNote);
      setComplaint(result.complaint);
      setActionNote('');
    } catch (e) {
      console.error(e);
    } finally {
      setIsUpdating(false);
    }
  };

  if (loading) return <div className="py-12 text-center">Loading case details...</div>;
  if (!complaint) return <div className="py-12 text-center text-red-600">Complaint not found.</div>;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <div className="flex items-center space-x-3 mb-1">
            <h1 className="text-2xl font-bold text-gray-900 font-mono">{complaint.id}</h1>
            <StatusBadge status={complaint.status} />
            <SeverityBadge severity={complaint.severity} />
          </div>
          <p className="text-gray-500">Filed on {complaint.date} • {complaint.department} ({complaint.location})</p>
        </div>
        <button onClick={() => navigate('/officer')} className="btn-secondary text-sm">
          &larr; Back to Queue
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Details & Evidence */}
        <div className="lg:col-span-2 space-y-6">
          <div className="card p-6">
            <h3 className="text-lg font-semibold border-b pb-2 mb-4 flex items-center">
              <FileText className="h-5 w-5 mr-2 text-gray-500" /> Original Complaint
            </h3>
            <div className="bg-gray-50 p-4 rounded-md text-gray-800 whitespace-pre-wrap">
              {complaint.description}
            </div>
            
            <div className="mt-6">
              <h4 className="font-medium text-gray-900 mb-3">Attached Evidence</h4>
              {complaint.evidence && complaint.evidence.length > 0 ? (
                <div className="flex gap-4 overflow-x-auto pb-2">
                  {complaint.evidence.map((img, i) => (
                    <div key={i} className="relative group">
                      <img src={img} alt="Evidence" className="h-32 w-48 object-cover rounded border border-gray-200" />
                      <div className="absolute inset-0 bg-black bg-opacity-0 group-hover:bg-opacity-40 transition-all flex items-center justify-center rounded">
                        <span className="text-white opacity-0 group-hover:opacity-100 text-sm font-medium">View Full</span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-gray-500 italic">No evidence files attached.</p>
              )}
            </div>
          </div>

          {/* Blockchain Log */}
          <div className="card p-6">
            <h3 className="text-lg font-semibold border-b pb-2 mb-4 flex items-center">
              <Shield className="h-5 w-5 mr-2 text-green-600" /> Immutable Audit Log
            </h3>
            <div className="space-y-4">
              {complaint.timeline.map((event, idx) => (
                <div key={idx} className="flex items-start">
                  <div className="mt-1 mr-3">
                    <div className="h-2 w-2 rounded-full bg-green-500"></div>
                    {idx !== complaint.timeline.length - 1 && <div className="h-full w-0.5 bg-gray-200 ml-1 mt-1"></div>}
                  </div>
                  <div className="flex-grow">
                    <p className="text-sm font-medium text-gray-900">{event.action}</p>
                    <div className="flex justify-between mt-1">
                      <span className="text-xs text-gray-500">{event.date} • Actor: {event.actor}</span>
                      <span className="text-xs font-mono text-gray-400 flex items-center">
                        <LinkIcon className="h-3 w-3 mr-1" /> {event.hash.substring(0, 16)}...
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right Column: AI Insights & Actions */}
        <div className="space-y-6">
          {/* AI Panel */}
          <div className="card p-6 border-t-4 border-t-purple-500">
            <h3 className="text-lg font-semibold mb-4 flex items-center text-purple-900">
              <BrainCircuit className="h-5 w-5 mr-2 text-purple-600" /> AI Insights
            </h3>
            
            <div className="mb-4">
              <div className="flex justify-between text-sm mb-1">
                <span className="text-gray-600">Credibility Score</span>
                <span className="font-bold">{complaint.aiScore}/100</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div 
                  className={`h-2 rounded-full ${complaint.aiScore > 80 ? 'bg-red-500' : complaint.aiScore > 60 ? 'bg-yellow-500' : 'bg-green-500'}`}
                  style={{ width: `${complaint.aiScore}%` }}
                ></div>
              </div>
              <p className="text-xs text-gray-500 mt-1">
                {complaint.aiScore > 80 ? 'High probability of valid grievance based on historical patterns.' : 'Standard verification required.'}
              </p>
            </div>

            <div>
              <h4 className="text-sm font-medium text-gray-700 mb-1">Auto-Summary</h4>
              <p className="text-sm text-gray-600 bg-purple-50 p-3 rounded border border-purple-100">
                {complaint.aiSummary}
              </p>
            </div>
          </div>

          {/* Complainant Info */}
          <div className="card p-6">
            <h3 className="text-lg font-semibold border-b pb-2 mb-4">Complainant</h3>
            {complaint.complainant.isAnonymous ? (
              <div className="flex items-center text-amber-600 bg-amber-50 p-3 rounded">
                <UserX className="h-5 w-5 mr-2" />
                <div>
                  <p className="font-medium">Anonymous Submission</p>
                  <p className="text-xs">Identity tokenized. Contact via system proxy only.</p>
                </div>
              </div>
            ) : (
              <div className="flex items-center text-gray-700">
                <UserCheck className="h-8 w-8 mr-3 text-gray-400" />
                <div>
                  <p className="font-medium">{complaint.complainant.name}</p>
                  <p className="text-sm text-gray-500">Ph: {complaint.complainant.phone}</p>
                </div>
              </div>
            )}
          </div>

          {/* Action Panel */}
          <div className="card p-6 bg-gray-50">
            <h3 className="text-lg font-semibold mb-4">Case Actions</h3>
            <textarea 
              className="input-field text-sm mb-3"
              rows="3"
              placeholder="Add internal notes or action description..."
              value={actionNote}
              onChange={(e) => setActionNote(e.target.value)}
            ></textarea>
            
            <div className="space-y-2">
              {complaint.status !== 'Investigation In Progress' && (
                <button 
                  onClick={() => handleStatusUpdate('Investigation In Progress')}
                  disabled={isUpdating}
                  className="w-full btn-primary bg-blue-600 hover:bg-blue-700 flex justify-center items-center"
                >
                  <Clock className="h-4 w-4 mr-2" /> Begin Investigation
                </button>
              )}
              
              <button 
                onClick={() => handleStatusUpdate('Escalated')}
                disabled={isUpdating}
                className="w-full btn-secondary text-red-600 border-red-200 hover:bg-red-50 flex justify-center items-center"
              >
                <AlertTriangle className="h-4 w-4 mr-2" /> Escalate to Supervisor
              </button>

              {complaint.status !== 'Resolved' && (
                <button 
                  onClick={() => handleStatusUpdate('Resolved')}
                  disabled={isUpdating || !actionNote}
                  className="w-full btn-secondary text-green-600 border-green-200 hover:bg-green-50 flex justify-center items-center"
                  title={!actionNote ? "Please add a note before resolving" : ""}
                >
                  <CheckCircle className="h-4 w-4 mr-2" /> Mark as Resolved
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}