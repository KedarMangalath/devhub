import React, { useMemo, useState, useEffect } from 'react';
import { 
  Shield, 
  CheckCircle, 
  AlertTriangle, 
  FileText, 
  Upload, 
  MapPin, 
  Calendar, 
  Lock, 
  EyeOff, 
  ChevronRight, 
  ChevronLeft, 
  Info, 
  Activity, 
  Building, 
  HardHat, 
  Car, 
  TreePine, 
  Wine, 
  BookOpen, 
  ShoppingCart, 
  Check, 
  X,
  Search,
  ShieldCheck,
  Cpu,
  Database,
  ArrowRight,
  ChevronDown,
  ChevronUp
} from 'lucide-react';
import AppShell from '../components/AppShell';
import { categories, userProfile } from '../mockData';

// ============================================================================
// INLINE UI PRIMITIVES
// ============================================================================

const Card = ({ className = '', children, ...props }) => (
  <div className={`bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden ${className}`} {...props}>
    {children}
  </div>
);

const Button = ({ children, variant = 'primary', size = 'md', className = '', disabled, ...props }) => {
  const baseStyle = "inline-flex items-center justify-center rounded-lg font-medium transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:opacity-60 disabled:cursor-not-allowed";
  const variants = {
    primary: "bg-[#059669] text-white hover:bg-[#047857] focus:ring-[#059669] shadow-sm",
    secondary: "bg-slate-100 text-slate-900 hover:bg-slate-200 focus:ring-slate-500",
    outline: "border border-slate-300 text-slate-700 hover:bg-slate-50 focus:ring-slate-500",
    ghost: "text-slate-600 hover:bg-slate-100 hover:text-slate-900 focus:ring-slate-500",
    danger: "bg-rose-600 text-white hover:bg-rose-700 focus:ring-rose-500 shadow-sm"
  };
  const sizes = {
    sm: "px-3 py-1.5 text-sm",
    md: "px-4 py-2 text-sm",
    lg: "px-6 py-3 text-base"
  };

  return (
    <button 
      className={`${baseStyle} ${variants[variant]} ${sizes[size]} ${className}`} 
      disabled={disabled}
      {...props}
    >
      {children}
    </button>
  );
};

const Input = ({ label, id, error, icon: Icon, className = '', ...props }) => (
  <div className={`space-y-1.5 ${className}`}>
    {label && <label htmlFor={id} className="block text-sm font-medium text-slate-700 font-body">{label}</label>}
    <div className="relative">
      {Icon && (
        <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
          <Icon className="h-5 w-5 text-slate-400" />
        </div>
      )}
      <input
        id={id}
        className={`block w-full rounded-lg border ${error ? 'border-rose-300 focus:ring-rose-500 focus:border-rose-500' : 'border-slate-300 focus:ring-[#059669] focus:border-[#059669]'} bg-white px-4 py-2.5 text-slate-900 placeholder-slate-400 shadow-sm transition-colors font-body sm:text-sm ${Icon ? 'pl-10' : ''}`}
        {...props}
      />
    </div>
    {error && <p className="text-sm text-rose-600 font-body">{error}</p>}
  </div>
);

const Textarea = ({ label, id, error, className = '', ...props }) => (
  <div className={`space-y-1.5 ${className}`}>
    {label && <label htmlFor={id} className="block text-sm font-medium text-slate-700 font-body">{label}</label>}
    <textarea
      id={id}
      className={`block w-full rounded-lg border ${error ? 'border-rose-300 focus:ring-rose-500 focus:border-rose-500' : 'border-slate-300 focus:ring-[#059669] focus:border-[#059669]'} bg-white px-4 py-3 text-slate-900 placeholder-slate-400 shadow-sm transition-colors font-body sm:text-sm`}
      {...props}
    />
    {error && <p className="text-sm text-rose-600 font-body">{error}</p>}
  </div>
);

