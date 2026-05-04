import { useState, useEffect } from 'react'
import { departments } from '../../mockData'
import { Check, ChevronRight, Upload, BrainCircuit, ShieldCheck } from 'lucide-react'
import { Building, FileText, MapPin, Calendar, Lock, AlertTriangle, File, X, Loader2, Info, ArrowLeft, Shield, HardHat, Car, Activity, ShoppingCart, BookOpen, TreePine, Wine } from 'lucide-react'

// Fallback data in case departments is not exported exactly as named in mockData
const fallbackDepartments = [
  { id: 'cat-1', name: 'Public Works (PWD)', icon: 'HardHat', color: '#D97706' },
  { id: 'cat-2', name: 'Revenue Department', icon: 'FileText', color: '#059669' },
  { id: 'cat-3', name: 'Local Self Govt (LSGD)', icon: 'Building', color: '#2563EB' },
  { id: 'cat-4', name: 'Motor Vehicles (MVD)', icon: 'Car', color: '#DC2626' },
  { id: 'cat-5', name: 'Health Services', icon: 'Activity', color: '#0D9488' },
  { id: 'cat-6', name: 'Kerala Police', icon: 'Shield', color: '#4F46E5' },
  { id: 'cat-7', name: 'Civil Supplies', icon: 'ShoppingCart', color: '#EA580C' },
  { id: 'cat-8', name: 'Education Dept', icon: 'BookOpen', color: '#7C3AED' },
  { id: 'cat-9', name: 'Forest Department', icon: 'TreePine', color: '#16A34A' },
  { id: 'cat-10', name: 'Excise Department', icon: 'Wine', color: '#BE123C' }
];

const iconMap = {
  HardHat, FileText, Building, Car, Activity, Shield, ShoppingCart, BookOpen, TreePine, Wine
};

const STEPS = [
  { id: 0, title: 'Category', description: 'Select department' },
  { id: 1, title: 'Details', description: 'Incident information' },
  { id: 2, title: 'Evidence', description: 'Upload files' },
  { id: 3, title: 'AI Analysis', description: 'Credibility check' },
  { id: 4, title: 'Review', description: 'Submit securely' }
];

