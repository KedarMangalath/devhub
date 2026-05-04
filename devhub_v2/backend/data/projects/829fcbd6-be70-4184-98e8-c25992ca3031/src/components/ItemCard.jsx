import React, { useState, useEffect } from 'react';
import { 
  MapPin, 
  Calendar, 
  ShieldAlert, 
  ArrowRight, 
  Bookmark, 
  Share2, 
  CheckCircle2, 
  Clock, 
  AlertTriangle,
  FileText,
  Check
} from 'lucide-react';

// ============================================================================
// INLINE UI PRIMITIVES
// Defined here to ensure the component is 100% self-contained and working
// without relying on external UI files not explicitly listed in the project plan.
// ============================================================================

const Card = ({ className = '', children, ...props }) => (
  <div 
    className={`rounded-xl border border-border bg-card text-foreground shadow-sm overflow-hidden ${className}`} 
    {...props}
  >
    {children}
  </div>
);

const Badge = ({ className = '', variant = "default", children, ...props }) => {
  const variants = {
    default: "border-transparent bg-primary text-white hover:bg-primary/90",
    secondary: "border-transparent bg-secondary text-secondary-foreground hover:bg-secondary/80",
    outline: "text-foreground border-border",
    destructive: "border-transparent bg-red-600 text-white hover:bg-red-700",
    success: "border-transparent bg-emerald-600 text-white hover:bg-emerald-700",
    warning: "border-transparent bg-amber-500 text-white hover:bg-amber-600",
  };
  
  return (
    <div 
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 ${variants[variant]} ${className}`} 
      {...props}
    >
      {children}
    </div>
  );
};

const Button = React.forwardRef(({ className = '', variant = "default", size = "default", children, ...props }, ref) => {
  const variants = {
    default: "bg-primary text-white hover:bg-primary/90 shadow-sm",
    outline: "border border-border bg-transparent hover:bg-secondary hover:text-accent-foreground",
    ghost: "hover:bg-secondary hover:text-accent-foreground",
    secondary: "bg-secondary text-secondary-foreground hover:bg-secondary/80",
  };
  const sizes = {
    default: "h-10 px-4 py-2",
    sm: "h-9 rounded-md px-3 text-xs",
    lg: "h-11 rounded-md px-8",
    icon: "h-10 w-10",
  };
  
  return (
    <button 
      ref={ref} 
      className={`inline-flex items-center justify-center rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 ${variants[variant]} ${sizes[size]} ${className}`} 
      {...props}
    >
      {children}
    </button>
  );
});
Button.displayName = "Button";

// ============================================================================
// MAIN COMPONENT: ItemCard
// ============================================================================

/**
 * ItemCard Component
 * Represents a domain item (e.g., a Complaint or Report) in a grid or list.
 * Features lazy-loaded imagery, clamped text, metadata, and interactive actions.
 */
export default function ItemCard({ item }) {
  // Fallback mock data if no item is provided, ensuring zero blank UI
  const data = item || {
    id: 'cmp-1042',
    title: 'Fraudulent Road Contract Allocation in District 4',
    description: 'Observed severe irregularities in the recent tender process for the NH-44 bypass. Documents suggest pre-approval of unqualified vendors linked to local officials. Immediate audit requested.',
    category: 'Public Works (PWD)',
    imageUrl: 'https://images.unsplash.com/photo-1584467735815-f778f274e296?w=800&q=80',
    date: '2023-10-24T10:30:00Z',
    status: 'Investigating',
    credibilityScore: 92,
    location: 'Thiruvananthapuram',
    evidenceCount: 3,
    isAnonymous: true
  };

  // Local state for interactions
  const [isBookmarked, setIsBookmarked] = useState(false);
  const [isShared, setIsShared] = useState(false);
  const [imageLoaded, setImageLoaded] = useState(false);

  // Handle share interaction with temporary visual feedback
  useEffect(() => {
    let timeout;
    if (isShared) {
      timeout = setTimeout(() => setIsShared(false), 2000);
    }
    return () => clearTimeout(timeout);
  }, [isShared]);

  const handleShare = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsShared(true);
    // In a real app, this would trigger navigator.share() or a modal
  };

  const toggleBookmark = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsBookmarked(!isBookmarked);
  };

  // Helper to format date
  const formatDate = (dateString) => {
    const options = { year: 'numeric', month: 'short', day: 'numeric' };
    return new Date(dateString).toLocaleDateString('en-IN', options);
  };

  // Helper to determine status badge styling and icon
  const getStatusConfig = (status) => {
    switch (status.toLowerCase()) {
      case 'resolved':
        return { variant: 'success', icon: CheckCircle2, label: 'Resolved' };
      case 'investigating':
        return { variant: 'warning', icon: Clock, label: 'Investigating' };
      case 'high risk':
        return { variant: 'destructive', icon: AlertTriangle, label: 'High Risk' };
      default:
        return { variant: 'secondary', icon: FileText, label: status || 'Pending' };
    }
  };

  const statusConfig = getStatusConfig(data.status);
  const StatusIcon = statusConfig.icon;

  return (
    <Card className="group relative flex flex-col h-full hover:-translate-y-1 hover:shadow-xl transition-all duration-300 bg-surface">
      
      {/* 1. Image Section (Aspect Ratio, Lazy Load, Overlays) */}
      <div className="relative aspect-[4/3] overflow-hidden bg-secondary/50">
        {/* Skeleton loader background */}
        {!imageLoaded && (
          <div className="absolute inset-0 animate-pulse bg-secondary" />
        )}
        
        <img 
          src={data.imageUrl || `https://picsum.photos/seed/${data.id}/600/400`} 
          alt={data.title} 
          loading="lazy" 
          onLoad={() => setImageLoaded(true)}
          className={`object-cover w-full h-full transition-transform duration-700 group-hover:scale-105 ${imageLoaded ? 'opacity-100' : 'opacity-0'}`} 
        />
        
        {/* Gradient Overlay for text readability */}
        <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/20 to-transparent opacity-90" />

        {/* Top Left: Category Badge */}
        <div className="absolute top-3 left-3 z-10">
          <Badge variant="secondary" className="bg-white/95 text-slate-900 hover:bg-white backdrop-blur-sm shadow-sm font-body">
            {data.category}
          </Badge>
        </div>

        {/* Top Right: Bookmark Action */}
        <div className="absolute top-3 right-3 z-10">
           <button 
             onClick={toggleBookmark} 
             className="p-2 rounded-full bg-black/20 hover:bg-black/40 backdrop-blur-md transition-colors focus:outline-none focus:ring-2 focus:ring-primary"
             aria-label={isBookmarked ? "Remove bookmark" : "Bookmark item"}
           >
             <Bookmark className={`w-4 h-4 transition-colors ${isBookmarked ? "fill-primary text-primary" : "text-white"}`} />
           </button>
        </div>

        {/* Bottom Overlay: Location & Evidence Count */}
        <div className="absolute bottom-3 left-3 right-3 flex justify-between items-end z-10">
           <div className="flex flex-col space-y-1">
             <div className="flex items-center space-x-1.5 text-white/90 text-sm font-medium font-body">
               <MapPin className="w-3.5 h-3.5 text-primary" />
               <span className="truncate max-w-[150px]">{data.location}</span>
             </div>
             {data.isAnonymous && (
               <span className="text-xs text-white/70 font-body flex items-center">
                 <ShieldAlert className="w-3 h-3 mr-1 opacity-70" />
                 Anonymous Report
               </span>
             )}
           </div>
           
           <div className="flex items-center space-x-1 bg-black/40 backdrop-blur-md rounded-md px-2 py-1 text-xs text-white font-medium">
             <FileText className="w-3 h-3" />
             <span>{data.evidenceCount} Files</span>
           </div>
        </div>
      </div>

      {/* 2. Content Section */}
      <div className="flex flex-col flex-grow p-5">
        
        {/* Title (2-line clamp) */}
        <div className="mb-2">
          <h3 className="font-display text-lg font-semibold text-foreground line-clamp-2 leading-snug group-hover:text-primary transition-colors">
            {data.title}
          </h3>
        </div>

        {/* Short Description (3-line clamp) */}
        <p className="font-body text-sm text-muted-foreground line-clamp-3 mb-4 flex-grow leading-relaxed">
          {data.description}
        </p>

        {/* 3. Metadata Row */}
        <div className="flex items-center justify-between py-3 border-t border-border mt-auto">
          
          {/* AI Credibility Score */}
          <div className="flex items-center space-x-2" title="AI Credibility Analysis Score">
             <div className="flex items-center justify-center w-8 h-8 rounded-full bg-primary/10 text-primary">
               <ShieldAlert className="w-4 h-4" />
             </div>
             <div className="flex flex-col">
               <span className="text-xs text-muted-foreground font-medium uppercase tracking-wider">AI Score</span>
               <span className="text-sm font-bold text-foreground">{data.credibilityScore}%</span>
             </div>
          </div>

          {/* Status Badge */}
          <div className="flex flex-col items-end">
             <span className="text-xs text-muted-foreground font-medium uppercase tracking-wider mb-1 flex items-center">
               <Calendar className="w-3 h-3 mr-1" />
               {formatDate(data.date)}
             </span>
             <Badge variant={statusConfig.variant} className="flex items-center space-x-1 shadow-sm">
               <StatusIcon className="w-3 h-3" />
               <span>{statusConfig.label}</span>
             </Badge>
          </div>
        </div>

        {/* 4. Action Buttons */}
        <div className="flex items-center gap-3 mt-4 pt-4 border-t border-border">
          <Button 
            className="flex-1 font-body font-semibold tracking-wide" 
            onClick={() => console.log('Navigate to details:', data.id)}
          >
            View Details
            <ArrowRight className="w-4 h-4 ml-2 transition-transform group-hover:translate-x-1" />
          </Button>
          
          <Button 
            variant="outline" 
            size="icon" 
            onClick={handleShare} 
            title="Share Report"
            className={`transition-all ${isShared ? 'bg-emerald-50 border-emerald-200 text-emerald-600' : ''}`}
          >
            {isShared ? <Check className="w-4 h-4" /> : <Share2 className="w-4 h-4" />}
          </Button>
        </div>
        
      </div>
    </Card>
  );
}
