import React, { useState, useRef } from 'react'
import { UploadCloud, FileText, X } from 'lucide-react'

export default function EvidenceUploader({ files = [], onFilesChange }) {
  const [isDragging, setIsDragging] = useState(false)
  const fileInputRef = useRef(null)

  const handleDragOver = (e) => {
    e.preventDefault()
    setIsDragging(true)
  }

  const handleDragLeave = (e) => {
    e.preventDefault()
    setIsDragging(false)
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setIsDragging(false)
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const newFiles = Array.from(e.dataTransfer.files)
      onFilesChange([...files, ...newFiles])
    }
  }

  const handleFileInput = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      const newFiles = Array.from(e.target.files)
      onFilesChange([...files, ...newFiles])
    }
  }

  const removeFile = (indexToRemove) => {
    const updatedFiles = files.filter((_, index) => index !== indexToRemove)
    onFilesChange(updatedFiles)
  }

  // Helper to format file size
  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 Bytes'
    const k = 1024
    const sizes = ['Bytes', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
  }

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold text-slate-900">Upload Evidence</h3>
        <p className="text-sm text-slate-500 mt-1">
          Attach any documents, photos, audio, or video recordings that support your complaint. 
          Strong evidence significantly improves the AI credibility score and speeds up resolution.
        </p>
      </div>

      {/* Drag & Drop Zone */}
      <div
        className={`relative border-2 border-dashed rounded-xl p-10 flex flex-col items-center justify-center transition-all duration-200 cursor-pointer ${
          isDragging
            ? 'border-blue-500 bg-blue-50'
            : 'border-slate-300 bg-slate-50 hover:bg-slate-100 hover:border-slate-400'
        }`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
      >
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleFileInput}
          className="hidden"
          multiple
          accept="image/*,application/pdf,audio/*,video/*"
        />
        <div className={`p-4 rounded-full shadow-sm mb-4 transition-colors ${isDragging ? 'bg-blue-100' : 'bg-white'}`}>
          <UploadCloud className={`w-8 h-8 ${isDragging ? 'text-blue-700' : 'text-blue-600'}`} />
        </div>
        <p className="text-slate-700 font-medium mb-1 text-center">
          Click to upload or drag and drop
        </p>
        <p className="text-slate-500 text-sm text-center">
          PDF, JPG, PNG, MP3, MP4 (max. 50MB per file)
        </p>
      </div>

      {/* Selected Files List */}
      {files.length > 0 && (
        <div className="space-y-3 animate-in fade-in slide-in-from-bottom-2 duration-300">
          <div className="flex items-center justify-between">
            <h4 className="text-sm font-medium text-slate-700">
              Attached Files ({files.length})
            </h4>
            <span className="text-xs text-slate-500">
              Total size: {formatFileSize(files.reduce((acc, file) => acc + file.size, 0))}
            </span>
          </div>
          <ul className="space-y-2">
            {files.map((file, index) => (
              <li
                key={`${file.name}-${index}`}
                className="flex items-center justify-between p-3 bg-white border border-slate-200 rounded-lg shadow-sm hover:border-slate-300 transition-colors group"
              >
                <div className="flex items-center space-x-3 overflow-hidden">
                  <div className="bg-slate-50 p-2 rounded-md shrink-0 border border-slate-100">
                    <FileText className="w-5 h-5 text-blue-600" />
                  </div>
                  <div className="truncate">
                    <p className="text-sm font-medium text-slate-900 truncate" title={file.name}>
                      {file.name}
                    </p>
                    <p className="text-xs text-slate-500">
                      {formatFileSize(file.size)}
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation()
                    removeFile(index)
                  }}
                  className="p-2 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-md transition-colors focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-1"
                  aria-label={`Remove ${file.name}`}
                >
                  <X className="w-4 h-4" />
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Security Note */}
      <div className="bg-blue-50 border border-blue-100 rounded-lg p-4 flex items-start space-x-3">
        <div className="shrink-0 mt-0.5">
          <svg className="w-5 h-5 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
          </svg>
        </div>
        <div>
          <h5 className="text-sm font-medium text-blue-900">Secure & Immutable</h5>
          <p className="text-xs text-blue-700 mt-1 leading-relaxed">
            All uploaded evidence is encrypted and hashed on the C3MS blockchain ledger. 
            Once submitted, files cannot be altered or deleted by any party, ensuring complete evidentiary integrity.
          </p>
        </div>
      </div>
    </div>
  )
}