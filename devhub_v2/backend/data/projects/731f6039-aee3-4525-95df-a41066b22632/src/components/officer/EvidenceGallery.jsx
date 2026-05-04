import React from 'react';
import { evidenceFiles } from '../../mockData';
import { FileText, Image as ImageIcon, Download } from 'lucide-react';

export default function EvidenceGallery({ complaintId }) {
  // Safely fallback to empty array if evidenceFiles is undefined in mockData
  const files = (evidenceFiles || []).filter(f => f.complaint_id === complaintId);

  if (files.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center p-10 bg-slate-50 rounded-xl border-2 border-dashed border-slate-200">
        <div className="w-16 h-16 bg-white rounded-full flex items-center justify-center shadow-sm mb-4">
          <ImageIcon className="w-8 h-8 text-slate-300" />
        </div>
        <h3 className="text-slate-700 font-semibold text-lg">No evidence attached</h3>
        <p className="text-sm text-slate-500 mt-1 max-w-sm text-center">
          This complaint was submitted without any supporting documents or images.
        </p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-5">
      {files.map((file) => {
        const isImage = file.file_type?.startsWith('image') || file.file_name?.match(/\.(jpg|jpeg|png|gif)$/i);
        // Generate a stable random size for mock realism
        const mockSize = ((file.file_name.length % 5) + 1.2).toFixed(1);

        return (
          <div
            key={file.id}
            className="group bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden hover:shadow-md hover:border-slate-300 transition-all duration-200 flex flex-col"
          >
            {/* Thumbnail Area */}
            <div className="h-44 bg-slate-50 relative border-b border-slate-100 flex items-center justify-center overflow-hidden">
              {isImage ? (
                <img
                  src={file.url}
                  alt={file.file_name}
                  className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                  onError={(e) => {
                    e.target.style.display = 'none';
                    if (e.target.nextSibling) {
                      e.target.nextSibling.style.display = 'flex';
                    }
                  }}
                />
              ) : null}

              {/* Fallback/Icon for non-images or broken images */}
              <div
                className={`absolute inset-0 flex items-center justify-center bg-slate-50 ${
                  isImage ? 'hidden' : 'flex'
                }`}
              >
                <div className="w-16 h-16 bg-white rounded-full flex items-center justify-center shadow-sm">
                  {isImage ? (
                    <ImageIcon className="w-8 h-8 text-slate-300" />
                  ) : (
                    <FileText className="w-8 h-8 text-slate-300" />
                  )}
                </div>
              </div>

              {/* Hover Overlay */}
              <div className="absolute inset-0 bg-slate-900/40 opacity-0 group-hover:opacity-100 transition-opacity duration-200 flex items-center justify-center gap-3 backdrop-blur-[2px]">
                <button
                  type="button"
                  className="p-2.5 bg-white text-slate-900 rounded-full hover:bg-slate-50 hover:text-vacb-700 transition-colors shadow-sm transform translate-y-2 group-hover:translate-y-0 duration-200"
                  title="Download"
                >
                  <Download className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* File Details */}
            <div className="p-4 flex flex-col flex-1 justify-between bg-white">
              <div className="flex items-start justify-between gap-3 mb-4">
                <div className="min-w-0 flex-1">
                  <p
                    className="text-sm font-semibold text-slate-900 truncate"
                    title={file.file_name}
                  >
                    {file.file_name}
                  </p>
                  <div className="flex items-center gap-2 mt-1.5">
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium bg-slate-100 text-slate-600 uppercase tracking-wider">
                      {file.file_type?.split('/')[1] || 'DOC'}
                    </span>
                    <span className="text-xs text-slate-500">
                      {mockSize} MB
                    </span>
                  </div>
                </div>
                {isImage ? (
                  <ImageIcon className="w-5 h-5 text-slate-400 flex-shrink-0 mt-0.5" />
                ) : (
                  <FileText className="w-5 h-5 text-slate-400 flex-shrink-0 mt-0.5" />
                )}
              </div>

              <button
                type="button"
                className="w-full py-2 px-3 text-sm font-medium text-vacb-700 bg-vacb-700/5 hover:bg-vacb-700/10 border border-vacb-700/10 rounded-lg transition-colors flex items-center justify-center gap-2"
              >
                View File
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}