const Badge = ({ children, variant = 'default', className = '' }) => {
  const variants = {
    default: "bg-slate-100 text-slate-800 border-slate-200",
    success: "bg-emerald-100 text-emerald-800 border-emerald-200",
    warning: "bg-amber-100 text-amber-800 border-amber-200",
    primary: "bg-emerald-50 text-emerald-700 border-emerald-200"
  };
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${variants[variant]} ${className}`}>
      {children}
    </span>
  );
};

// ============================================================================
// HELPER FUNCTIONS
// ============================================================================

const getIconComponent = (iconName) => {
  const icons = {
    HardHat, FileText, Building, Car, Activity, Shield, 
    ShoppingCart, BookOpen, TreePine, Wine
  };
  return icons[iconName] || FileText;
};

// ============================================================================
// MAIN PAGE COMPONENT
// ============================================================================

export default function Workflow() {
  // --- State ---
  const [currentStep, setCurrentStep] = useState(1);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [aiAnalysisState, setAiAnalysisState] = useState('idle'); // idle, analyzing, complete
  const [trackingId, setTrackingId] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [openFaq, setOpenFaq] = useState(null);

  const [formData, setFormData] = useState({
    categoryId: '',
    categoryName: '',
    title: '',
    description: '',
    location: '',
    incidentDate: '',
    isAnonymous: true,
    evidenceFiles: []
  });

  const [errors, setErrors] = useState({});

  // --- Handlers ---
  const handleNext = () => {
    if (currentStep === 1 && !formData.categoryId) {
      setErrors({ category: 'Please select a department category.' });
      return;
    }
    if (currentStep === 2) {
      const newErrors = {};
      if (!formData.title.trim()) newErrors.title = 'Title is required.';
      if (!formData.description.trim()) newErrors.description = 'Description is required.';
      if (!formData.location.trim()) newErrors.location = 'Location is required.';
      if (!formData.incidentDate) newErrors.incidentDate = 'Date is required.';
      
      if (Object.keys(newErrors).length > 0) {
        setErrors(newErrors);
        return;
      }
    }

    setErrors({});
    setCurrentStep(prev => prev + 1);
    window.scrollTo({ top: 0, behavior: 'smooth' });

    // Trigger AI analysis simulation when entering step 3
    if (currentStep === 2) {
      setAiAnalysisState('analyzing');
      setTimeout(() => {
        setAiAnalysisState('complete');
      }, 2500);
    }
  };

  const handlePrev = () => {
    setCurrentStep(prev => prev - 1);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleCategorySelect = (cat) => {
    setFormData(prev => ({ ...prev, categoryId: cat.id, categoryName: cat.name }));
    setErrors({});
  };

  const handleInputChange = (e) => {
    const { id, value, type, checked } = e.target;
    setFormData(prev => ({
      ...prev,
      [id]: type === 'checkbox' ? checked : value
    }));
    if (errors[id]) {
      setErrors(prev => ({ ...prev, [id]: null }));
    }
  };

  const handleSubmit = () => {
    setIsSubmitting(true);
    // Simulate API call
    setTimeout(() => {
      setIsSubmitting(false);
      setTrackingId(`C3MS-${Math.floor(100000 + Math.random() * 900000)}`);
      setCurrentStep(4);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }, 1500);
  };

  const toggleFaq = (index) => {
    setOpenFaq(openFaq === index ? null : index);
  };

  // --- Derived Data ---
  const filteredCategories = useMemo(() => {
    return categories.filter(c => c.name.toLowerCase().includes(searchQuery.toLowerCase()));
  }, [searchQuery]);

  const steps = [
    { id: 1, name: 'Select Department', icon: Building },
    { id: 2, name: 'Incident Details', icon: FileText },
    { id: 3, name: 'Review & AI Check', icon: Cpu },
    { id: 4, name: 'Confirmation', icon: ShieldCheck }
  ];

  // ============================================================================
  // RENDER SECTIONS
  // ============================================================================

  return (
    <AppShell>
      <div className="min-h-screen bg-slate-50 pb-24">
        
        {/* SECTION 1: Hero / Header */}
        <div className="bg-slate-950 py-12 sm:py-16 relative overflow-hidden">
          <div className="absolute inset-0 opacity-10 bg-[linear-gradient(to_right,#4f4f4f2e_1px,transparent_1px),linear-gradient(to_bottom,#4f4f4f2e_1px,transparent_1px)] bg-[size:24px_24px]"></div>
          <div className="absolute left-1/2 top-0 -translate-x-1/2 blur-3xl opacity-20 pointer-events-none">
            <div className="aspect-[1155/678] w-[72.1875rem] bg-gradient-to-tr from-[#059669] to-[#0f172a]" style={{ clipPath: 'polygon(74.1% 44.1%, 100% 61.6%, 97.5% 26.9%, 85.5% 0.1%, 80.7% 2%, 72.5% 32.5%, 60.2% 62.4%, 52.4% 68.1%, 47.5% 58.3%, 45.2% 34.5%, 27.5% 76.7%, 0.1% 64.9%, 17.9% 100%, 27.6% 76.8%, 76.1% 97.7%, 74.1% 44.1%)' }} />
          </div>
          
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
            <div className="max-w-3xl">
              <Badge variant="primary" className="mb-4 bg-emerald-500/10 text-emerald-400 border-emerald-500/20">
                <Lock className="w-3 h-3 mr-1.5" /> Secure Reporting Workflow
              </Badge>
              <h1 className="text-3xl sm:text-4xl font-bold text-white font-display tracking-tight mb-4">
                File a Confidential Report
              </h1>
              <p className="text-lg text-slate-400 font-body">
                Your identity is protected by zero-knowledge proofs. Provide as much detail as possible to help our AI and investigators take swift action.
              </p>
            </div>
          </div>
        </div>

        {/* SECTION 2: Stepper Indicator */}
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 -mt-8 relative z-20">
          <Card className="p-4 sm:p-6 mb-8">
            <nav aria-label="Progress">
              <ol role="list" className="flex items-center justify-between w-full">
                {steps.map((stepItem, stepIdx) => {
                  const StepIcon = stepItem.icon;
                  const isActive = currentStep === stepItem.id;
                  const isCompleted = currentStep > stepItem.id;
                  
                  return (
                    <li key={stepItem.name} className={`relative ${stepIdx !== steps.length - 1 ? 'pr-8 sm:pr-20 w-full' : ''}`}>
                      {/* Connecting Line */}
                      {stepIdx !== steps.length - 1 && (
                        <div className="absolute top-1/2 left-0 -translate-y-1/2 w-full h-0.5 bg-slate-200" aria-hidden="true">
                          <div 
                            className="h-full bg-[#059669] transition-all duration-500 ease-in-out" 
                            style={{ width: isCompleted ? '100%' : '0%' }}
                          />
                        </div>
                      )}
                      
                      {/* Step Circle */}
                      <div className="relative flex items-center justify-center bg-white">
                        <div className={`
                          flex h-10 w-10 items-center justify-center rounded-full border-2 transition-colors duration-300
                          ${isCompleted ? 'bg-[#059669] border-[#059669]' : isActive ? 'border-[#059669] bg-emerald-50' : 'border-slate-300 bg-white'}
                        `}>
                          {isCompleted ? (
                            <Check className="h-5 w-5 text-white" aria-hidden="true" />
                          ) : (
                            <StepIcon className={`h-5 w-5 ${isActive ? 'text-[#059669]' : 'text-slate-400'}`} aria-hidden="true" />
                          )}
                        </div>
                        <span className={`absolute -bottom-6 w-max text-xs font-medium ${isActive ? 'text-[#059669]' : 'text-slate-500'}`}>
                          <span className="hidden sm:inline">Step {stepItem.id}: </span>{stepItem.name}
                        </span>
                      </div>
                    </li>
                  );
                })}
              </ol>
            </nav>
          </Card>

          {/* Main Content Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
            
            {/* Left Column: Wizard Content */}
            <div className="lg:col-span-8 space-y-6">
              
              {/* SECTION 3: Step 1 - Category Selection */}
              {currentStep === 1 && (
                <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
                  <div className="flex items-center justify-between mb-6">
                    <div>
                      <h2 className="text-xl font-bold text-slate-900 font-display">Select Department</h2>
                      <p className="text-sm text-slate-500 font-body mt-1">Which government department is involved in this incident?</p>
                    </div>
                    <div className="relative w-64 hidden sm:block">
                      <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                      <input 
                        type="text" 
                        placeholder="Search departments..." 
                        className="w-full pl-9 pr-4 py-2 rounded-lg border border-slate-200 text-sm focus:ring-[#059669] focus:border-[#059669]"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                      />
                    </div>
                  </div>

                  {errors.category && (
                    <div className="mb-4 p-3 bg-rose-50 border border-rose-200 rounded-lg flex items-start text-rose-700 text-sm">
                      <AlertTriangle className="h-5 w-5 mr-2 flex-shrink-0" />
                      {errors.category}
                    </div>
                  )}

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    {filteredCategories.map((cat) => {
                      const Icon = getIconComponent(cat.icon);
                      const isSelected = formData.categoryId === cat.id;
                      return (
                        <button
                          key={cat.id}
                          onClick={() => handleCategorySelect(cat)}
                          className={`
                            flex items-start p-4 rounded-xl border-2 text-left transition-all duration-200
                            ${isSelected 
                              ? 'border-[#059669] bg-emerald-50/50 shadow-sm' 
                              : 'border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50'}
                          `}
                        >
                          <div className={`p-2 rounded-lg mr-4 ${isSelected ? 'bg-[#059669] text-white' : 'bg-slate-100 text-slate-600'}`}>
                            <Icon className="h-5 w-5" />
                          </div>
                          <div>
                            <h3 className={`font-semibold font-display ${isSelected ? 'text-[#059669]' : 'text-slate-900'}`}>
                              {cat.name}
                            </h3>
                            <p className="text-xs text-slate-500 mt-1 font-body">
                              {cat.count} recent reports
                            </p>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* SECTION 4: Step 2 - Details Form */}
              {currentStep === 2 && (
                <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 space-y-6">
                  <div>
                    <h2 className="text-xl font-bold text-slate-900 font-display">Incident Details</h2>
                    <p className="text-sm text-slate-500 font-body mt-1">Provide specific information about the event. The more details, the better our AI can analyze it.</p>
                  </div>

                  <Card className="p-6 space-y-6">
                    <Input 
                      label="Report Title" 
                      id="title" 
                      placeholder="e.g., Bribery request for building permit" 
                      value={formData.title}
                      onChange={handleInputChange}
                      error={errors.title}
                    />

                    <Textarea 
                      label="Detailed Description" 
                      id="description" 
                      rows={5}
                      placeholder="Describe what happened, who was involved, and any other relevant context..." 
                      value={formData.description}
                      onChange={handleInputChange}
                      error={errors.description}
                    />

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                      <Input 
                        label="Location / Office" 
                        id="location" 
                        icon={MapPin}
                        placeholder="e.g., Thiruvananthapuram HQ" 
                        value={formData.location}
                        onChange={handleInputChange}
                        error={errors.location}
                      />
                      <Input 
                        label="Date of Incident" 
                        id="incidentDate" 
                        type="date"
                        icon={Calendar}
                        value={formData.incidentDate}
                        onChange={handleInputChange}
                        error={errors.incidentDate}
                      />
                    </div>

                    <div className="pt-4 border-t border-slate-100">
                      <label className="block text-sm font-medium text-slate-700 font-body mb-3">Evidence Upload (Optional)</label>
                      <div className="mt-1 flex justify-center px-6 pt-5 pb-6 border-2 border-slate-300 border-dashed rounded-xl hover:bg-slate-50 transition-colors cursor-pointer">
                        <div className="space-y-1 text-center">
                          <Upload className="mx-auto h-10 w-10 text-slate-400" />
                          <div className="flex text-sm text-slate-600 justify-center">
                            <span className="relative cursor-pointer bg-transparent rounded-md font-medium text-[#059669] hover:text-[#047857] focus-within:outline-none">
                              <span>Upload files</span>
                            </span>
                            <p className="pl-1">or drag and drop</p>
                          </div>
                          <p className="text-xs text-slate-500">PNG, JPG, PDF, MP3 up to 10MB</p>
                        </div>
                      </div>
                    </div>

                    <div className="pt-4 border-t border-slate-100">
                      <div className="flex items-start">
                        <div className="flex items-center h-5">
                          <input
                            id="isAnonymous"
                            type="checkbox"
                            checked={formData.isAnonymous}
                            onChange={handleInputChange}
                            className="focus:ring-[#059669] h-4 w-4 text-[#059669] border-slate-300 rounded"
                          />
                        </div>
                        <div className="ml-3 text-sm">
                          <label htmlFor="isAnonymous" className="font-medium text-slate-900 flex items-center gap-2">
                            Submit Anonymously <Badge variant="success">Recommended</Badge>
                          </label>
                          <p className="text-slate-500 mt-1">Your identity will be hidden from investigators and protected via cryptographic zero-knowledge proofs.</p>
                        </div>
                      </div>
                    </div>
                  </Card>
                </div>
              )}

              {/* SECTION 5: Step 3 - Review & AI Analysis */}
              {currentStep === 3 && (
                <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 space-y-6">
                  <div>
                    <h2 className="text-xl font-bold text-slate-900 font-display">Review & AI Verification</h2>
                    <p className="text-sm text-slate-500 font-body mt-1">Please review your report before final submission to the blockchain ledger.</p>
                  </div>

                  {/* AI Analysis Panel */}
                  <Card className={`p-6 border-2 transition-colors duration-500 ${aiAnalysisState === 'complete' ? 'border-emerald-500 bg-emerald-50/30' : 'border-blue-500 bg-blue-50/30'}`}>
                    <div className="flex items-start gap-4">
                      <div className={`p-3 rounded-full ${aiAnalysisState === 'complete' ? 'bg-emerald-100 text-emerald-600' : 'bg-blue-100 text-blue-600 animate-pulse'}`}>
                        <Cpu className="h-6 w-6" />
                      </div>
                      <div className="flex-1">
                        <h3 className="text-lg font-semibold text-slate-900 font-display flex items-center gap-2">
                          C3MS Predictive AI Analysis
                          {aiAnalysisState === 'complete' && <Badge variant="success">Complete</Badge>}
                        </h3>
                        
                        {aiAnalysisState === 'analyzing' ? (
                          <div className="mt-3 space-y-2">
                            <p className="text-sm text-slate-600">Cross-referencing historical data and analyzing text patterns...</p>
                            <div className="w-full bg-slate-200 rounded-full h-1.5 overflow-hidden">
                              <div className="bg-blue-500 h-1.5 rounded-full animate-[progress_2s_ease-in-out_infinite]" style={{ width: '60%' }}></div>
                            </div>
                          </div>
                        ) : (
                          <div className="mt-4 grid grid-cols-1 sm:grid-cols-3 gap-4">
                            <div className="bg-white p-3 rounded-lg border border-slate-200 shadow-sm">
                              <p className="text-xs text-slate-500 uppercase tracking-wider font-semibold mb-1">Credibility Score</p>
                              <p className="text-2xl font-bold text-emerald-600">92%</p>
                            </div>
                            <div className="bg-white p-3 rounded-lg border border-slate-200 shadow-sm">
                              <p className="text-xs text-slate-500 uppercase tracking-wider font-semibold mb-1">Risk Level</p>
                              <p className="text-lg font-bold text-amber-600 flex items-center gap-1"><AlertTriangle className="w-4 h-4"/> High</p>
                            </div>
                            <div className="bg-white p-3 rounded-lg border border-slate-200 shadow-sm">
                              <p className="text-xs text-slate-500 uppercase tracking-wider font-semibold mb-1">Action</p>
                              <p className="text-sm font-medium text-slate-900">Priority Routing</p>
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  </Card>

                  {/* Summary Card */}
                  <Card className="overflow-hidden">
                    <div className="bg-slate-50 px-6 py-4 border-b border-slate-200 flex justify-between items-center">
                      <h3 className="font-semibold text-slate-900">Report Summary</h3>
                      <Button variant="ghost" size="sm" onClick={() => setCurrentStep(2)}>Edit Details</Button>
                    </div>
                    <div className="p-6 space-y-4">
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-y-4 gap-x-6">
                        <div>
                          <p className="text-sm text-slate-500 mb-1">Department</p>
                          <p className="font-medium text-slate-900 flex items-center gap-2">
                            <Building className="w-4 h-4 text-slate-400" /> {formData.categoryName}
                          </p>
                        </div>
                        <div>
                          <p className="text-sm text-slate-500 mb-1">Identity Status</p>
                          <p className="font-medium text-slate-900 flex items-center gap-2">
                            {formData.isAnonymous ? (
                              <><EyeOff className="w-4 h-4 text-emerald-600" /> Anonymous (Protected)</>
                            ) : (
                              <><Info className="w-4 h-4 text-amber-600" /> Disclosed to Investigators</>
                            )}
                          </p>
                        </div>
                        <div className="sm:col-span-2">
                          <p className="text-sm text-slate-500 mb-1">Title</p>
                          <p className="font-medium text-slate-900">{formData.title}</p>
                        </div>
                        <div className="sm:col-span-2">
                          <p className="text-sm text-slate-500 mb-1">Description</p>
                          <p className="text-sm text-slate-700 bg-slate-50 p-3 rounded-lg border border-slate-100">{formData.description}</p>
                        </div>
                        <div>
                          <p className="text-sm text-slate-500 mb-1">Location</p>
                          <p className="font-medium text-slate-900">{formData.location}</p>
                        </div>
                        <div>
                          <p className="text-sm text-slate-500 mb-1">Date</p>
                          <p className="font-medium text-slate-900">{formData.incidentDate}</p>
                        </div>
                      </div>
                    </div>
                  </Card>
                </div>
              )}

              {/* SECTION 6: Step 4 - Success Confirmation */}
              {currentStep === 4 && (
                <div className="animate-in zoom-in-95 duration-500">
                  <Card className="p-8 sm:p-12 text-center border-emerald-200 bg-emerald-50/30">
                    <div className="mx-auto w-20 h-20 bg-emerald-100 rounded-full flex items-center justify-center mb-6">
                      <CheckCircle className="w-10 h-10 text-emerald-600" />
                    </div>
                    <h2 className="text-3xl font-bold text-slate-900 font-display mb-2">Report Submitted Securely</h2>
                    <p className="text-slate-600 mb-8 max-w-md mx-auto">
                      Your report has been encrypted and recorded on the immutable blockchain ledger. Our AI has already routed it to the appropriate investigative unit.
                    </p>
                    
                    <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm max-w-sm mx-auto mb-8">
                      <p className="text-sm text-slate-500 uppercase tracking-wider font-semibold mb-2">Your Tracking ID</p>
                      <div className="flex items-center justify-center gap-3">
                        <code className="text-2xl font-mono font-bold text-slate-900 bg-slate-100 px-4 py-2 rounded-lg">
                          {trackingId}
                        </code>
                      </div>
                      <p className="text-xs text-amber-600 mt-3 flex items-center justify-center gap-1">
                        <AlertTriangle className="w-3 h-3" /> Save this ID. It cannot be recovered if lost.
                      </p>
                    </div>

                    <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
                      <Link to="/dashboard">
                        <Button variant="primary" size="lg">Go to Dashboard</Button>
                      </Link>
                      <Link to="/explore">
                        <Button variant="outline" size="lg">Explore Public Records</Button>
                      </Link>
                    </div>
                  </Card>
                </div>
              )}

              {/* Navigation Buttons (Hidden on Step 4) */}
              {currentStep < 4 && (
                <div className="flex items-center justify-between pt-6 border-t border-slate-200 mt-8">
                  <Button 
                    variant="ghost" 
                    onClick={handlePrev} 
                    disabled={currentStep === 1 || isSubmitting}
                  >
                    <ChevronLeft className="w-4 h-4 mr-2" /> Back
                  </Button>
                  
                  {currentStep < 3 ? (
                    <Button variant="primary" onClick={handleNext}>
                      Continue <ChevronRight className="w-4 h-4 ml-2" />
                    </Button>
                  ) : (
                    <Button 
                      variant="primary" 
                      onClick={handleSubmit} 
                      disabled={isSubmitting || aiAnalysisState !== 'complete'}
                      className="min-w-[160px]"
                    >
                      {isSubmitting ? (
                        <span className="flex items-center">
                          <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                          Encrypting...
                        </span>
                      ) : (
                        <span className="flex items-center">
                          Submit Securely <Lock className="w-4 h-4 ml-2" />
                        </span>
                      )}
                    </Button>
                  )}
                </div>
              )}
            </div>

            {/* Right Column: Contextual Sidebar */}
            <div className="lg:col-span-4 space-y-6">
              
              {/* Dynamic Help Card based on Step */}
              <Card className="p-6 bg-slate-900 text-white border-slate-800">
                <div className="flex items-center gap-3 mb-4">
                  <div className="p-2 bg-emerald-500/20 rounded-lg">
                    <Info className="w-5 h-5 text-emerald-400" />
                  </div>
                  <h3 className="font-display font-semibold text-lg">Guidance</h3>
                </div>
                
                <div className="text-slate-300 text-sm space-y-4 font-body">
                  {currentStep === 1 && (
                    <>
                      <p>Selecting the correct department ensures your report is routed to the specialized investigative unit immediately.</p>
                      <p>If you are unsure, select the department that most closely matches the office or service involved.</p>
                    </>
                  )}
                  {currentStep === 2 && (
                    <>
                      <p><strong>Be Specific:</strong> Include names, designations, exact amounts, and timelines if known.</p>
                      <p><strong>Evidence:</strong> Audio recordings, photos of documents, or screenshots significantly increase the AI credibility score.</p>
                      <p className="text-emerald-400 flex items-center gap-2 mt-4 pt-4 border-t border-slate-800">
                        <Shield className="w-4 h-4" /> Your IP address is not logged.
                      </p>
                    </>
                  )}
                  {currentStep === 3 && (
                    <>
                      <p>Our Predictive AI analyzes your report against thousands of historical records to flag systemic issues and prioritize high-risk cases.</p>
                      <p>Once submitted, this record is hashed and stored on the blockchain, making it tamper-proof.</p>
                    </>
                  )}
                  {currentStep === 4 && (
                    <>
                      <p>Your report is now active in the system.</p>
                      <p>Use your Tracking ID to check status updates anonymously. Do not share this ID with anyone.</p>
                    </>
                  )}
                </div>
              </Card>

              {/* Trust & Security Banner */}
              <Card className="p-5 border-emerald-100 bg-emerald-50/50">
                <h4 className="font-semibold text-slate-900 flex items-center gap-2 mb-3 text-sm">
                  <Database className="w-4 h-4 text-emerald-600" /> Blockchain Verified
                </h4>
                <p className="text-xs text-slate-600 leading-relaxed">
                  Every report submitted through C3MS is cryptographically hashed and stored on an immutable ledger. This guarantees that no official can alter or delete your complaint once filed.
                </p>
              </Card>

            </div>
          </div>
        </div>

        {/* SECTION 7: FAQ Accordion */}
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 mt-24">
          <div className="text-center mb-10">
            <h2 className="text-2xl font-bold text-slate-900 font-display">Frequently Asked Questions</h2>
            <p className="text-slate-500 mt-2">Learn more about how the C3MS reporting process works.</p>
          </div>
          
          <div className="space-y-4">
            {[
              { q: "How is my anonymity guaranteed?", a: "We use Zero-Knowledge Proofs (ZKP) to authenticate your session without linking it to your personal identity. Your IP address is stripped, and the data is encrypted before it reaches our servers." },
              { q: "What happens after I submit?", a: "Our AI immediately analyzes the report for credibility and risk. It is then routed to the appropriate Vigilance officer. You can track the progress using your unique Tracking ID." },
              { q: "Can I add evidence later?", a: "Yes. You can log in using your Tracking ID and append additional files or text to your existing report at any time." },
              { q: "What if the accused officer tries to delete my report?", a: "They cannot. All reports are hashed and anchored to a blockchain ledger. Any attempt to tamper with the database will trigger an immediate system-wide alert." }
            ].map((faq, idx) => (
              <Card key={idx} className="overflow-hidden transition-all duration-200">
                <button 
                  className="w-full px-6 py-4 text-left flex justify-between items-center focus:outline-none"
                  onClick={() => toggleFaq(idx)}
                >
                  <span className="font-medium text-slate-900">{faq.q}</span>
                  {openFaq === idx ? (
                    <ChevronUp className="w-5 h-5 text-slate-400" />
                  ) : (
                    <ChevronDown className="w-5 h-5 text-slate-400" />
                  )}
                </button>
                {openFaq === idx && (
                  <div className="px-6 pb-4 text-slate-600 text-sm border-t border-slate-100 pt-4 bg-slate-50">
                    {faq.a}
                  </div>
                )}
              </Card>
            ))}
          </div>
        </div>

      </div>
    </AppShell>
  );
}
