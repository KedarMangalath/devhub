import { useState, useEffect } from 'react'
import { departments } from '../../mockData'
import { Search, Filter, X, ChevronDown } from 'lucide-react'

const KERALA_DISTRICTS = [
  "Alappuzha",
  "Ernakulam",
  "Idukki",
  "Kannur",
  "Kasaragod",
  "Kollam",
  "Kottayam",
  "Kozhikode",
  "Malappuram",
  "Palakkad",
  "Pathanamthitta",
  "Thiruvananthapuram",
  "Thrissur",
  "Wayanad"
];

export default function SearchFilterBar({ onFilterChange }) {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedDepartment, setSelectedDepartment] = useState('');
  const [selectedDistrict, setSelectedDistrict] = useState('');

  // Debounce search term slightly for better performance in a real app, 
  // but immediate update is fine for local state MVP.
  useEffect(() => {
    if (onFilterChange) {
      onFilterChange({
        search: searchTerm,
        department: selectedDepartment,
        district: selectedDistrict
      });
    }
  }, [searchTerm, selectedDepartment, selectedDistrict, onFilterChange]);

  const handleClearFilters = () => {
    setSearchTerm('');
    setSelectedDepartment('');
    setSelectedDistrict('');
  };

  const hasActiveFilters = searchTerm !== '' || selectedDepartment !== '' || selectedDistrict !== '';

  return (
    <div className="bg-card border border-border rounded-xl p-4 shadow-sm w-full transition-all duration-200 hover:shadow-md">
      <div className="flex flex-col lg:flex-row gap-4 items-start lg:items-center">
        
        {/* Search Input Area */}
        <div className="relative flex-grow w-full lg:w-auto group">
          <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none">
            <Search className="h-5 w-5 text-muted-foreground group-focus-within:text-primary transition-colors" />
          </div>
          <input
            type="text"
            placeholder="Search complaints by ID, keyword, or subject..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="block w-full pl-11 pr-4 py-3 border border-border rounded-lg leading-5 bg-background text-foreground placeholder-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary sm:text-sm transition-all font-body"
            aria-label="Search complaints"
          />
          {searchTerm && (
            <button
              onClick={() => setSearchTerm('')}
              className="absolute inset-y-0 right-0 pr-3 flex items-center text-muted-foreground hover:text-foreground"
              aria-label="Clear search"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>

        {/* Filters Container */}
        <div className="flex flex-col sm:flex-row gap-3 w-full lg:w-auto shrink-0">
          
          {/* Department Filter */}
          <div className="relative w-full sm:w-56 group">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <Filter className="h-4 w-4 text-muted-foreground group-focus-within:text-primary transition-colors" />
            </div>
            <select
              value={selectedDepartment}
              onChange={(e) => setSelectedDepartment(e.target.value)}
              className="block w-full pl-9 pr-10 py-3 text-sm border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary bg-background text-foreground appearance-none cursor-pointer font-body transition-all"
              aria-label="Filter by Department"
            >
              <option value="">All Departments</option>
              {departments?.map((dept) => {
                // Handle both object and string array structures safely
                const value = typeof dept === 'object' ? (dept.id || dept.name) : dept;
                const label = typeof dept === 'object' ? dept.name : dept;
                return (
                  <option key={value} value={value}>
                    {label}
                  </option>
                );
              })}
            </select>
            <div className="absolute inset-y-0 right-0 pr-3 flex items-center pointer-events-none">
              <ChevronDown className="h-4 w-4 text-muted-foreground" />
            </div>
          </div>

          {/* District Filter */}
          <div className="relative w-full sm:w-48 group">
            <select
              value={selectedDistrict}
              onChange={(e) => setSelectedDistrict(e.target.value)}
              className="block w-full pl-4 pr-10 py-3 text-sm border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary bg-background text-foreground appearance-none cursor-pointer font-body transition-all"
              aria-label="Filter by District"
            >
              <option value="">All Districts</option>
              {KERALA_DISTRICTS.map((district) => (
                <option key={district} value={district}>
                  {district}
                </option>
              ))}
            </select>
            <div className="absolute inset-y-0 right-0 pr-3 flex items-center pointer-events-none">
              <ChevronDown className="h-4 w-4 text-muted-foreground" />
            </div>
          </div>

          {/* Clear Filters Action */}
          {hasActiveFilters && (
            <button
              onClick={handleClearFilters}
              className="flex items-center justify-center px-4 py-3 border border-transparent text-sm font-medium rounded-lg text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary focus:ring-offset-background whitespace-nowrap"
              aria-label="Clear all filters"
            >
              <X className="h-4 w-4 mr-2" />
              Clear
            </button>
          )}
        </div>
      </div>
      
      {/* Active Filter Badges (Optional visual feedback) */}
      {hasActiveFilters && (
        <div className="mt-4 pt-4 border-t border-border flex flex-wrap gap-2 items-center">
          <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider mr-2">
            Active Filters:
          </span>
          {searchTerm && (
            <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-primary/10 text-primary border border-primary/20">
              Search: {searchTerm}
            </span>
          )}
          {selectedDepartment && (
            <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-secondary text-secondary-foreground border border-border">
              Dept: {typeof departments[0] === 'object' ? departments.find(d => d.id === selectedDepartment || d.name === selectedDepartment)?.name || selectedDepartment : selectedDepartment}
            </span>
          )}
          {selectedDistrict && (
            <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-secondary text-secondary-foreground border border-border">
              District: {selectedDistrict}
            </span>
          )}
        </div>
      )}
    </div>
  );
}