import React, { useState, useEffect } from 'react';
import { 
  Search, 
  ChevronDown, 
  SlidersHorizontal, 
  X, 
  Filter,
  Calendar,
  MapPin,
  Activity
} from 'lucide-react';
import { categories } from '../mockData.js';

// --- Inline UI Primitives ---
// Built inline to guarantee highly styled elements without relying on external 
// UI component files that may not exist in the strict file plan.

const StyledInput = ({ icon: Icon, onClear, ...props }) => (
  <div className="relative w-full">
    {Icon && (
      <Icon className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400 w-5 h-5 pointer-events-none" />
    )}
    <input
      className={`w-full bg-slate-50 border border-slate-200 text-slate-900 rounded-xl focus:outline-none focus:ring-2 focus:ring-emerald-500/50 focus:border-emerald-500 transition-all font-body placeholder:text-slate-400 shadow-sm ${
        Icon ? 'pl-11' : 'pl-4'
      } ${onClear && props.value ? 'pr-10' : 'pr-4'} py-2.5`}
      {...props}
    />
    {onClear && props.value && (
      <button
        onClick={onClear}
        className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 transition-colors p-1 rounded-full hover:bg-slate-200"
        aria-label="Clear search"
      >
        <X className="w-4 h-4" />
      </button>
    )}
  </div>
);

const StyledSelect = ({ icon: Icon, options, value, onChange, placeholder }) => (
  <div className="relative w-full">
    {Icon && (
      <Icon className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400 w-4 h-4 pointer-events-none z-10" />
    )}
    <select
      value={value}
      onChange={onChange}
      className={`w-full appearance-none bg-white border border-slate-200 text-slate-700 py-2.5 rounded-xl focus:outline-none focus:ring-2 focus:ring-emerald-500/50 focus:border-emerald-500 font-body cursor-pointer shadow-sm transition-all hover:bg-slate-50 ${
        Icon ? 'pl-10' : 'pl-4'
      } pr-10`}
    >
      {placeholder && (
        <option value="" disabled hidden>
          {placeholder}
        </option>
      )}
      {options.map((opt) => (
        <option key={opt.value} value={opt.value}>
          {opt.label}
        </option>
      ))}
    </select>
    <ChevronDown className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-400 w-4 h-4 pointer-events-none" />
  </div>
);

const PillButton = ({ active, onClick, children, count }) => (
  <button
    onClick={onClick}
    className={`group flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium transition-all duration-200 font-body border ${
      active
        ? 'bg-emerald-600 border-emerald-600 text-white shadow-md shadow-emerald-600/20'
        : 'bg-white border-slate-200 text-slate-600 hover:bg-slate-50 hover:border-slate-300 hover:text-slate-900'
    }`}
  >
    {children}
    {count !== undefined && (
      <span
        className={`text-xs px-2 py-0.5 rounded-full transition-colors ${
          active
            ? 'bg-emerald-500/50 text-white'
            : 'bg-slate-100 text-slate-500 group-hover:bg-slate-200'
        }`}
      >
        {count}
      </span>
    )}
  </button>
);

// --- Main Component ---

/**
 * SearchFilterBar
 * A comprehensive search and filtering header component for list views.
 * Includes text search, quick category pills, sorting, and an expandable advanced filter section.
 */
