import React from 'react';
import { AlertCircle } from 'lucide-react';

export default function ComplaintForm({ formData, onChange }) {
  const handleChange = (e) => {
    const { name, value } = e.target;
    onChange({ ...formData, [name]: value });
  };

  const categories = [
    "Bribery / Demand for Money",
    "Public Fund Misappropriation",
    "Delay in Service Delivery",
    "Abuse of Official Position",
    "Disproportionate Assets",
    "Other"
  ];

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 flex items-start gap-3">
        <AlertCircle className="w-5 h-5 text-amber-600 mt-0.5 flex-shrink-0" />
        <div>
          <h4 className="text-sm font-semibold text-amber-800">Provide specific details</h4>
          <p className="text-sm text-amber-700 mt-1">
            Clear, factual information helps our AI system process your grievance faster and assign it to the correct investigating officer.
          </p>
        </div>
      </div>

      <div className="space-y-5">
        <div>
          <label htmlFor="title" className="block text-sm font-medium text-slate-700 mb-1.5">
            Complaint Title <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            id="title"
            name="title"
            value={formData?.title || ''}
            onChange={handleChange}
            placeholder="e.g., Demand for bribe for Land Possession Certificate"
            className="w-full rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-slate-900 placeholder:text-slate-400 focus:border-vacb-500 focus:outline-none focus:ring-2 focus:ring-vacb-500/20 transition-colors"
            required
          />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          <div>
            <label htmlFor="category" className="block text-sm font-medium text-slate-700 mb-1.5">
              Category <span className="text-red-500">*</span>
            </label>
            <div className="relative">
              <select
                id="category"
                name="category"
                value={formData?.category || ''}
                onChange={handleChange}
                className="w-full rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-slate-900 focus:border-vacb-500 focus:outline-none focus:ring-2 focus:ring-vacb-500/20 transition-colors appearance-none"
                required
              >
                <option value="" disabled>Select a category</option>
                {categories.map((cat) => (
                  <option key={cat} value={cat}>{cat}</option>
                ))}
              </select>
              <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-4 text-slate-500">
                <svg className="h-4 w-4 fill-current" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20">
                  <path d="M9.293 12.95l.707.707L15.657 8l-1.414-1.414L10 10.828 5.757 6.586 4.343 8z" />
                </svg>
              </div>
            </div>
          </div>

          <div>
            <label htmlFor="location" className="block text-sm font-medium text-slate-700 mb-1.5">
              Location / District <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              id="location"
              name="location"
              value={formData?.location || ''}
              onChange={handleChange}
              placeholder="e.g., Taluk Office, Ernakulam"
              className="w-full rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-slate-900 placeholder:text-slate-400 focus:border-vacb-500 focus:outline-none focus:ring-2 focus:ring-vacb-500/20 transition-colors"
              required
            />
          </div>
        </div>

        <div>
          <label htmlFor="description" className="block text-sm font-medium text-slate-700 mb-1.5">
            Detailed Description <span className="text-red-500">*</span>
          </label>
          <textarea
            id="description"
            name="description"
            value={formData?.description || ''}
            onChange={handleChange}
            rows={6}
            placeholder="Describe the incident in detail. Include dates, times, names of officials involved (if known), and the exact sequence of events..."
            className="w-full rounded-lg border border-slate-300 bg-white px-4 py-3 text-slate-900 placeholder:text-slate-400 focus:border-vacb-500 focus:outline-none focus:ring-2 focus:ring-vacb-500/20 transition-colors resize-y"
            required
          />
          <div className="flex justify-between items-center mt-2">
            <p className="text-xs text-slate-500">
              Please do not include sensitive personal information like bank account numbers unless directly relevant to the evidence.
            </p>
            <p className="text-xs font-medium text-slate-500">
              {formData?.description?.length || 0} characters
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}