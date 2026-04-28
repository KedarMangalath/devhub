import { cn } from '../../utils/cn'

export default function Card({ 
  children, 
  className, 
  hoverable = false, 
  onClick,
  ...props 
}) {
  return (
    <div
      onClick={onClick}
      className={cn(
        "bg-white border border-slate-200 rounded-2xl p-6 shadow-sm",
        hoverable && "hover:shadow-md transition-shadow duration-200 cursor-pointer",
        className
      )}
      {...props}
    >
      {children}
    </div>
  )
}