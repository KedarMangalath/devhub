import React from 'react'
import { Calendar, ChevronRight, Tag, Hash, ArrowRight } from 'lucide-react'
import StatusPill from './shared/StatusPill'
import { cn } from '../utils/cn'

export default function ItemCard({
  title,
  subtitle,
  description,
  imageUrl,
  status,
  severity,
  metadata = [],
  date,
  id,
  actionLabel = "View Details",
  onAction,
  className
}) {
  // Format date if provided
  const formattedDate = date ? new Date(date).toLocaleDateString('en-IN', {
    year: 'numeric',
    month: 'short',
    day: 'numeric'
  }) : null;

  return (
    <div 
      className={cn(
        "group flex flex-col bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden hover:shadow-md transition-all duration-200",
        className
      )}
    >
      {/* Optional Image Header */}
      {imageUrl && (
        <div className="relative h-48 w-full overflow-hidden bg-slate-100">
          <img 
            src={imageUrl} 
            alt={title} 
            className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105"
            loading="lazy"
          />
          {/* Overlay Badges on Image */}
          <div className="absolute top-3 left-3 flex flex-wrap gap-2">
            {status && <StatusPill status={status} />}
            {severity && (
              <span className={cn(
                "px-2.5 py-1 rounded-full text-xs font-semibold border backdrop-blur-md",
                severity.toLowerCase() === 'critical' ? "bg-red-500/90 text-white border-red-600" :
                severity.toLowerCase() === 'high' ? "bg-amber-500/90 text-white border-amber-600" :
                "bg-slate-800/80 text-white border-slate-700"
              )}>
                {severity}
              </span>
            )}
          </div>
        </div>
      )}

      <div className="flex flex-col flex-grow p-5">
        {/* Header Section (if no image, show badges here) */}
        {!imageUrl && (status || severity) && (
          <div className="flex flex-wrap gap-2 mb-3">
            {status && <StatusPill status={status} />}
            {severity && (
              <span className={cn(
                "px-2.5 py-0.5 rounded-full text-xs font-semibold border",
                severity.toLowerCase() === 'critical' ? "bg-red-50 text-red-700 border-red-200" :
                severity.toLowerCase() === 'high' ? "bg-amber-50 text-amber-700 border-amber-200" :
                "bg-slate-100 text-slate-700 border-slate-200"
              )}>
                {severity}
              </span>
            )}
          </div>
        )}

        {/* Title & Subtitle */}
        <div className="mb-3">
          {subtitle && (
            <div className="flex items-center gap-1.5 text-xs font-medium text-blue-700 mb-1.5 uppercase tracking-wider">
              <Tag className="w-3.5 h-3.5" />
              {subtitle}
            </div>
          )}
          <h3 className="text-lg font-bold text-slate-900 line-clamp-2 leading-tight group-hover:text-blue-800 transition-colors">
            {title}
          </h3>
        </div>

        {/* Description */}
        {description && (
          <p className="text-sm text-slate-600 line-clamp-3 mb-4 flex-grow">
            {description}
          </p>
        )}

        {/* Metadata Grid */}
        {metadata && metadata.length > 0 && (
          <div className="grid grid-cols-2 gap-y-2 gap-x-4 mb-5 py-3 border-y border-slate-100">
            {metadata.map((item, idx) => (
              <div key={idx} className="flex items-start gap-2 text-sm">
                {item.icon && (
                  <item.icon className="w-4 h-4 text-slate-400 mt-0.5 shrink-0" />
                )}
                <div className="flex flex-col">
                  <span className="text-xs text-slate-500">{item.label}</span>
                  <span className="font-medium text-slate-800 truncate">{item.value}</span>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Footer */}
        <div className="mt-auto pt-4 flex items-center justify-between border-t border-slate-100">
          <div className="flex flex-col gap-1">
            {id && (
              <div className="flex items-center gap-1.5 text-xs font-mono text-slate-500">
                <Hash className="w-3.5 h-3.5" />
                {id}
              </div>
            )}
            {formattedDate && (
              <div className="flex items-center gap-1.5 text-xs text-slate-500">
                <Calendar className="w-3.5 h-3.5" />
                {formattedDate}
              </div>
            )}
          </div>

          {onAction && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onAction();
              }}
              className="inline-flex items-center justify-center gap-1.5 px-4 py-2 text-sm font-medium text-blue-700 bg-blue-50 hover:bg-blue-100 rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1"
            >
              {actionLabel}
              <ArrowRight className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}