import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../services/api';
import { UploadCloud, ShieldCheck, AlertCircle, Loader2 } from 'lucide-react';

export default function SubmitComplaint() {
  const navigate = useNavigate();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formData, setFormData] = useState({
    isAnonymous: false,
    name: '',
    phone: '',
    department: '',
    location: '',
    category: '',
    description: '',
    hasEvidence: false
  });

  const handleChange = (e) => {
    const value = e.target.type === 'checkbox' ? e.target.checked : e.target.value;
    setFormData({ ...formData, [e.target.name]: value });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsSubmitting(true);
    try {
      const result = await api.submitComplaint(formData);
      navigate(`/track?id=${result.id}&new=true`);
    } catch (error) {
      console.error("Submission failed", error);
      setIsSubmitting(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">File a Complaint</h1>
        <p className="text-gray-600 mt-2">Your submission will be processed by our AI engine and secured on the blockchain.</p>
      </div>

      <div className="card p-6 md:p-8">
        <form onSubmit={handleSubmit} className="space-y-6">
          
          {/* Identity Section */}
          <div className="bg-gray-50 p-4 rounded-lg border border-gray-200">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-medium text-gray-900 flex items-center">
                <ShieldCheck className="h-5 w-5 text-vacb-600 mr-2" />
                Complainant Details
              </h3>
              <label className="flex items-center space-x-2 text-sm font-medium text-gray-700 cursor-pointer">
                <input 
                  type="checkbox" 
                  name="isAnonymous"
                  checked={formData.isAnonymous}
                  onChange={handleChange}
                  className="rounded text-vacb-600 focus:ring-vacb-500 h-4 w-4"
                />
                <span>Submit Anonymously</span>
              </label>
            </div>
            
            {!formData.isAnonymous && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Full Name</label>
                  <input required type="text" name="name" value={formData.name} onChange={handleChange} className="input-field" placeholder="John Doe" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Mobile Number (for OTP/Updates)</label>
                  <input required type="tel" name="phone" value={formData.phone} onChange={handleChange} className="input-field" placeholder="10-digit number" />
                </div>
              </div>
            )}
            {formData.isAnonymous && (
              <div className="text-sm text-gray-600 flex items-start">
                <AlertCircle className="h-5 w-5 text-amber-500 mr-2 flex-shrink-0" />
                <p>Your identity will be tokenized. You will still receive a tracking ID, but VACB officers will not see your personal details unless legally mandated.</p>
              </div>
            )}
          </div>

          {/* Incident Details */}
          <div className="space-y-4">
            <h3 className="text-lg font-medium text-gray-900 border-b pb-2">Incident Details</h3>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Department Involved</label>
                <select required name="department" value={formData.department} onChange={handleChange} className="input-field">
                  <option value="">Select Department</option>
                  <option value="Revenue">Revenue</option>
                  <option value="PWD">Public Works Dept (PWD)</option>
                  <option value="Police">Police</option>
                  <option value="LSGD">Local Self Govt (LSGD)</option>
                  <option value="Health">Health</option>
                  <option value="Other">Other</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Office Location / District</label>
                <input required type="text" name="location" value={formData.location} onChange={handleChange} className="input-field" placeholder="e.g., Taluk Office, Kochi" />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Complaint Category</label>
              <select required name="category" value={formData.category} onChange={handleChange} className="input-field">
                <option value="">Select Category</option>
                <option value="Bribery">Bribery / Demanding Money</option>
                <option value="Service Denial">Denial of Service</option>
                <option value="Favoritism">Favoritism / Nepotism</option>
                <option value="Misappropriation">Misappropriation of Funds</option>
                <option value="Contractor Fraud">Contractor Fraud / Poor Quality</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Detailed Description</label>
              <textarea 
                required 
                name="description" 
                value={formData.description} 
                onChange={handleChange} 
                rows="5" 
                className="input-field"
                placeholder="Describe the incident in detail. Our AI will automatically extract key entities and summarize this for investigators."
              ></textarea>
            </div>
          </div>

          {/* Evidence Upload (Simulated) */}
          <div>
            <h3 className="text-lg font-medium text-gray-900 border-b pb-2 mb-4">Supporting Evidence</h3>
            <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center hover:bg-gray-50 transition-colors">
              <UploadCloud className="h-10 w-10 text-gray-400 mx-auto mb-2" />
              <p className="text-sm text-gray-600">Drag and drop files here, or click to browse</p>
              <p className="text-xs text-gray-500 mt-1">Supports JPG, PNG, MP3, MP4, PDF (Max 50MB)</p>
              <div className="mt-4">
                <label className="inline-flex items-center">
                  <input type="checkbox" name="hasEvidence" checked={formData.hasEvidence} onChange={handleChange} className="rounded text-vacb-600 focus:ring-vacb-500 h-4 w-4 mr-2" />
                  <span className="text-sm text-gray-700">Simulate attaching evidence files</span>
                </label>
              </div>
            </div>
          </div>

          <div className="pt-4 flex justify-end">
            <button 
              type="submit" 
              disabled={isSubmitting}
              className="btn-primary w-full md:w-auto flex items-center justify-center min-w-[200px]"
            >
              {isSubmitting ? (
                <><Loader2 className="animate-spin h-5 w-5 mr-2" /> Processing via AI...</>
              ) : (
                'Submit Securely'
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}