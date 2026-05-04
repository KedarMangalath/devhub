import React, { useState, useEffect, useRef } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { 
  Shield, 
  AlertTriangle, 
  CheckCircle, 
  ChevronRight, 
  ChevronLeft,
  UploadCloud,
  FileText,
  Lock,
  EyeOff,
  Eye,
  Info,
  MapPin,
  Calendar,
  Clock,
  Building,
  HardHat,
  Activity,
  Car,
  ShieldCheck,
  ShoppingCart,
  BookOpen,
  TreePine,
  Wine,
  HelpCircle,
  X,
  File,
  Check,
  Cpu,
  Fingerprint,
  Copy
} from 'lucide-react';

import AppShell from '../components/AppShell';
import PageHero from '../components/PageHero';
import { categories } from '../mockData';

// ============================================================================
// INLINE UI PRIMITIVES
// Built inline to ensure the page is 100% self-contained and working without
// relying on external UI files not explicitly listed in the project plan.
// ============================================================================

const Card = ({ className = '', children, ...props }) => (
  <div 
    className={`rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden ${className}`} 
    {...props}
  >
    {children}
  </div>
);

const Button = React.forwardRef(({ className = '', variant = "default", size = "default", children, disabled, ...props }, ref) => {
  const variants = {
    default: "bg-emerald-600 text-white hover:bg-emerald-700 shadow-sm border border-transparent",
    outline: "border border-slate-300 bg-transparent text-slate-700 hover:bg-slate-50",
    ghost: "hover:bg-slate-100 text-slate-700",
    secondary: "bg-slate-100 text-slate-900 hover:bg-slate-200",
    danger: "bg-rose-600 text-white hover:bg-rose-700 shadow-sm",
  };
  const sizes = {
    default: "h-11 px-6 py-2",
    sm: "h-9 rounded-md px-4 text-sm",
    lg: "h-14 rounded-lg px-8 text-lg",
    icon: "h-11 w-11",
  };
  
  return (
    <button 
      ref={ref} 
      disabled={disabled}
      className={`inline-flex items-center justify-center rounded-lg font-medium transition-all focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed ${variants[variant]} ${sizes[size]} ${className}`} 
      {...props}
    >
      {children}
    </button>
  );
});
Button.displayName = "Button";

const Input = React.forwardRef(({ className = '', error, icon: Icon, ...props }, ref) => {
  return (
    <div className="relative w-full">
      {Icon && (
        <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
          <Icon className="h-5 w-5 text-slate-400" />
        </div>
      )}
      <input
        ref={ref}
        className={`flex h-11 w-full rounded-lg border ${error ? 'border-rose-500 focus:ring-rose-500' : 'border-slate-300 focus:ring-emerald-500'} bg-white px-3 py-2 text-sm placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:border-transparent disabled:cursor-not-allowed disabled:opacity-50 ${Icon ? 'pl-10' : ''} ${className}`}
        {...props}
      />
      {error && <p className="mt-1 text-xs text-rose-500">{error}</p>}
    </div>
  );
});
Input.displayName = "Input";

const Textarea = React.forwardRef(({ className = '', error, ...props }, ref) => {
  return (
    <div className="w-full">
      <textarea
        ref={ref}
        className={`flex min-h-[120px] w-full rounded-lg border ${error ? 'border-rose-500 focus:ring-rose-500' : 'border-slate-300 focus:ring-emerald-500'} bg-white px-3 py-2 text-sm placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:border-transparent disabled:cursor-not-allowed disabled:opacity-50 ${className}`}
        {...props}
      />
      {error && <p className="mt-1 text-xs text-rose-500">{error}</p>}
    </div>
  );
});
Textarea.displayName = "Textarea";

const Label = React.forwardRef(({ className = '', children, required, ...props }, ref) => (
  <label
    ref={ref}
    className={`text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 text-slate-700 mb-2 block ${className}`}
    {...props}
  >
    {children}
    {required && <span className="text-rose-500 ml-1">*</span>}
  </label>
));
Label.displayName = "Label";