export default function WorkflowStepper() {
  const [currentStep, setCurrentStep] = useState(0);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [trackingId, setTrackingId] = useState('');
  
  const [formData, setFormData] = useState({
    department: '',
    subject: '',
    description: '',
    location: '',
    incidentDate: '',
    isAnonymous: true,
    files: []
  });

  const activeDepartments = departments || fallbackDepartments;

  const handleNext = () => {
    if (currentStep === 2) {
      // Moving to AI Analysis step
      setCurrentStep(3);
      setIsAnalyzing(true);
      setTimeout(() => {
        setIsAnalyzing(false);
      }, 2500);
    } else if (currentStep < 5) {
      setCurrentStep(prev => prev + 1);
    }
  };

  const handleBack = () => {
    if (currentStep > 0) {
      setCurrentStep(prev => prev - 1);
    }
  };

  const handleFileUpload = (e) => {
    const newFiles = Array.from(e.target.files).map(file => ({
      name: file.name,
      size: (file.size / 1024 / 1024).toFixed(2) + ' MB',
      type: file.type
    }));
    setFormData(prev => ({ ...prev, files: [...prev.files, ...newFiles] }));
  };

  const removeFile = (indexToRemove) => {
    setFormData(prev => ({
      ...prev,
      files: prev.files.filter((_, index) => index !== indexToRemove)
    }));
  };

  const handleSubmit = () => {
    // Simulate API call and submission
    const newTrackingId = `C3MS-${Math.floor(100000 + Math.random() * 900000)}`;
    setTrackingId(newTrackingId);
    setCurrentStep(5); // Success screen
  };

  const renderStepIndicator = () => {
    if (currentStep === 5) return null; // Hide on success

    return (
      <div className="mb-10">
        <div className="flex items-center justify-between relative">
          <div className="absolute left-0 top-1/2 transform -translate-y-1/2 w-full h-1 bg-secondary z-0 rounded-full"></div>
          <div 
            className="absolute left-0 top-1/2 transform -translate-y-1/2 h-1 bg-primary z-0 rounded-full transition-all duration-500 ease-in-out"
            style={{ width: `${(currentStep / (STEPS.length - 1)) * 100}%` }}
          ></div>
          
          {STEPS.map((step, index) => {
            const isActive = index === currentStep;
            const isCompleted = index < currentStep;
            
            return (
              <div key={step.id} className="relative z-10 flex flex-col items-center">
                <div 
                  className={`w-10 h-10 rounded-full flex items-center justify-center border-2 font-display font-semibold transition-colors duration-300 ${
                    isActive 
                      ? 'bg-primary border-primary text-white shadow-md shadow-primary/30' 
                      : isCompleted 
                        ? 'bg-primary border-primary text-white' 
                        : 'bg-card border-border text-muted-foreground'
                  }`}
                >
                  {isCompleted ? <Check className="w-5 h-5" /> : step.id + 1}
                </div>
                <div className="absolute top-12 text-center w-32 -ml-11">
                  <p className={`text-sm font-semibold font-display ${isActive ? 'text-foreground' : 'text-muted-foreground'}`}>
                    {step.title}
                  </p>
                  <p className="text-xs text-muted-foreground hidden md:block mt-0.5 font-body">
                    {step.description}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    );
  };

  const renderCategorySelection = () => (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="text-center mb-8">
        <h2 className="text-2xl font-display font-bold text-foreground">Select Department</h2>
        <p className="text-muted-foreground font-body mt-2">Which government department is this complaint regarding?</p>
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {activeDepartments.map((dept) => {
          const IconComponent = iconMap[dept.icon] || Building;
          const isSelected = formData.department === dept.name;
          
          return (
            <button
              key={dept.id}
              onClick={() => {
                setFormData(prev => ({ ...prev, department: dept.name }));
                setTimeout(handleNext, 300);
              }}
              className={`flex flex-col items-center justify-center p-6 rounded-xl border-2 transition-all duration-200 ${
                isSelected 
                  ? 'border-primary bg-primary/5 shadow-sm' 
                  : 'border-border bg-card hover:border-primary/40 hover:bg-secondary/30'
              }`}
            >
              <div 
                className="w-14 h-14 rounded-full flex items-center justify-center mb-4"
                style={{ backgroundColor: `${dept.color}15`, color: dept.color }}
              >
                <IconComponent className="w-7 h-7" />
              </div>
              <h3 className="font-display font-semibold text-foreground text-center">{dept.name}</h3>
            </button>
          );
        })}
      </div>
    </div>
  );

  const renderDetailsInput = () => (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="mb-6">
        <h2 className="text-2xl font-display font-bold text-foreground">Incident Details</h2>
        <p className="text-muted-foreground font-body mt-2">Provide clear and factual information about the incident.</p>
      </div>

      <div className="space-y-5">
        <div>
          <label className="block text-sm font-semibold text-foreground mb-1.5 font-body">Subject / Title</label>
          <input 
            type="text" 
            value={formData.subject}
            onChange={(e) => setFormData({...formData, subject: e.target.value})}
            placeholder="e.g., Bribery request for building permit"
            className="w-full bg-background border border-border rounded-lg p-3 text-foreground font-body focus:ring-2 focus:ring-primary/50 focus:border-primary outline-none transition-all"
          />
        </div>

        <div>
          <label className="block text-sm font-semibold text-foreground mb-1.5 font-body">Detailed Description</label>
          <textarea 
            value={formData.description}
            onChange={(e) => setFormData({...formData, description: e.target.value})}
            placeholder="Describe what happened, who was involved, and any specific demands made..."
            rows={5}
            className="w-full bg-background border border-border rounded-lg p-3 text-foreground font-body focus:ring-2 focus:ring-primary/50 focus:border-primary outline-none transition-all resize-none"
          />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          <div>
            <label className="block text-sm font-semibold text-foreground mb-1.5 font-body">Location (Office/City)</label>
            <div className="relative">
              <MapPin className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
              <input 
                type="text" 
                value={formData.location}
                onChange={(e) => setFormData({...formData, location: e.target.value})}
                placeholder="e.g., Village Office, Kochi"
                className="w-full bg-background border border-border rounded-lg py-3 pl-10 pr-3 text-foreground font-body focus:ring-2 focus:ring-primary/50 focus:border-primary outline-none transition-all"
              />
            </div>
          </div>
          <div>
            <label className="block text-sm font-semibold text-foreground mb-1.5 font-body">Date of Incident</label>
            <div className="relative">
              <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
              <input 
                type="date" 
                value={formData.incidentDate}
                onChange={(e) => setFormData({...formData, incidentDate: e.target.value})}
                className="w-full bg-background border border-border rounded-lg py-3 pl-10 pr-3 text-foreground font-body focus:ring-2 focus:ring-primary/50 focus:border-primary outline-none transition-all"
              />
            </div>
          </div>
        </div>

        <div className="bg-secondary/40 border border-border rounded-lg p-4 flex items-start gap-4 mt-4">
          <div className="bg-background p-2 rounded-full shadow-sm border border-border shrink-0">
            <Lock className="w-5 h-5 text-primary" />
          </div>
          <div className="flex-1">
            <h4 className="font-display font-semibold text-foreground">Anonymous Reporting</h4>
            <p className="text-sm text-muted-foreground font-body mt-1">
              Your identity will be encrypted and hidden from investigating officers unless you choose to reveal it later.
            </p>
          </div>
          <label className="relative inline-flex items-center cursor-pointer mt-2">
            <input 
              type="checkbox" 
              className="sr-only peer" 
              checked={formData.isAnonymous}
              onChange={(e) => setFormData({...formData, isAnonymous: e.target.checked})}
            />
            <div className="w-11 h-6 bg-muted rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary"></div>
          </label>
        </div>
      </div>

      <div className="flex justify-between pt-6 border-t border-border mt-8">
        <button 
          onClick={handleBack}
          className="px-6 py-2.5 rounded-lg font-semibold font-body text-foreground bg-secondary hover:bg-secondary/80 transition-colors flex items-center gap-2"
        >
          <ArrowLeft className="w-4 h-4" /> Back
        </button>
        <button 
          onClick={handleNext}
          disabled={!formData.subject || !formData.description}
          className="px-6 py-2.5 rounded-lg font-semibold font-body text-white bg-primary hover:bg-primary/90 transition-colors flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Continue <ChevronRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  );

  const renderEvidenceUpload = () => (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="mb-6">
        <h2 className="text-2xl font-display font-bold text-foreground">Upload Evidence</h2>
        <p className="text-muted-foreground font-body mt-2">Attach documents, audio recordings, or images to support your claim. Max 50MB total.</p>
      </div>

      <div className="border-2 border-dashed border-border rounded-xl p-10 flex flex-col items-center justify-center bg-secondary/20 hover:bg-secondary/40 transition-colors relative group">
        <input 
          type="file" 
          multiple 
          onChange={handleFileUpload}
          className="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-10"
        />
        <div className="bg-background p-4 rounded-full shadow-sm border border-border mb-4 group-hover:scale-110 transition-transform">
          <Upload className="w-8 h-8 text-primary" />
        </div>
        <h3 className="font-display font-semibold text-foreground text-lg">Drag & drop files here</h3>
        <p className="text-muted-foreground font-body text-sm mt-1">or click to browse from your device</p>
        <div className="flex gap-2 mt-4">
          <span className="text-xs font-semibold bg-background border border-border px-2 py-1 rounded text-muted-foreground">PDF</span>
          <span className="text-xs font-semibold bg-background border border-border px-2 py-1 rounded text-muted-foreground">JPG/PNG</span>
          <span className="text-xs font-semibold bg-background border border-border px-2 py-1 rounded text-muted-foreground">MP3/MP4</span>
        </div>
      </div>

      {formData.files.length > 0 && (
        <div className="space-y-3 mt-6">
          <h4 className="font-display font-semibold text-foreground text-sm">Attached Files ({formData.files.length})</h4>
          {formData.files.map((file, index) => (
            <div key={index} className="flex items-center justify-between p-3 bg-background border border-border rounded-lg shadow-sm">
              <div className="flex items-center gap-3">
                <File className="w-5 h-5 text-primary" />
                <div>
                  <p className="font-body font-medium text-sm text-foreground">{file.name}</p>
                  <p className="font-body text-xs text-muted-foreground">{file.size}</p>
                </div>
              </div>
              <button 
                onClick={() => removeFile(index)}
                className="p-2 hover:bg-secondary rounded-md text-muted-foreground hover:text-destructive transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="flex justify-between pt-6 border-t border-border mt-8">
        <button 
          onClick={handleBack}
          className="px-6 py-2.5 rounded-lg font-semibold font-body text-foreground bg-secondary hover:bg-secondary/80 transition-colors flex items-center gap-2"
        >
          <ArrowLeft className="w-4 h-4" /> Back
        </button>
        <button 
          onClick={handleNext}
          className="px-6 py-2.5 rounded-lg font-semibold font-body text-white bg-primary hover:bg-primary/90 transition-colors flex items-center gap-2"
        >
          Analyze Evidence <ChevronRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  );

  const renderAIPreview = () => (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="mb-6">
        <h2 className="text-2xl font-display font-bold text-foreground">AI Credibility Analysis</h2>
        <p className="text-muted-foreground font-body mt-2">Our system is reviewing your submission to prioritize and route it effectively.</p>
      </div>

      {isAnalyzing ? (
        <div className="flex flex-col items-center justify-center py-16 space-y-6">
          <div className="relative">
            <div className="absolute inset-0 bg-primary/20 rounded-full blur-xl animate-pulse"></div>
            <BrainCircuit className="w-16 h-16 text-primary animate-bounce relative z-10" />
          </div>
          <div className="text-center space-y-2">
            <h3 className="font-display font-semibold text-xl text-foreground flex items-center justify-center gap-2">
              <Loader2 className="w-5 h-5 animate-spin text-primary" />
              Analyzing Submission...
            </h3>
            <p className="text-muted-foreground font-body text-sm">Cross-referencing entities and evaluating evidence quality.</p>
          </div>
        </div>
      ) : (
        <div className="bg-slate-900 rounded-xl p-6 border border-slate-800 text-slate-100 shadow-lg relative overflow-hidden">
          {/* Decorative background elements */}
          <div className="absolute top-0 right-0 w-64 h-64 bg-emerald-500/10 rounded-full blur-3xl -mr-20 -mt-20 pointer-events-none"></div>
          
          <div className="flex items-center gap-3 mb-6 relative z-10">
            <div className="bg-emerald-500/20 p-2 rounded-lg border border-emerald-500/30">
              <BrainCircuit className="text-emerald-400 w-6 h-6" />
            </div>
            <div>
              <h3 className="font-display text-xl font-semibold text-white">Analysis Complete</h3>
              <p className="text-slate-400 text-sm font-body">Automated preliminary assessment</p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6 relative z-10">
            <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4">
              <p className="text-slate-400 text-xs font-semibold uppercase tracking-wider mb-1">Credibility Score</p>
              <div className="flex items-end gap-2">
                <span className="text-3xl font-display font-bold text-emerald-400">88%</span>
                <span className="text-sm text-slate-300 mb-1">High</span>
              </div>
            </div>
            <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4">
              <p className="text-slate-400 text-xs font-semibold uppercase tracking-wider mb-1">Priority Level</p>
              <div className="flex items-end gap-2">
                <span className="text-3xl font-display font-bold text-amber-400">P2</span>
                <span className="text-sm text-slate-300 mb-1">Elevated</span>
              </div>
            </div>
            <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4">
              <p className="text-slate-400 text-xs font-semibold uppercase tracking-wider mb-1">Evidence Quality</p>
              <div className="flex items-end gap-2">
                <span className="text-3xl font-display font-bold text-blue-400">Good</span>
                <span className="text-sm text-slate-300 mb-1">{formData.files.length} files</span>
              </div>
            </div>
          </div>

          <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4 relative z-10">
            <p className="text-slate-400 text-xs font-semibold uppercase tracking-wider mb-3">Extracted Entities</p>
            <div className="flex flex-wrap gap-2">
              <span className="px-3 py-1 bg-slate-700 text-slate-200 rounded-full text-xs font-medium border border-slate-600">
                Dept: {formData.department || 'Unknown'}
              </span>
              {formData.location && (
                <span className="px-3 py-1 bg-slate-700 text-slate-200 rounded-full text-xs font-medium border border-slate-600">
                  Loc: {formData.location}
                </span>
              )}
              <span className="px-3 py-1 bg-emerald-900/50 text-emerald-300 rounded-full text-xs font-medium border border-emerald-800/50 flex items-center gap-1">
                <Check className="w-3 h-3" /> Verified Format
              </span>
            </div>
          </div>
          
          <div className="mt-4 flex items-start gap-2 text-slate-400 text-xs font-body relative z-10">
            <Info className="w-4 h-4 shrink-0 mt-0.5" />
            <p>This is an automated preliminary analysis to assist investigators. It does not represent a final judgment on the case.</p>
          </div>
        </div>
      )}

      <div className="flex justify-between pt-6 border-t border-border mt-8">
        <button 
          onClick={handleBack}
          disabled={isAnalyzing}
          className="px-6 py-2.5 rounded-lg font-semibold font-body text-foreground bg-secondary hover:bg-secondary/80 transition-colors flex items-center gap-2 disabled:opacity-50"
        >
          <ArrowLeft className="w-4 h-4" /> Back
        </button>
        <button 
          onClick={handleNext}
          disabled={isAnalyzing}
          className="px-6 py-2.5 rounded-lg font-semibold font-body text-white bg-primary hover:bg-primary/90 transition-colors flex items-center gap-2 disabled:opacity-50"
        >
          Proceed to Review <ChevronRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  );

  const renderReviewSubmit = () => (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="mb-6">
        <h2 className="text-2xl font-display font-bold text-foreground">Review & Submit</h2>
        <p className="text-muted-foreground font-body mt-2">Please verify the details before final submission. This action will generate a secure blockchain hash.</p>
      </div>

      <div className="bg-card border border-border rounded-xl overflow-hidden shadow-sm">
        <div className="bg-secondary/50 px-6 py-4 border-b border-border flex justify-between items-center">
          <h3 className="font-display font-semibold text-foreground">Complaint Summary</h3>
          {formData.isAnonymous && (
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-primary/10 text-primary border border-primary/20">
              <Lock className="w-3 h-3" /> Anonymous Mode Active
            </span>
          )}
        </div>
        
        <div className="p-6 space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <p className="text-sm text-muted-foreground font-body mb-1">Department</p>
              <p className="font-medium text-foreground font-body">{formData.department}</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground font-body mb-1">Subject</p>
              <p className="font-medium text-foreground font-body">{formData.subject}</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground font-body mb-1">Location</p>
              <p className="font-medium text-foreground font-body">{formData.location || 'Not specified'}</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground font-body mb-1">Incident Date</p>
              <p className="font-medium text-foreground font-body">{formData.incidentDate || 'Not specified'}</p>
            </div>
          </div>

          <div>
            <p className="text-sm text-muted-foreground font-body mb-1">Description</p>
            <p className="font-medium text-foreground font-body bg-secondary/30 p-3 rounded-lg text-sm leading-relaxed">
              {formData.description}
            </p>
          </div>

          <div>
            <p className="text-sm text-muted-foreground font-body mb-2">Evidence Attached ({formData.files.length})</p>
            {formData.files.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {formData.files.map((f, i) => (
                  <span key={i} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium bg-background border border-border text-foreground">
                    <File className="w-3.5 h-3.5 text-muted-foreground" /> {f.name}
                  </span>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground italic">No files attached.</p>
            )}
          </div>
        </div>
      </div>

      <div className="bg-amber-500/10 border border-amber-500/20 rounded-lg p-4 flex items-start gap-3">
        <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
        <div>
          <h4 className="font-display font-semibold text-amber-800 dark:text-amber-500">Legal Declaration</h4>
          <p className="text-sm text-amber-700/80 dark:text-amber-400/80 font-body mt-1">
            By submitting this form, you declare that the information provided is true to the best of your knowledge. False reporting may lead to legal consequences.
          </p>
        </div>
      </div>

      <div className="flex justify-between pt-6 border-t border-border mt-8">
        <button 
          onClick={handleBack}
          className="px-6 py-2.5 rounded-lg font-semibold font-body text-foreground bg-secondary hover:bg-secondary/80 transition-colors flex items-center gap-2"
        >
          <ArrowLeft className="w-4 h-4" /> Edit Details
        </button>
        <button 
          onClick={handleSubmit}
          className="px-8 py-2.5 rounded-lg font-semibold font-body text-white bg-primary hover:bg-primary/90 transition-colors flex items-center gap-2 shadow-lg shadow-primary/20"
        >
          <ShieldCheck className="w-5 h-5" /> Submit Securely
        </button>
      </div>
    </div>
  );

  const renderSuccess = () => (
    <div className="py-12 flex flex-col items-center text-center animate-in zoom-in-95 duration-500">
      <div className="w-24 h-24 bg-primary/10 rounded-full flex items-center justify-center mb-6 relative">
        <div className="absolute inset-0 bg-primary/20 rounded-full animate-ping opacity-75"></div>
        <Check className="w-12 h-12 text-primary relative z-10" />
      </div>
      
      <h2 className="text-3xl font-display font-bold text-foreground mb-2">Report Submitted Successfully</h2>
      <p className="text-muted-foreground font-body max-w-md mb-8">
        Your complaint has been securely recorded on the blockchain and routed to the appropriate vigilance officer.
      </p>

      <div className="bg-secondary/50 border border-border rounded-xl p-6 w-full max-w-sm mb-8">
        <p className="text-sm text-muted-foreground font-body uppercase tracking-wider font-semibold mb-2">Your Tracking ID</p>
        <div className="text-2xl font-display font-bold text-foreground tracking-widest bg-background py-3 rounded-lg border border-border shadow-inner">
          {trackingId}
        </div>
        <p className="text-xs text-muted-foreground mt-3 font-body">
          Please save this ID. You will need it to track the status of your complaint anonymously.
        </p>
      </div>

      <div className="flex gap-4">
        <button 
          onClick={() => window.location.reload()}
          className="px-6 py-2.5 rounded-lg font-semibold font-body text-foreground bg-secondary hover:bg-secondary/80 transition-colors"
        >
          File Another Report
        </button>
        <button 
          className="px-6 py-2.5 rounded-lg font-semibold font-body text-white bg-primary hover:bg-primary/90 transition-colors shadow-lg shadow-primary/20"
        >
          Track Status
        </button>
      </div>
    </div>
  );

  const renderStepContent = () => {
    switch (currentStep) {
      case 0: return renderCategorySelection();
      case 1: return renderDetailsInput();
      case 2: return renderEvidenceUpload();
      case 3: return renderAIPreview();
      case 4: return renderReviewSubmit();
      case 5: return renderSuccess();
      default: return null;
    }
  };

  return (
    <div className="w-full max-w-4xl mx-auto bg-card rounded-2xl shadow-sm border border-border p-6 md:p-10">
      {renderStepIndicator()}
      <div className="mt-4">
        {renderStepContent()}
      </div>
    </div>
  );
}