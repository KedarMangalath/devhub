import { departments } from '../../mockData'
import { Search, Building2 } from 'lucide-react'
import { useState } from 'react'
import { cn } from '../../utils/cn'

export default function DepartmentSelector({ selectedId, onSelect }) {
  const [searchQuery, setSearchQuery] = useState('')

  const filteredDepartments = departments.filter((dept) =>
    dept.name.toLowerCase().includes(searchQuery.toLowerCase())
  )

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-slate-900">Select Department</h2>
        <p className="text-sm text-slate-500 mt-1">
          Choose the government department related to your grievance. If you are unsure, search by keywords.
        </p>
      </div>

      <div className="relative">
        <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
          <Search className="h-5 w-5 text-slate-400" />
        </div>
        <input
          type="text"
          className="block w-full pl-10 pr-3 py-3.5 border border-slate-200 rounded-xl leading-5 bg-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-vacb-600 focus:border-vacb-600 sm:text-sm transition-colors shadow-sm"
          placeholder="Search departments (e.g., Revenue, Police, Health)..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
        />
      </div>

      {filteredDepartments.length > 0 ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredDepartments.map((dept) => {
            const isSelected = selectedId === dept.id
            return (
              <button
                key={dept.id}
                onClick={() => onSelect(dept.id)}
                className={cn(
                  "flex flex-col items-start p-5 rounded-xl border text-left transition-all duration-200 w-full focus:outline-none focus:ring-2 focus:ring-vacb-600 focus:ring-offset-2",
                  isSelected
                    ? "border-vacb-600 bg-vacb-50/50 shadow-sm ring-1 ring-vacb-600"
                    : "border-slate-200 bg-white hover:border-vacb-300 hover:shadow-md hover:-translate-y-0.5"
                )}
              >
                <div className={cn(
                  "p-2.5 rounded-lg mb-4 transition-colors",
                  isSelected ? "bg-vacb-100 text-vacb-700" : "bg-slate-100 text-slate-600"
                )}>
                  <Building2 className="h-6 w-6" />
                </div>
                <h3 className={cn(
                  "font-medium text-base leading-tight",
                  isSelected ? "text-vacb-900" : "text-slate-900"
                )}>
                  {dept.name}
                </h3>
                <div className="mt-auto pt-3 w-full flex items-center justify-between">
                  <span className="text-xs text-slate-400 font-mono">
                    {dept.id}
                  </span>
                  {isSelected && (
                    <span className="text-xs font-medium text-vacb-700 bg-vacb-100 px-2 py-0.5 rounded-full">
                      Selected
                    </span>
                  )}
                </div>
              </button>
            )
          })}
        </div>
      ) : (
        <div className="text-center py-16 bg-slate-50 rounded-xl border border-slate-200 border-dashed">
          <Building2 className="mx-auto h-12 w-12 text-slate-300" />
          <h3 className="mt-4 text-sm font-medium text-slate-900">No departments found</h3>
          <p className="mt-1 text-sm text-slate-500">
            We couldn't find anything matching "{searchQuery}".
          </p>
          <button
            onClick={() => setSearchQuery('')}
            className="mt-6 text-sm font-medium text-vacb-600 hover:text-vacb-700 bg-vacb-50 px-4 py-2 rounded-lg transition-colors"
          >
            Clear search
          </button>
        </div>
      )}
    </div>
  )
}