const Badge = ({ className = '', variant = "default", children, ...props }) => {
  const variants = {
    default: "bg-slate-100 text-slate-800",
    primary: "bg-emerald-100 text-emerald-800",
    warning: "bg-amber-100 text-amber-800",
    danger: "bg-rose-100 text-rose-800",
  };
  
  return (
    <span 
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${variants[variant]} ${className}`} 
      {...props}
    >
      {children}
    </span>
  );
};

// ============================================================================
// HELPER COMPONENTS
// ============================================================================

const IconMap = {
  HardHat, FileText, Building, Car, Activity, Shield, ShoppingCart, BookOpen, TreePine, Wine
};

const districts = [
  "Thiruvananthapuram", "Kollam", "Pathanamthitta", "Alappuzha", "Kottayam", 
  "Idukki", "Ernakulam", "Thrissur", "Palakkad", "Malappuram", "Kozhikode", 
  "Wayanad", "Kannur", "Kasaragod"
];

// ============================================================================
// MAIN PAGE COMPONENT
// ============================================================================

export default function FileComplaintWorkflow() {
  const navigate = useNavigate();
  
  // --- State Management ---
  const [currentStep, setCurrentStep] = useState(1);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [aiAnalyzing, setAiAnalyzing] = useState(false);
  const [trackingId, setTrackingId] = useState(null);
  
  const [formData, setFormData] = useState({
    categoryId: '',
    district: '',
    title: '',
    description: '',
    date: '',
    time: '',
    locationDetails: '',
    files: [],
    isAnonymous: true,
    contactPhone: '',
    contactEmail: ''
  });

  const [errors, setErrors] = useState({});

  // --- Handlers ---
  const handleInputChange = (field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    // Clear error when typing
    if (errors[field]) {
      setErrors(prev => ({ ...prev, [field]: null }));
    }
  };

  const handleFileUpload = (e) => {
    const newFiles = Array.from(e.target.files).map(file => ({
      name: file.name,
      size: (file.size / 1024 / 1024).toFixed(2) + ' MB',
      type: file.type,
      id: Math.random().toString(36).substring(7)
    }));
    
    setFormData(prev => ({
      ...prev,
      files: [...prev.files, ...newFiles]
    }));
  };

  const removeFile = (id) => {
    setFormData(prev => ({
      ...prev,
      files: prev.files.filter(f => f.id !== id)
    }));
  };

  const validateStep = () => {
    const newErrors = {};
    let isValid = true;

    if (currentStep === 2) {
      if (!formData.categoryId) { newErrors.categoryId = 'Please select a department category.'; isValid = false; }
      if (!formData.district) { newErrors.district = 'Please select a district.'; isValid = false; }
    }
    
    if (currentStep === 3) {
      if (!formData.title || formData.title.length < 10) { newErrors.title = 'Title must be at least 10 characters.'; isValid = false; }
      if (!formData.description || formData.description.length < 50) { newErrors.description = 'Please provide more details (min 50 characters).'; isValid = false; }
      if (!formData.date) { newErrors.date = 'Date of incident is required.'; isValid = false; }
    }

    if (currentStep === 5 && !formData.isAnonymous) {
      if (!formData.contactPhone && !formData.contactEmail) {
        newErrors.contact = 'Please provide either a phone number or email if not reporting anonymously.';
        isValid = false;
      }
    }

    setErrors(newErrors);
    return isValid;
  };

  const nextStep = () => {
    if (validateStep()) {
      window.scrollTo({ top: 0, behavior: 'smooth' });
      if (currentStep === 5) {
        // Simulate AI Analysis before review step
        setAiAnalyzing(true);
        setCurrentStep(6);
        setTimeout(() => {
          setAiAnalyzing(false);
        }, 2500);
      } else {
        setCurrentStep(prev => Math.min(prev + 1, 7));
      }
    }
  };

  const prevStep = () => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
    setCurrentStep(prev => Math.max(prev - 1, 1));
  };

  const handleSubmit = () => {
    setIsSubmitting(true);
    // Simulate API call and blockchain hashing
    setTimeout(() => {
      setIsSubmitting(false);
      setTrackingId(`C3MS-${new Date().getFullYear()}-${Math.floor(1000 + Math.random() * 9000)}-${Math.random().toString(36).substring(2, 5).toUpperCase()}`);
      setCurrentStep(7);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }, 3000);
  };

  const fillSampleData = () => {
    setFormData({
      categoryId: 'cat-1',
      district: 'Thiruvananthapuram',
      title: 'Demand for bribe during building permit approval',
      description: 'The assistant engineer at the local LSGD office demanded a bribe of ₹25,000 to process my residential building permit, despite all documents being in order. He explicitly stated that the file would not move without the "processing fee". I have recorded the conversation.',
      date: '2023-10-20',
      time: '14:30',
      locationDetails: 'LSGD Office, Ward 14, Main Building, 2nd Floor',
      files: [
        { name: 'audio_recording_oct20.mp3', size: '2.4 MB', type: 'audio/mp3', id: 'f1' },
        { name: 'permit_application_copy.pdf', size: '1.1 MB', type: 'application/pdf', id: 'f2' }
      ],
      isAnonymous: true,
      contactPhone: '',
      contactEmail: ''
    });
    setCurrentStep(2);
  };

  // --- Render Helpers ---
  const steps = [
    { num: 1, title: 'Guidelines' },
    { num: 2, title: 'Category' },
    { num: 3, title: 'Details' },
    { num: 4, title: 'Evidence' },
    { num: 5, title: 'Identity' },
    { num: 6, title: 'Review' }
  ];

  const selectedCategory = categories.find(c => c.id === formData.categoryId);

  return (
    <AppShell>
      {/* Hero Section */}
      <PageHero 
        title="File a Secure Report"
        sub="Your identity is protected by zero-knowledge encryption. Provide as much detail as possible to help our AI and investigators take swift action."
        breadcrumbs={[
          { label: 'Report', href: '/report' }
        ]}
        badge={{ text: "End-to-End Encrypted", icon: Lock }}
      />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        
        {/* Stepper UI (Hidden on Success Step) */}
        {currentStep < 7 && (
          <div className="mb-12">
            <div className="hidden md:flex items-center justify-between relative">
              <div className="absolute left-0 top-1/2 -translate-y-1/2 w-full h-1 bg-slate-200 -z-10 rounded-full"></div>
              <div 
                className="absolute left-0 top-1/2 -translate-y-1/2 h-1 bg-emerald-500 -z-10 rounded-full transition-all duration-500 ease-in-out"
                style={{ width: `${((currentStep - 1) / (steps.length - 1)) * 100}%` }}
              ></div>
              
              {steps.map((step) => (
                <div key={step.num} className="flex flex-col items-center gap-2 bg-slate-50 px-2">
                  <div 
                    className={`w-10 h-10 rounded-full flex items-center justify-center font-bold text-sm transition-colors duration-300 ${
                      currentStep > step.num 
                        ? 'bg-emerald-500 text-white' 
                        : currentStep === step.num 
                          ? 'bg-emerald-600 text-white ring-4 ring-emerald-100' 
                          : 'bg-white border-2 border-slate-300 text-slate-400'
                    }`}
                  >
                    {currentStep > step.num ? <Check className="w-5 h-5" /> : step.num}
                  </div>
                  <span className={`text-xs font-medium ${currentStep >= step.num ? 'text-slate-900' : 'text-slate-400'}`}>
                    {step.title}
                  </span>
                </div>
              ))}
            </div>
            
            {/* Mobile Stepper */}
            <div className="md:hidden flex items-center justify-between">
              <span className="text-sm font-medium text-slate-500">Step {currentStep} of {steps.length}</span>
              <span className="text-sm font-bold text-slate-900">{steps[currentStep-1]?.title}</span>
            </div>
            <div className="md:hidden w-full h-2 bg-slate-200 rounded-full mt-3">
              <div 
                className="h-full bg-emerald-500 rounded-full transition-all duration-300"
                style={{ width: `${(currentStep / steps.length) * 100}%` }}
              ></div>
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          
          {/* Main Form Area */}
          <div className="lg:col-span-2">
            <Card className="p-6 sm:p-8 min-h-[500px] flex flex-col">
              
              {/* STEP 1: Guidelines */}
              {currentStep === 1 && (
                <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 flex-grow">
                  <div className="flex items-center gap-3 mb-6">
                    <div className="p-3 bg-emerald-100 rounded-lg text-emerald-600">
                      <ShieldCheck className="w-6 h-6" />
                    </div>
                    <h2 className="text-2xl font-display font-bold text-slate-900">Before you begin</h2>
                  </div>
                  
                  <div className="prose prose-slate max-w-none mb-8">
                    <p className="text-slate-600 text-lg">
                      The Vigilance C3MS platform is designed to securely process reports of corruption, bribery, and misuse of public office in Kerala.
                    </p>
                    
                    <div className="bg-amber-50 border border-amber-200 rounded-xl p-5 my-6">
                      <h4 className="flex items-center gap-2 text-amber-800 font-semibold mb-2 m-0">
                        <AlertTriangle className="w-5 h-5" />
                        Important Notice
                      </h4>
                      <p className="text-amber-700 text-sm m-0">
                        Filing a false report with malicious intent is a punishable offense. Please ensure all information provided is accurate to the best of your knowledge.
                      </p>
                    </div>

                    <h3 className="text-lg font-semibold text-slate-900 mt-8 mb-4">What you will need:</h3>
                    <ul className="space-y-3 text-slate-600">
                      <li className="flex items-start gap-3">
                        <CheckCircle className="w-5 h-5 text-emerald-500 shrink-0 mt-0.5" />
                        <span>Specific details about the incident (Date, Time, Location).</span>
                      </li>
                      <li className="flex items-start gap-3">
                        <CheckCircle className="w-5 h-5 text-emerald-500 shrink-0 mt-0.5" />
                        <span>The department or official involved (if known).</span>
                      </li>
                      <li className="flex items-start gap-3">
                        <CheckCircle className="w-5 h-5 text-emerald-500 shrink-0 mt-0.5" />
                        <span>Any supporting evidence (Audio, Video, Documents, Photos).</span>
                      </li>
                    </ul>
                  </div>

                  <div className="mt-auto pt-8 border-t border-slate-100 flex justify-between items-center">
                    <Button variant="ghost" onClick={fillSampleData} className="text-slate-400 hover:text-emerald-600">
                      Auto-fill Demo Data
                    </Button>
                    <Button onClick={nextStep} size="lg" className="gap-2">
                      I Understand, Start Report <ChevronRight className="w-5 h-5" />
                    </Button>
                  </div>
                </div>
              )}

              {/* STEP 2: Category & Location */}
              {currentStep === 2 && (
                <div className="animate-in fade-in slide-in-from-right-4 duration-500 flex-grow flex flex-col">
                  <h2 className="text-2xl font-display font-bold text-slate-900 mb-2">Department & Location</h2>
                  <p className="text-slate-500 mb-8">Select the department involved and the district where the incident occurred.</p>

                  <div className="space-y-8 flex-grow">
                    <div>
                      <Label required>Which department is involved?</Label>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-3">
                        {categories.map(cat => {
                          const Icon = IconMap[cat.icon] || Building;
                          const isSelected = formData.categoryId === cat.id;
                          return (
                            <button
                              key={cat.id}
                              onClick={() => handleInputChange('categoryId', cat.id)}
                              className={`flex items-center gap-3 p-4 rounded-xl border text-left transition-all duration-200 ${
                                isSelected 
                                  ? 'border-emerald-500 bg-emerald-50 ring-1 ring-emerald-500' 
                                  : 'border-slate-200 hover:border-emerald-300 hover:bg-slate-50'
                              }`}
                            >
                              <div className={`p-2 rounded-lg ${isSelected ? 'bg-emerald-500 text-white' : 'bg-slate-100 text-slate-500'}`}>
                                <Icon className="w-5 h-5" />
                              </div>
                              <span className={`font-medium ${isSelected ? 'text-emerald-900' : 'text-slate-700'}`}>
                                {cat.name}
                              </span>
                            </button>
                          );
                        })}
                      </div>
                      {errors.categoryId && <p className="mt-2 text-sm text-rose-500 flex items-center gap-1"><AlertTriangle className="w-4 h-4"/> {errors.categoryId}</p>}
                    </div>

                    <div>
                      <Label required>District</Label>
                      <div className="relative">
                        <MapPin className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 w-5 h-5" />
                        <select
                          value={formData.district}
                          onChange={(e) => handleInputChange('district', e.target.value)}
                          className={`w-full h-11 pl-10 pr-4 rounded-lg border ${errors.district ? 'border-rose-500' : 'border-slate-300'} bg-white text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 appearance-none`}
                        >
                          <option value="" disabled>Select a district...</option>
                          {districts.map(d => (
                            <option key={d} value={d}>{d}</option>
                          ))}
                        </select>
                      </div>
                      {errors.district && <p className="mt-2 text-sm text-rose-500 flex items-center gap-1"><AlertTriangle className="w-4 h-4"/> {errors.district}</p>}
                    </div>
                  </div>

                  <div className="mt-8 pt-6 border-t border-slate-100 flex justify-between">
                    <Button variant="outline" onClick={prevStep}>Back</Button>
                    <Button onClick={nextStep}>Continue</Button>
                  </div>
                </div>
              )}

              {/* STEP 3: Details */}
              {currentStep === 3 && (
                <div className="animate-in fade-in slide-in-from-right-4 duration-500 flex-grow flex flex-col">
                  <h2 className="text-2xl font-display font-bold text-slate-900 mb-2">Incident Details</h2>
                  <p className="text-slate-500 mb-8">Provide a clear and factual description of what happened.</p>

                  <div className="space-y-6 flex-grow">
                    <div>
                      <Label required>Report Title</Label>
                      <Input 
                        placeholder="e.g., Demand for bribe during building permit approval" 
                        value={formData.title}
                        onChange={(e) => handleInputChange('title', e.target.value)}
                        error={errors.title}
                      />
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                      <div>
                        <Label required>Date of Incident</Label>
                        <Input 
                          type="date" 
                          icon={Calendar}
                          value={formData.date}
                          onChange={(e) => handleInputChange('date', e.target.value)}
                          error={errors.date}
                        />
                      </div>
                      <div>
                        <Label>Time (Approximate)</Label>
                        <Input 
                          type="time" 
                          icon={Clock}
                          value={formData.time}
                          onChange={(e) => handleInputChange('time', e.target.value)}
                        />
                      </div>
                    </div>

                    <div>
                      <Label>Specific Location / Office Name</Label>
                      <Input 
                        placeholder="e.g., LSGD Office, Ward 14, Main Building" 
                        icon={Building}
                        value={formData.locationDetails}
                        onChange={(e) => handleInputChange('locationDetails', e.target.value)}
                      />
                    </div>

                    <div>
                      <Label required>Detailed Description</Label>
                      <Textarea 
                        placeholder="Describe the sequence of events, names of officials involved (if known), and any other relevant context..." 
                        value={formData.description}
                        onChange={(e) => handleInputChange('description', e.target.value)}
                        error={errors.description}
                        className="min-h-[150px]"
                      />
                      <p className="text-xs text-slate-500 mt-2 text-right">
                        {formData.description.length} characters (min 50)
                      </p>
                    </div>
                  </div>

                  <div className="mt-8 pt-6 border-t border-slate-100 flex justify-between">
                    <Button variant="outline" onClick={prevStep}>Back</Button>
                    <Button onClick={nextStep}>Continue</Button>
                  </div>
                </div>
              )}

              {/* STEP 4: Evidence */}
              {currentStep === 4 && (
                <div className="animate-in fade-in slide-in-from-right-4 duration-500 flex-grow flex flex-col">
                  <h2 className="text-2xl font-display font-bold text-slate-900 mb-2">Upload Evidence</h2>
                  <p className="text-slate-500 mb-8">Attach any documents, photos, or audio recordings that support your claim. Files are encrypted before upload.</p>

                  <div className="flex-grow">
                    {/* Drag & Drop Zone */}
                    <div className="border-2 border-dashed border-slate-300 rounded-xl bg-slate-50 p-10 text-center hover:bg-slate-100 hover:border-emerald-400 transition-colors cursor-pointer relative">
                      <input 
                        type="file" 
                        multiple 
                        className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                        onChange={handleFileUpload}
                        title="Upload files"
                      />
                      <div className="mx-auto w-16 h-16 bg-white rounded-full shadow-sm flex items-center justify-center mb-4 text-emerald-600">
                        <UploadCloud className="w-8 h-8" />
                      </div>
                      <h3 className="text-lg font-semibold text-slate-900 mb-1">Click or drag files here</h3>
                      <p className="text-sm text-slate-500 mb-4">Supports PDF, JPG, PNG, MP3, MP4 (Max 50MB per file)</p>
                      <Button variant="outline" size="sm" className="pointer-events-none">Browse Files</Button>
                    </div>

                    {/* File List */}
                    {formData.files.length > 0 && (
                      <div className="mt-8">
                        <h4 className="text-sm font-semibold text-slate-900 mb-3 flex items-center gap-2">
                          <FileText className="w-4 h-4" /> Attached Files ({formData.files.length})
                        </h4>
                        <div className="space-y-3">
                          {formData.files.map(file => (
                            <div key={file.id} className="flex items-center justify-between p-3 bg-white border border-slate-200 rounded-lg shadow-sm">
                              <div className="flex items-center gap-3 overflow-hidden">
                                <div className="p-2 bg-emerald-50 text-emerald-600 rounded-md shrink-0">
                                  <File className="w-5 h-5" />
                                </div>
                                <div className="truncate">
                                  <p className="text-sm font-medium text-slate-900 truncate">{file.name}</p>
                                  <p className="text-xs text-slate-500">{file.size}</p>
                                </div>
                              </div>
                              <button 
                                onClick={() => removeFile(file.id)}
                                className="p-2 text-slate-400 hover:text-rose-500 hover:bg-rose-50 rounded-md transition-colors"
                                aria-label="Remove file"
                              >
                                <X className="w-4 h-4" />
                              </button>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>

                  <div className="mt-8 pt-6 border-t border-slate-100 flex justify-between">
                    <Button variant="outline" onClick={prevStep}>Back</Button>
                    <Button onClick={nextStep}>Continue</Button>
                  </div>
                </div>
              )}

              {/* STEP 5: Identity Protection */}
              {currentStep === 5 && (
                <div className="animate-in fade-in slide-in-from-right-4 duration-500 flex-grow flex flex-col">
                  <h2 className="text-2xl font-display font-bold text-slate-900 mb-2">Identity Protection</h2>
                  <p className="text-slate-500 mb-8">Choose how you want to submit this report. The Whistleblower Protection Act guarantees your safety.</p>

                  <div className="space-y-6 flex-grow">
                    
                    {/* Toggle Cards */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div 
                        onClick={() => handleInputChange('isAnonymous', true)}
                        className={`cursor-pointer rounded-xl border-2 p-5 transition-all ${
                          formData.isAnonymous 
                            ? 'border-emerald-500 bg-emerald-50/50' 
                            : 'border-slate-200 hover:border-emerald-200 bg-white'
                        }`}
                      >
                        <div className="flex justify-between items-start mb-4">
                          <div className={`p-3 rounded-lg ${formData.isAnonymous ? 'bg-emerald-500 text-white' : 'bg-slate-100 text-slate-500'}`}>
                            <EyeOff className="w-6 h-6" />
                          </div>
                          {formData.isAnonymous && <CheckCircle className="w-6 h-6 text-emerald-500" />}
                        </div>
                        <h3 className="text-lg font-bold text-slate-900 mb-2">Submit Anonymously</h3>
                        <p className="text-sm text-slate-600">
                          Your identity is completely hidden using Zero-Knowledge Proofs. You will receive a secure Tracking ID to check updates without revealing who you are.
                        </p>
                        <Badge variant="primary" className="mt-4">Recommended</Badge>
                      </div>

                      <div 
                        onClick={() => handleInputChange('isAnonymous', false)}
                        className={`cursor-pointer rounded-xl border-2 p-5 transition-all ${
                          !formData.isAnonymous 
                            ? 'border-emerald-500 bg-emerald-50/50' 
                            : 'border-slate-200 hover:border-emerald-200 bg-white'
                        }`}
                      >
                        <div className="flex justify-between items-start mb-4">
                          <div className={`p-3 rounded-lg ${!formData.isAnonymous ? 'bg-emerald-500 text-white' : 'bg-slate-100 text-slate-500'}`}>
                            <Eye className="w-6 h-6" />
                          </div>
                          {!formData.isAnonymous && <CheckCircle className="w-6 h-6 text-emerald-500" />}
                        </div>
                        <h3 className="text-lg font-bold text-slate-900 mb-2">Provide Contact Info</h3>
                        <p className="text-sm text-slate-600">
                          Share your details securely with the investigating officer. This allows them to contact you directly for further clarification if needed.
                        </p>
                      </div>
                    </div>

                    {/* Conditional Contact Fields */}
                    {!formData.isAnonymous && (
                      <div className="animate-in fade-in slide-in-from-top-2 bg-slate-50 p-5 rounded-xl border border-slate-200 mt-6">
                        <h4 className="font-semibold text-slate-900 mb-4">Secure Contact Details</h4>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                          <div>
                            <Label>Phone Number</Label>
                            <Input 
                              placeholder="+91 98765 43210" 
                              value={formData.contactPhone}
                              onChange={(e) => handleInputChange('contactPhone', e.target.value)}
                            />
                          </div>
                          <div>
                            <Label>Email Address</Label>
                            <Input 
                              type="email"
                              placeholder="secure@example.com" 
                              value={formData.contactEmail}
                              onChange={(e) => handleInputChange('contactEmail', e.target.value)}
                            />
                          </div>
                        </div>
                        {errors.contact && <p className="mt-3 text-sm text-rose-500 flex items-center gap-1"><AlertTriangle className="w-4 h-4"/> {errors.contact}</p>}
                      </div>
                    )}

                  </div>

                  <div className="mt-8 pt-6 border-t border-slate-100 flex justify-between">
                    <Button variant="outline" onClick={prevStep}>Back</Button>
                    <Button onClick={nextStep}>Review Report</Button>
                  </div>
                </div>
              )}

              {/* STEP 6: Review & Submit */}
              {currentStep === 6 && (
                <div className="animate-in fade-in duration-500 flex-grow flex flex-col">
                  
                  {aiAnalyzing ? (
                    <div className="flex flex-col items-center justify-center h-full py-20">
                      <div className="relative w-24 h-24 mb-8">
                        <div className="absolute inset-0 border-4 border-slate-100 rounded-full"></div>
                        <div className="absolute inset-0 border-4 border-emerald-500 rounded-full border-t-transparent animate-spin"></div>
                        <div className="absolute inset-0 flex items-center justify-center text-emerald-600">
                          <Cpu className="w-8 h-8" />
                        </div>
                      </div>
                      <h3 className="text-xl font-display font-bold text-slate-900 mb-2">AI Pre-Check in Progress</h3>
                      <p className="text-slate-500 text-center max-w-md">
                        Our predictive AI is analyzing your report for completeness, categorizing entities, and generating a cryptographic hash for the blockchain ledger...
                      </p>
                    </div>
                  ) : (
                    <>
                      <div className="flex items-center justify-between mb-6">
                        <div>
                          <h2 className="text-2xl font-display font-bold text-slate-900">Review & Submit</h2>
                          <p className="text-slate-500">Please verify the details before final submission.</p>
                        </div>
                        <Badge variant="primary" className="px-3 py-1 text-sm gap-1">
                          <ShieldCheck className="w-4 h-4" /> AI Verified
                        </Badge>
                      </div>

                      <div className="space-y-6 flex-grow">
                        
                        {/* Summary Card */}
                        <div className="bg-slate-50 rounded-xl border border-slate-200 p-6">
                          <div className="flex justify-between items-start mb-4 pb-4 border-b border-slate-200">
                            <div>
                              <h3 className="font-bold text-lg text-slate-900">{formData.title}</h3>
                              <div className="flex items-center gap-4 mt-2 text-sm text-slate-600">
                                <span className="flex items-center gap-1"><Building className="w-4 h-4"/> {selectedCategory?.name}</span>
                                <span className="flex items-center gap-1"><MapPin className="w-4 h-4"/> {formData.district}</span>
                                <span className="flex items-center gap-1"><Calendar className="w-4 h-4"/> {formData.date}</span>
                              </div>
                            </div>
                            <Button variant="ghost" size="sm" onClick={() => setCurrentStep(3)}>Edit</Button>
                          </div>
                          
                          <div className="mb-4">
                            <h4 className="text-sm font-semibold text-slate-900 mb-2">Description</h4>
                            <p className="text-sm text-slate-600 whitespace-pre-wrap">{formData.description}</p>
                          </div>

                          <div className="flex justify-between items-start pt-4 border-t border-slate-200">
                            <div>
                              <h4 className="text-sm font-semibold text-slate-900 mb-2">Evidence Attached</h4>
                              {formData.files.length > 0 ? (
                                <ul className="text-sm text-slate-600 space-y-1">
                                  {formData.files.map(f => <li key={f.id} className="flex items-center gap-2"><FileText className="w-3 h-3"/> {f.name}</li>)}
                                </ul>
                              ) : (
                                <span className="text-sm text-slate-500 italic">No files attached</span>
                              )}
                            </div>
                            <div className="text-right">
                              <h4 className="text-sm font-semibold text-slate-900 mb-2">Identity</h4>
                              <Badge variant={formData.isAnonymous ? "default" : "warning"}>
                                {formData.isAnonymous ? "Anonymous" : "Identified"}
                              </Badge>
                            </div>
                          </div>
                        </div>

                        {/* AI Analysis Results */}
                        <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-5">
                          <h4 className="flex items-center gap-2 text-emerald-800 font-semibold mb-3">
                            <Cpu className="w-5 h-5" /> AI Pre-Check Results
                          </h4>
                          <ul className="space-y-2 text-sm text-emerald-700">
                            <li className="flex items-start gap-2">
                              <CheckCircle className="w-4 h-4 mt-0.5 shrink-0" />
                              Description contains sufficient detail for investigation.
                            </li>
                            <li className="flex items-start gap-2">
                              <CheckCircle className="w-4 h-4 mt-0.5 shrink-0" />
                              Category matches extracted keywords (Bribe, Permit).
                            </li>
                            <li className="flex items-start gap-2">
                              <CheckCircle className="w-4 h-4 mt-0.5 shrink-0" />
                              Evidence files scanned and verified safe.
                            </li>
                          </ul>
                        </div>

                      </div>

                      <div className="mt-8 pt-6 border-t border-slate-100 flex justify-between items-center">
                        <Button variant="outline" onClick={prevStep} disabled={isSubmitting}>Back</Button>
                        <Button 
                          onClick={handleSubmit} 
                          size="lg" 
                          disabled={isSubmitting}
                          className="min-w-[200px]"
                        >
                          {isSubmitting ? (
                            <span className="flex items-center gap-2">
                              <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                              Encrypting & Submitting...
                            </span>
                          ) : (
                            <span className="flex items-center gap-2">
                              <Lock className="w-5 h-5" /> Submit Securely
                            </span>
                          )}
                        </Button>
                      </div>
                    </>
                  )}
                </div>
              )}

              {/* STEP 7: Success */}
              {currentStep === 7 && (
                <div className="animate-in zoom-in-95 duration-500 flex flex-col items-center justify-center text-center py-12 flex-grow">
                  <div className="w-20 h-20 bg-emerald-100 rounded-full flex items-center justify-center mb-6">
                    <CheckCircle className="w-10 h-10 text-emerald-600" />
                  </div>
                  <h2 className="text-3xl font-display font-bold text-slate-900 mb-4">Report Submitted Successfully</h2>
                  <p className="text-slate-600 max-w-md mb-8">
                    Your report has been encrypted, hashed to the blockchain, and assigned to the Vigilance Anti-Corruption Bureau. 
                  </p>

                  <div className="bg-slate-50 border border-slate-200 rounded-xl p-6 w-full max-w-md mb-8">
                    <p className="text-sm text-slate-500 font-medium mb-2 uppercase tracking-wider">Your Secure Tracking ID</p>
                    <div className="flex items-center justify-between bg-white border border-slate-300 rounded-lg p-3">
                      <code className="text-lg font-mono font-bold text-slate-900">{trackingId}</code>
                      <button 
                        onClick={() => {
                          navigator.clipboard.writeText(trackingId);
                          alert('Tracking ID copied to clipboard!');
                        }}
                        className="p-2 text-slate-400 hover:text-emerald-600 transition-colors"
                        title="Copy ID"
                      >
                        <Copy className="w-5 h-5" />
                      </button>
                    </div>
                    {formData.isAnonymous && (
                      <div className="mt-4 flex items-start gap-2 text-left text-amber-700 bg-amber-50 p-3 rounded-lg text-sm">
                        <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" />
                        <p>Save this ID immediately. Because you reported anonymously, this is the <strong>only</strong> way to track your case or communicate with investigators.</p>
                      </div>
                    )}
                  </div>

                  <div className="flex gap-4">
                    <Button variant="outline" onClick={() => window.print()}>
                      Print Receipt
                    </Button>
                    <Button onClick={() => navigate('/dashboard')}>
                      Go to Dashboard
                    </Button>
                  </div>
                </div>
              )}

            </Card>
          </div>

          {/* Contextual Sidebar */}
          <div className="hidden lg:block space-y-6">
            
            {/* Dynamic Info Card based on step */}
            <Card className="p-6 bg-slate-900 text-white border-slate-800">
              {currentStep === 1 && (
                <>
                  <Shield className="w-8 h-8 text-emerald-400 mb-4" />
                  <h3 className="text-lg font-bold mb-2">Whistleblower Protection</h3>
                  <p className="text-slate-300 text-sm leading-relaxed">
                    Under the Whistleblowers Protection Act, your identity is strictly guarded. The C3MS system uses Zero-Knowledge Proofs, meaning even system administrators cannot link your report to your IP address or device.
                  </p>
                </>
              )}
              {currentStep === 2 && (
                <>
                  <Building className="w-8 h-8 text-emerald-400 mb-4" />
                  <h3 className="text-lg font-bold mb-2">Why Category Matters</h3>
                  <p className="text-slate-300 text-sm leading-relaxed">
                    Selecting the correct department ensures your report is instantly routed to the specialized investigating unit. Our AI will cross-reference historical data for this specific department to flag systemic issues.
                  </p>
                </>
              )}
              {currentStep === 3 && (
                <>
                  <FileText className="w-8 h-8 text-emerald-400 mb-4" />
                  <h3 className="text-lg font-bold mb-2">Detail is Key</h3>
                  <p className="text-slate-300 text-sm leading-relaxed">
                    Vague reports are difficult to investigate. Mentioning specific dates, times, and office locations allows investigators to pull CCTV footage and verify attendance records before evidence can be tampered with.
                  </p>
                </>
              )}
              {currentStep === 4 && (
                <>
                  <Fingerprint className="w-8 h-8 text-emerald-400 mb-4" />
                  <h3 className="text-lg font-bold mb-2">Immutable Evidence</h3>
                  <p className="text-slate-300 text-sm leading-relaxed">
                    Every file you upload is cryptographically hashed (SHA-256) and logged on a blockchain ledger. This creates an unbreakable chain of custody, proving the evidence existed at this exact moment and hasn't been altered.
                  </p>
                </>
              )}
              {currentStep === 5 && (
                <>
                  <Lock className="w-8 h-8 text-emerald-400 mb-4" />
                  <h3 className="text-lg font-bold mb-2">Zero-Knowledge Architecture</h3>
                  <p className="text-slate-300 text-sm leading-relaxed">
                    If you choose Anonymous, the system generates a cryptographic token. You hold the key (Tracking ID), and the server holds the lock. We can verify you own the report without ever knowing who you are.
                  </p>
                </>
              )}
              {(currentStep === 6 || currentStep === 7) && (
                <>
                  <Cpu className="w-8 h-8 text-emerald-400 mb-4" />
                  <h3 className="text-lg font-bold mb-2">AI Predictive Analysis</h3>
                  <p className="text-slate-300 text-sm leading-relaxed">
                    Your report is now part of the C3MS neural network. It will be cross-referenced with thousands of other reports to detect organized syndicates and recurring patterns of corruption across the state.
                  </p>
                </>
              )}
            </Card>

            {/* Static Trust Indicators */}
            <Card className="p-6">
              <h4 className="text-sm font-bold text-slate-900 uppercase tracking-wider mb-4">System Integrity</h4>
              <ul className="space-y-4">
                <li className="flex items-start gap-3">
                  <div className="p-1.5 bg-emerald-100 text-emerald-600 rounded-md mt-0.5">
                    <Lock className="w-4 h-4" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-slate-900">AES-256 Encryption</p>
                    <p className="text-xs text-slate-500">Military-grade data protection at rest and in transit.</p>
                  </div>
                </li>
                <li className="flex items-start gap-3">
                  <div className="p-1.5 bg-emerald-100 text-emerald-600 rounded-md mt-0.5">
                    <ShieldCheck className="w-4 h-4" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-slate-900">Govt. Audited</p>
                    <p className="text-xs text-slate-500">Certified by the State Cyber Security Nodal Agency.</p>
                  </div>
                </li>
              </ul>
            </Card>

          </div>
        </div>
      </div>

      {/* FAQ Section at the bottom for extra context */}
      <div className="bg-slate-50 border-t border-slate-200 py-16">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-10">
            <h2 className="text-2xl font-display font-bold text-slate-900">Frequently Asked Questions</h2>
            <p className="text-slate-500 mt-2">Common concerns about filing a report.</p>
          </div>
          
          <div className="space-y-4">
            {[
              { q: "Can my IP address be tracked if I report anonymously?", a: "No. The C3MS platform strips all metadata, including IP addresses, browser fingerprints, and device IDs before the report reaches our main servers. We use a secure proxy layer to ensure absolute anonymity." },
              { q: "What happens after I submit?", a: "Your report is first analyzed by our AI to assess credibility and extract key entities. It is then assigned to a specialized investigating officer. You can use your Tracking ID to view status updates, such as 'Investigation Initiated' or 'Action Taken'." },
              { q: "Can I add more evidence later?", a: "Yes. Using your Tracking ID, you can log into the secure portal at any time to upload additional documents or respond to anonymous queries from the investigating officer." }
            ].map((faq, i) => (
              <div key={i} className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
                <h4 className="font-semibold text-slate-900 flex items-start gap-2">
                  <HelpCircle className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5" />
                  {faq.q}
                </h4>
                <p className="text-slate-600 text-sm mt-2 ml-7 leading-relaxed">{faq.a}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </AppShell>
  );
}
