import React from 'react';
import { ShieldCheck } from 'lucide-react';

export default function ReviewSubmitCard({ 
  formData = {}, 
  departmentName = 'Not Selected', 
  files = [], 
  onSubmit 
}) {
  const {
    title = 'No title provided',
    description = 'No description provided',
    category = 'Not specified',
    district = 'Not specified',
    incidentDate = 'Not specified',
    isAnonymous = false
  } = formData;

  return (
    <div className="bg-white rounded-lg border border-slate-200 shadow-sm overflow-hidden font-sans">
      <div className="p-6 border-b border-slate-200 bg-slate-50 flex items-center gap-3">
        <ShieldCheck className="w-6 h-6 text-[#047857]" />
        <h3 className="text-lg font-semibold text-slate-900">Review Your Complaint</h3>
      </div>
      
      <div className="p-6 space-y-8">
        {/* Department & Basic Info */}
        <section>
          <h4 className="text-sm font-semibold text-slate-900 uppercase tracking-wider mb-4 border-b border-slate-100 pb-2">
            Target Department
          </h4>
          <div className="bg-slate-50 p-4 rounded-md border border-slate-100">
            <p className="text-slate-900 font-medium">{departmentName}</p>
          </div>
        </section>

        {/* Complaint Details */}
        <section>
          <h4 className="text-sm font-semibold text-slate-900 uppercase tracking-wider mb-4 border-b border-slate-100 pb-2">
            Complaint Details
          </h4>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="md:col-span-2">
              <label className="block text-xs font-medium text-slate-500 mb-1">Title</label>
              <p className="text-slate-900 font-medium">{title}</p>
            </div>
            
            <div className="md:col-span-2">
              <label className="block text-xs font-medium text-slate-500 mb-1">Description</label>
              <p className="text-slate-700 text-sm whitespace-pre-wrap leading-relaxed bg-slate-50 p-4 rounded-md border border-slate-100">
                {description}
              </p>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1">Category</label>
              <p className="text-slate-900">{category}</p>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1">District</label>
              <p className="text-slate-900">{district}</p>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1">Date of Incident</label>
              <p className="text-slate-900">{incidentDate}</p>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1">Filing Preference</label>
              <p className="text-slate-900">
                {isAnonymous ? (
                  <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-800">
                    Anonymous Filing
                  </span>
                ) : (
                  <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                    Standard Filing
                  </span>
                )}
              </p>
            </div>
          </div>
        </section>

        {/* Evidence */}
        <section>
          <h4 className="text-sm font-semibold text-slate-900 uppercase tracking-wider mb-4 border-b border-slate-100 pb-2">
            Attached Evidence
          </h4>
          {files.length > 0 ? (
            <ul className="space-y-2">
              {files.map((file, index) => (
                <li key={index} className="flex items-center text-sm text-slate-700 bg-slate-50 p-3 rounded-md border border-slate-100">
                  <span className="w-2 h-2 rounded-full bg-[#047857] mr-3"></span>
                  {file.name || `Attachment_${index + 1}.pdf`}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-slate-500 italic">No evidence files attached.</p>
          )}
        </section>
      </div>

      <div className="p-6 bg-slate-50 border-t border-slate-200 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="text-xs text-slate-500 max-w-md">
          By submitting, you confirm that the information provided is true to the best of your knowledge. 
          Your submission will be securely logged on the immutable C3MS blockchain ledger.
        </div>
        <button
          onClick={onSubmit}
          className="w-full sm:w-auto inline-flex items-center justify-center px-6 py-3 border border-transparent text-base font-medium rounded-md text-white bg-[#047857] hover:bg-blue-800 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[#047857] shadow-sm transition-colors"
        >
          <ShieldCheck className="w-5 h-5 mr-2" />
          Submit Securely
        </button>
      </div>
    </div>
  );
}