export default function SearchFilterBar({
  searchTerm = '',
  onSearchChange = () => {},
  activeFilter = 'all',
  onFilterChange = () => {},
  sortBy = 'newest',
  onSortChange = () => {},
  resultCount = 0,
  filters = [],
}) {
  // Local state for advanced filters panel
  const [isAdvancedOpen, setIsAdvancedOpen] = useState(false);
  
  // Local state for advanced filter selections (demonstrating local state requirement)
  const [advancedFilters, setAdvancedFilters] = useState({
    status: '',
    district: '',
    dateRange: ''
  });

  // Fallback to mock data if no filters provided, ensuring zero empty states
  const displayFilters = filters.length > 0 ? filters : categories.slice(0, 5).map(c => ({
    id: c.id,
    label: c.name.replace(/ \([^)]*\)/, ''), // Clean up names for pills
    count: c.count
  }));

  const sortOptions = [
    { value: 'newest', label: 'Newest First' },
    { value: 'oldest', label: 'Oldest First' },
    { value: 'severity-high', label: 'Highest Severity' },
    { value: 'status', label: 'Status (Open First)' },
    { value: 'verified', label: 'Blockchain Verified' }
  ];

  const handleAdvancedFilterChange = (key, value) => {
    setAdvancedFilters(prev => ({ ...prev, [key]: value }));
  };

  const clearAdvancedFilters = () => {
    setAdvancedFilters({ status: '', district: '', dateRange: '' });
  };

  const activeAdvancedCount = Object.values(advancedFilters).filter(Boolean).length;

  return (
    <div className="w-full bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden flex flex-col">
      {/* Top Section: Search & Sort */}
      <div className="p-4 sm:p-5 border-b border-slate-100 flex flex-col lg:flex-row gap-4 items-start lg:items-center justify-between bg-slate-50/50">
        
        {/* Search Input Area */}
        <div className="w-full lg:max-w-xl flex-1 flex items-center gap-3">
          <StyledInput
            icon={Search}
            type="text"
            placeholder="Search complaints, departments, or keywords..."
            value={searchTerm}
            onChange={(e) => onSearchChange(e.target.value)}
            onClear={() => onSearchChange('')}
          />
          
          {/* Mobile Advanced Toggle (Icon only) */}
          <button
            onClick={() => setIsAdvancedOpen(!isAdvancedOpen)}
            className={`lg:hidden p-2.5 rounded-xl border transition-colors flex-shrink-0 ${
              isAdvancedOpen || activeAdvancedCount > 0
                ? 'bg-emerald-50 border-emerald-200 text-emerald-700'
                : 'bg-white border-slate-200 text-slate-600 hover:bg-slate-50'
            }`}
            aria-label="Toggle advanced filters"
          >
            <SlidersHorizontal className="w-5 h-5" />
            {activeAdvancedCount > 0 && (
              <span className="absolute top-1.5 right-1.5 w-2.5 h-2.5 bg-emerald-500 rounded-full border-2 border-white"></span>
            )}
          </button>
        </div>

        {/* Desktop Controls: Sort & Advanced Toggle */}
        <div className="w-full lg:w-auto flex items-center gap-3 justify-between lg:justify-end">
          <div className="flex items-center gap-3 w-full sm:w-auto">
            <span className="text-sm font-medium text-slate-500 hidden sm:inline-block font-body whitespace-nowrap">
              Sort by:
            </span>
            <div className="w-full sm:w-56">
              <StyledSelect
                options={sortOptions}
                value={sortBy}
                onChange={(e) => onSortChange(e.target.value)}
              />
            </div>
          </div>

          {/* Desktop Advanced Toggle */}
          <button
            onClick={() => setIsAdvancedOpen(!isAdvancedOpen)}
            className={`hidden lg:flex items-center gap-2 px-4 py-2.5 rounded-xl border text-sm font-medium transition-all font-body whitespace-nowrap ${
              isAdvancedOpen || activeAdvancedCount > 0
                ? 'bg-emerald-50 border-emerald-200 text-emerald-700'
                : 'bg-white border-slate-200 text-slate-600 hover:bg-slate-50 hover:text-slate-900'
            }`}
          >
            <SlidersHorizontal className="w-4 h-4" />
            Filters
            {activeAdvancedCount > 0 && (
              <span className="bg-emerald-100 text-emerald-700 px-2 py-0.5 rounded-full text-xs font-bold ml-1">
                {activeAdvancedCount}
              </span>
            )}
          </button>
        </div>
      </div>

      {/* Expandable Advanced Filters Panel */}
      {isAdvancedOpen && (
        <div className="p-4 sm:p-5 border-b border-slate-100 bg-slate-50 animate-in slide-in-from-top-2 fade-in duration-200">
          <div className="flex flex-col sm:flex-row items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-slate-900 font-display flex items-center gap-2">
              <Filter className="w-4 h-4 text-emerald-600" />
              Advanced Filters
            </h3>
            {activeAdvancedCount > 0 && (
              <button 
                onClick={clearAdvancedFilters}
                className="text-xs font-medium text-slate-500 hover:text-slate-900 transition-colors flex items-center gap-1"
              >
                <X className="w-3 h-3" /> Clear all
              </button>
            )}
          </div>
          
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <StyledSelect
              icon={Activity}
              placeholder="Any Status"
              value={advancedFilters.status}
              onChange={(e) => handleAdvancedFilterChange('status', e.target.value)}
              options={[
                { value: 'open', label: 'Open / Pending' },
                { value: 'investigating', label: 'Under Investigation' },
                { value: 'resolved', label: 'Resolved' },
                { value: 'closed', label: 'Closed' }
              ]}
            />
            <StyledSelect
              icon={MapPin}
              placeholder="Any District"
              value={advancedFilters.district}
              onChange={(e) => handleAdvancedFilterChange('district', e.target.value)}
              options={[
                { value: 'tvm', label: 'Thiruvananthapuram' },
                { value: 'ekm', label: 'Ernakulam' },
                { value: 'kkd', label: 'Kozhikode' },
                { value: 'tsr', label: 'Thrissur' }
              ]}
            />
            <StyledSelect
              icon={Calendar}
              placeholder="Any Time"
              value={advancedFilters.dateRange}
              onChange={(e) => handleAdvancedFilterChange('dateRange', e.target.value)}
              options={[
                { value: '7d', label: 'Last 7 Days' },
                { value: '30d', label: 'Last 30 Days' },
                { value: '90d', label: 'Last 3 Months' },
                { value: '1y', label: 'Past Year' }
              ]}
            />
          </div>
        </div>
      )}

      {/* Bottom Section: Quick Category Pills & Results Count */}
      <div className="p-4 sm:p-5 flex flex-col lg:flex-row gap-4 justify-between items-start lg:items-center bg-white">
        
        {/* Scrollable Pill Container */}
        <div className="w-full lg:w-auto overflow-x-auto pb-2 lg:pb-0 -mx-4 px-4 lg:mx-0 lg:px-0 hide-scrollbar">
          <div className="flex items-center gap-2 min-w-max">
            <PillButton
              active={activeFilter === 'all'}
              onClick={() => onFilterChange('all')}
            >
              All Categories
            </PillButton>
            
            {displayFilters.map(filter => (
              <PillButton
                key={filter.id}
                active={activeFilter === filter.id}
                onClick={() => onFilterChange(filter.id)}
                count={filter.count}
              >
                {filter.label}
              </PillButton>
            ))}
          </div>
        </div>

        {/* Results Counter */}
        <div className="flex-shrink-0 text-sm text-slate-500 font-body bg-slate-50 px-4 py-2 rounded-lg border border-slate-100 w-full lg:w-auto text-center lg:text-left">
          Showing <span className="font-semibold text-slate-900">{resultCount.toLocaleString()}</span> results
          {(searchTerm || activeFilter !== 'all' || activeAdvancedCount > 0) && (
            <span className="text-slate-400 ml-1">for current filters</span>
          )}
        </div>
      </div>

      {/* Custom CSS to hide scrollbar for the pills container but keep it scrollable */}
      <style dangerouslySetInnerHTML={{__html: `
        .hide-scrollbar::-webkit-scrollbar {
          display: none;
        }
        .hide-scrollbar {
          -ms-overflow-style: none;
          scrollbar-width: none;
        }
      `}} />
    </div>
  );
}
