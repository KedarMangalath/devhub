import { useState } from 'react';
import { submitComplaint } from '../services/api';
import { CheckCircle2, AlertCircle } from 'lucide-react';

const DISTRICTS = ['Thiruvananthapuram', 'Kollam', 'Pathanamthitta', 'Alappuzha', 'Kottayam', 'Idukki', 'Ernakulam', 'Thrissur', 'Palakkad', 'Malappuram', 'Kozhikode', 'Wayanad', 'Kannur', 'Kasaragod'];

export default function SubmitComplaint() {
  const [formData, setFormData] = useState({ title: '', description: '', location: '', is_anonymous: false });
  const [status, setStatus] = useState({ loading: false, error: null, success: null });

  const handleSubmit = async (e) => {
    e.preventDefault();
    setStatus({ loading: true, error: null, success: null });
    try {
      const res = await submitComplaint(formData);
      setStatus({ loading: false, error: null, success: res });
      setFormData({ title: '', description: '', location: '', is_anonymous: false });
    } catch (err) {
      setStatus({ loading: false, error: err.message, success: null });
    }
  };

  if (status.success) {
    return (
      <div className="max-w-2xl mx-auto bg-white p-8 rounded-xl shadow-sm border border-green-200 text-center">
        <CheckCircle2 className="w-16 h-16 text-green-500 mx-auto mb-4" />
        <h2 className="text-2xl font-bold text-gray-900 mb-2">Complaint Registered Successfully</h2>
        <p className="text-gray-600 mb-6">Your complaint has been securely logged and analyzed by our AI system.</p>
        <div className="bg-gray-50 p-4 rounded-lg inline-block mb-6">
          <p className="text-sm text-gray-500 uppercase tracking-wide">Your Tracking ID</p>
          <p className="text-2xl font-mono font-bold text-vacb-700">{status.success.tracking_id}</p>
        </div>
        <div className="text-left bg-blue-50 p-4 rounded-lg border border-blue-100">
          <h4 className="font-semibold text-blue-900 mb-1">AI Initial Assessment:</h4>
          <ul className="text-sm text-blue-800 space-y-1">
            <li>Category: <strong>{status.success.ai_analysis.category}</strong></li>
            <li>Priority: <strong>{status.success.ai_analysis.priority}</strong></li>
          </ul>
        </div>
        <button onClick={() => setStatus({ loading: false, error: null, success: null })} className="mt-8 text-vacb-600 font-medium hover:underline">
          Submit another complaint
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Report Corruption</h1>
        <p className="text-gray-600 mt-2">Provide details about the incident. You can choose to remain anonymous.</p>
      </div>

      {status.error && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg flex items-center text-red-700">
          <AlertCircle className="w-5 h-5 mr-2" /> {status.error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="bg-white p-6 rounded-xl shadow-sm border border-gray-200 space-y-6">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Incident Title</label>
          <input 
            required 
            type="text" 
            className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-vacb-500 focus:border-vacb-500"
            placeholder="e.g., Demand for bribe at Village Office"
            value={formData.title}
            onChange={e => setFormData({...formData, title: e.target.value})}
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Detailed Description</label>
          <textarea 
            required 
            rows={5}
            className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-vacb-500 focus:border-vacb-500"
            placeholder="Describe what happened, who was involved, and when..."
            value={formData.description}
            onChange={e => setFormData({...formData, description: e.target.value})}
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">District / Location</label>
          <select 
            required
            className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-vacb-500 focus:border-vacb-500"
            value={formData.location}
            onChange={e => setFormData({...formData, location: e.target.value})}
          >
            <option value="">Select District</option>
            {DISTRICTS.map(d => <option key={d} value={d}>{d}</option>)}
          </select>
        </div>

        <div className="flex items-center">
          <input 
            id="anonymous" 
            type="checkbox" 
            className="h-4 w-4 text-vacb-600 focus:ring-vacb-500 border-gray-300 rounded"
            checked={formData.is_anonymous}
            onChange={e => setFormData({...formData, is_anonymous: e.target.checked})}
          />
          <label htmlFor="anonymous" className="ml-2 block text-sm text-gray-900">
            Submit Anonymously (Your identity will not be recorded)
          </label>
        </div>

        <button 
          type="submit" 
          disabled={status.loading}
          className="w-full flex justify-center py-3 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-vacb-600 hover:bg-vacb-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-vacb-500 disabled:opacity-50"
        >
          {status.loading ? 'Processing via AI...' : 'Submit Securely'}
        </button>
      </form>
    </div>
  );
}