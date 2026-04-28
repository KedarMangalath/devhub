import React from 'react'
import { Star, Calendar, DollarSign } from 'lucide-react'
import { Card } from './ui/Card'
import { Button } from './ui/Button'
import { Badge } from './ui/Badge'
import { cn } from '../utils/cn'

export default function ItemCard({
  image,
  title,
  subtitle,
  badge,
  metadata = [],
  rating,
  price,
  date,
  action,
  secondaryAction,
  className,
  imageClassName
}) {
  return (
    <Card className={cn("overflow-hidden flex flex-col transition-all duration-300 hover:shadow-md group bg-white border-slate-200 rounded-2xl", className)}>
      {image && (
        <div className={cn("relative w-full h-48 overflow-hidden bg-slate-100 shrink-0", imageClassName)}>
          <img 
            src={image} 
            alt={title} 
            className="w-full h-full object-cover transition-transform duration-700 group-hover:scale-105"
            loading="lazy"
          />
          {badge && (
            <div className="absolute top-3 right-3 z-10">
              <Badge variant={badge.variant || "secondary"} className="shadow-sm backdrop-blur-md bg-white/90 text-slate-800 border-none font-medium">
                {badge.text}
              </Badge>
            </div>
          )}
          <div className="absolute inset-0 bg-gradient-to-t from-black/20 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
        </div>
      )}
      
      <div className="p-5 flex-1 flex flex-col">
        {!image && badge && (
          <div className="mb-3">
            <Badge variant={badge.variant || "secondary"} className="font-medium">
              {badge.text}
            </Badge>
          </div>
        )}

        <div className="mb-1.5 flex justify-between items-start gap-3">
          <h3 className="font-display font-semibold text-lg text-slate-900 line-clamp-1" title={title}>
            {title}
          </h3>
          {rating && (
            <div className="flex items-center gap-1 bg-amber-50 text-amber-700 px-1.5 py-0.5 rounded-md text-sm font-semibold shrink-0 border border-amber-100/50">
              <Star className="w-3.5 h-3.5 fill-amber-500 text-amber-500" />
              <span>{rating}</span>
            </div>
          )}
        </div>

        {subtitle && (
          <p className="text-sm text-slate-500 mb-4 line-clamp-1 font-medium">{subtitle}</p>
        )}

        {metadata.length > 0 && (
          <div className="space-y-2.5 mb-5 mt-1">
            {metadata.map((item, idx) => (
              <div key={idx} className="flex items-center text-sm text-slate-600">
                {item.icon && (
                  <span className="mr-2.5 flex items-center justify-center text-slate-400 w-4 h-4 shrink-0">
                    {item.icon}
                  </span>
                )}
                <span className="truncate">{item.text}</span>
              </div>
            ))}
          </div>
        )}

        <div className="mt-auto pt-4 flex items-center justify-between border-t border-slate-100">
          <div className="flex flex-col gap-1.5">
            {date && (
              <div className="flex items-center text-sm font-medium text-slate-700">
                <Calendar className="w-4 h-4 mr-1.5 text-primary" />
                {date}
              </div>
            )}
            {price && (
              <div className="flex items-center text-sm font-semibold text-slate-900">
                <DollarSign className="w-4 h-4 mr-1 text-emerald-500" />
                {price}
              </div>
            )}
          </div>

          <div className="flex items-center gap-2 shrink-0 ml-4">
            {secondaryAction && (
              <Button 
                variant={secondaryAction.variant || "outline"} 
                size="sm" 
                onClick={secondaryAction.onClick}
                className="text-xs px-3 h-8 rounded-lg"
              >
                {secondaryAction.label}
              </Button>
            )}
            {action && (
              <Button 
                variant={action.variant || "primary"} 
                size="sm" 
                onClick={action.onClick}
                className="text-xs px-3 h-8 rounded-lg shadow-sm"
              >
                {action.label}
              </Button>
            )}
          </div>
        </div>
      </div>
    </Card>
  )
}