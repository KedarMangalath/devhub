import { Filter } from 'lucide-react'

export default function FilterSidebar({ specialties = [], selectedSpecialty, onSelectSpecialty }) {
  return (
    <div className="w-full md:w-64 bg-white border border-gray-200 rounded-xl shadow-sm p-5 h-fit sticky top-24">
      <div className="flex items-center gap-2 mb-4 pb-4 border-b border-gray-100">
        <Filter className="w-5 h-5 text-blue-600" />
        <h2 className="text-lg font-semibold text-gray-800">Specialties</h2>
      </div>
      
      <div className="space-y-1.5 max-h-[60vh] overflow-y-auto pr-2 custom-scrollbar">
        <button
          onClick={() => onSelectSpecialty('')}
          className={`w-full text-left px-3 py-2.5 rounded-lg transition-colors text-sm ${
            !selectedSpecialty
              ? 'bg-blue-50 text-blue-700 font-medium'
              : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
          }`}
        >
          All Specialties
        </button>
        
        {specialties.map((specialty) => (
          <button
            key={specialty.id || specialty.name}
            onClick={() => onSelectSpecialty(specialty.name)}
            className={`w-full text-left px-3 py-2.5 rounded-lg transition-colors text-sm ${
              selectedSpecialty === specialty.name
                ? 'bg-blue-50 text-blue-700 font-medium'
                : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
            }`}
          >
            {specialty.name}
          </button>
        ))}

        {specialties.length === 0 && (
          <div className="text-sm text-gray-400 px-3 py-2 italic">
            No specialties loaded.
          </div>
        )}
      </div>
    </div>
  )
}