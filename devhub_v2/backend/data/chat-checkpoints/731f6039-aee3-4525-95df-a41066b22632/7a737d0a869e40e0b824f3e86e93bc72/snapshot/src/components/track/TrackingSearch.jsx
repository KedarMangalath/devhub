import { Search } from 'lucide-react'
import { useState } from 'react'

export default function TrackingSearch({ onSearch }) {
  const [trackingId, setTrackingId] = useState('')

  const handleSubmit = (e) => {
    e.preventDefault()
    if (trackingId.trim()) {
      onSearch(trackingId.trim())
    }
  }

  return (
    <div className="w-full max-w-3xl mx-auto">
      <form onSubmit={handleSubmit} className="relative flex flex-col sm:flex-row items-center shadow-sm rounded-lg">
        <div className="relative flex-grow w-full">
          <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
            <Search className="h-6 w-6 text-slate-400" />
          </div>
          <input
            type="text"
            value={trackingId}
            onChange={(e) => setTrackingId(e.target.value)}
            placeholder="Enter Tracking ID (e.g., TRK-9A8B7C)"
            className="block w-full pl-12 pr-4 py-4 text-lg border border-slate-200 sm:rounded-l-lg sm:rounded-r-none rounded-t-lg sm:rounded-b-none focus:ring-2 focus:ring-vacb-700 focus:border-vacb-700 text-slate-900 placeholder-slate-400 bg-white transition-all outline-none"
            required
          />
        </div>
        <button
          type="submit"
          className="w-full sm:w-auto flex-shrink-0 px-8 py-4 text-lg font-medium text-white bg-vacb-700 border border-vacb-700 sm:rounded-r-lg sm:rounded-l-none rounded-b-lg sm:rounded-t-none hover:bg-vacb-800 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-vacb-700 transition-colors"
        >
          Track Status
        </button>
      </form>
      <p className="mt-4 text-sm text-slate-500 text-center font-medium">
        Your tracking ID is a unique code provided upon complaint submission.
      </p>
    </div>
  )
}