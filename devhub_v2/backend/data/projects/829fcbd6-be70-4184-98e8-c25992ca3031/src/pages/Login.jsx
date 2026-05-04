import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { 
  ShieldCheck, 
  Shield, 
  Menu, 
  X, 
  Lock, 
  Mail, 
  Smartphone, 
  ArrowRight, 
  Fingerprint, 
  Eye, 
  EyeOff, 
  AlertCircle,
  CheckCircle2,
  ChevronRight,
  Building,
  FileText,
  Activity,
  Car,
  Loader2
} from 'lucide-react';

// Exact imports requested by the contract
import MinimalNavbar from '../components/layout/MinimalNavbar';
import SplitAuthLayout from '../components/auth/SplitAuthLayout';
import LoginForm from '../components/auth/LoginForm';
import MinimalFooter from '../components/layout/MinimalFooter';

// ============================================================================
// INLINE UI PRIMITIVES
// Built inline to ensure the page is 100% self-contained while maintaining
// a high-quality, consistent design system.
// ============================================================================

const Button = ({ children, variant = 'primary', size = 'default', className = '', isLoading, icon: Icon, ...props }) => {
  const baseStyle = "inline-flex items-center justify-center rounded-lg font-medium transition-all focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:opacity-60 disabled:cursor-not-allowed font-body";
  
  const variants = {
    primary: "bg-[#059669] text-white hover:bg-[#047857] focus:ring-[#059669] shadow-sm",
    secondary: "bg-slate-800 text-white hover:bg-slate-700 focus:ring-slate-800 shadow-sm",
    outline: "border-2 border-slate-200 bg-transparent text-slate-700 hover:border-[#059669] hover:text-[#059669] focus:ring-[#059669]",
    ghost: "bg-transparent text-slate-600 hover:bg-slate-100 hover:text-slate-900 focus:ring-slate-200",
    epramaan: "bg-gradient-to-r from-blue-600 to-indigo-700 text-white hover:from-blue-700 hover:to-indigo-800 focus:ring-blue-600 shadow-md"
  };

  const sizes = {
    sm: "px-3 py-1.5 text-sm",
    default: "px-4 py-2.5 text-sm",
    lg: "px-6 py-3 text-base",
    icon: "p-2"
  };

  return (
    <button 
      className={`${baseStyle} ${variants[variant]} ${sizes[size]} ${className}`}
      disabled={isLoading || props.disabled}
      {...props}
    >
      {isLoading ? (
        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
      ) : Icon ? (
        <Icon className="w-4 h-4 mr-2" />
      ) : null}
      {children}
    </button>
  );
};

const Input = ({ label, id, error, icon: Icon, ...props }) => {
  return (
    <div className="space-y-1.5 w-full">
      {label && (
        <label htmlFor={id} className="block text-sm font-medium text-slate-700 font-body">
          {label}
        </label>
      )}
      <div className="relative">
        {Icon && (
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <Icon className="h-5 w-5 text-slate-400" />
          </div>
        )}
        <input
          id={id}
          className={`block w-full rounded-lg border ${
            error ? 'border-red-300 focus:ring-red-500 focus:border-red-500' : 'border-slate-300 focus:ring-[#059669] focus:border-[#059669]'
          } bg-white px-3 py-2.5 text-slate-900 placeholder-slate-400 shadow-sm focus:outline-none focus:ring-2 sm:text-sm font-body transition-colors ${
            Icon ? 'pl-10' : ''
          }`}
          {...props}
        />
      </div>
      {error && (
        <p className="text-sm text-red-600 flex items-center mt-1 font-body">
          <AlertCircle className="w-4 h-4 mr-1" />
          {error}
        </p>
      )}
    </div>
  );
};

const Card = ({ children, className = '' }) => (
  <div className={`bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden ${className}`}>
    {children}
  </div>
);

const Badge = ({ children, variant = 'default', className = '' }) => {
  const variants = {
    default: "bg-slate-100 text-slate-800 border-slate-200",
    success: "bg-emerald-100 text-emerald-800 border-emerald-200",
    warning: "bg-amber-100 text-amber-800 border-amber-200",
  };
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${variants[variant]} ${className}`}>
      {children}
    </span>
  );
};

// ============================================================================
// MAIN PAGE COMPONENT
// ============================================================================

export default function Login() {
  const navigate = useNavigate();
  
  // Local State for Interactions
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [authMethod, setAuthMethod] = useState('password'); // 'password' | 'otp'
  const [userRole, setUserRole] = useState('citizen'); // 'citizen' | 'official'
  const [showPassword, setShowPassword] = useState(false);
  
  // Form State
  const [formData, setFormData] = useState({
    identifier: '',
    password: '',
    phone: '',
    otp: ''
  });
  const [isLoading, setIsLoading] = useState(false);
  const [formError, setFormError] = useState('');
  const [otpSent, setOtpSent] = useState(false);

  // Wireframe Data
  const wireframeData = {
    navbar: {
      logo: { text: "Vigilance C3MS", icon: ShieldCheck },
      links: [
        { label: "Home", href: "/" },
        { label: "Track Complaint", href: "/track" },
        { label: "Transparency Portal", href: "/transparency" },
        { label: "Help & Support", href: "/support" }
      ],
      cta_primary: { label: "Register as Citizen", href: "/register" }
    },
    hero: {
      headline: "Secure Authentication for Vigilance C3MS Portal",
      sub: "Log in to securely report corruption, track your existing complaints, and access AI-driven transparency dashboards. Your identity and data remain strictly confidential under whistleblower protection protocols.",
      cta_primary: { label: "Authenticate via e-Pramaan", href: "/auth/epramaan" },
      cta_secondary: { label: "Login with Mobile OTP", href: "/auth/otp" },
      image: {
        src: "https://images.unsplash.com/photo-1555949963-aa79dcee981c?w=800&q=80",
        alt: "Abstract representation of secure blockchain data and governance"
      }
    },
    footer: {
      brand: {
        name: "Vigilance C3MS",
        description: "Empowering citizens to securely report, track, and combat corruption with AI-driven transparency across Kerala.",
        logo_icon: Shield
      },
      link_groups: [
        {
          title: "Key Departments",
          links: [
            { label: "Public Works Department (PWD)", href: "/departments/pwd" },
            { label: "Revenue Department", href: "/departments/revenue" },
            { label: "Local Self Government (LSGD)", href: "/departments/lsgd" },
            { label: "Motor Vehicles Department (MVD)", href: "/departments/mvd" }
          ]
        },
        {
          title: "Resources",
          links: [
            { label: "Reporting Guidelines", href: "/guidelines" },
            { label: "Whistleblower Protection", href: "/protection" },
            { label: "Blockchain Audit Trails", href: "/audit-trails" },
            { label: "System Status", href: "/status" }
          ]
        },
        {
          title: "Contact & Support",
          links: [
            { label: "Toll-Free: 1064", href: "tel:1064" },
            { label: "Email: support@vigilance.kerala.gov.in", href: "mailto:support@vigilance.kerala.gov.in" },
            { label: "Directorate of Vigilance", href: "/contact" },
            { label: "Thiruvananthapuram HQ", href: "/locations/tvm" }
          ]
        }
      ],
      legal: {
        text: "© 2024 Vigilance and Anti-Corruption Bureau, Government of Kerala. All rights reserved.",
        links: [
          { label: "Privacy Policy", href: "/privacy" },
          { label: "Terms of Service", href: "/terms" },
          { label: "Accessibility Statement", href: "/accessibility" }
        ]
      }
    }
  };

  // Handlers
  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
    if (formError) setFormError('');
  };

  const handleSendOTP = (e) => {
    e.preventDefault();
    if (!formData.phone || formData.phone.length < 10) {
      setFormError('Please enter a valid 10-digit mobile number.');
      return;
    }
    setIsLoading(true);
    // Simulate API call
    setTimeout(() => {
      setIsLoading(false);
      setOtpSent(true);
      setFormError('');
    }, 1500);
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    setFormError('');

    if (authMethod === 'password') {
      if (!formData.identifier || !formData.password) {
        setFormError('Please enter both email/ID and password.');
        return;
      }
    } else {
      if (!formData.otp || formData.otp.length < 4) {
        setFormError('Please enter the valid OTP sent to your mobile.');
        return;
      }
    }

    setIsLoading(true);
    
    // Simulate authentication and role-based routing
    setTimeout(() => {
      setIsLoading(false);
      if (userRole === 'official' || formData.identifier.includes('admin')) {
        navigate('/dashboard');
      } else {
        navigate('/history');
      }
    }, 2000);
  };

  const handleEpramaanLogin = () => {
    setIsLoading(true);
    setTimeout(() => {
      setIsLoading(false);
      navigate('/dashboard');
    }, 1500);
  };

  return (
    <div className="min-h-screen flex flex-col bg-[#F8FAFC] font-body text-slate-900 selection:bg-[#059669] selection:text-white">
      
      {/* =====================================================================
          SECTION 1: NAVBAR
          ===================================================================== */}
      <section className="sticky top-0 z-50 w-full border-b border-slate-200 bg-white/90 backdrop-blur-md shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-20">
            
            {/* Logo */}
            <div className="flex-shrink-0 flex items-center">
              <Link to="/" className="flex items-center gap-3 group">
                <div className="bg-[#059669] p-2.5 rounded-xl group-hover:bg-[#047857] transition-colors shadow-sm">
                  <wireframeData.navbar.logo.icon className="h-6 w-6 text-white" />
                </div>
                <span className="font-display font-bold text-2xl tracking-tight text-slate-900">
                  {wireframeData.navbar.logo.text.split(' ')[0]} <span className="text-[#059669]">{wireframeData.navbar.logo.text.split(' ')[1]}</span>
                </span>
              </Link>
            </div>

            {/* Desktop Navigation */}
            <nav className="hidden md:flex items-center space-x-8">
              {wireframeData.navbar.links.map((link, idx) => (
                <Link
                  key={idx}
                  to={link.href}
                  className="text-sm font-medium text-slate-600 hover:text-[#059669] transition-colors"
                >
                  {link.label}
                </Link>
              ))}
            </nav>

            {/* Desktop CTA */}
            <div className="hidden md:flex items-center">
              <Link to={wireframeData.navbar.cta_primary.href}>
                <Button variant="outline" className="border-slate-300">
                  {wireframeData.navbar.cta_primary.label}
                </Button>
              </Link>
            </div>

            {/* Mobile menu button */}
            <div className="flex items-center md:hidden">
              <button
                onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
                className="inline-flex items-center justify-center p-2 rounded-md text-slate-400 hover:text-slate-500 hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-[#059669]"
              >
                <span className="sr-only">Open main menu</span>
                {isMobileMenuOpen ? (
                  <X className="block h-6 w-6" aria-hidden="true" />
                ) : (
                  <Menu className="block h-6 w-6" aria-hidden="true" />
                )}
              </button>
            </div>
          </div>
        </div>

        {/* Mobile Menu Panel */}
        {isMobileMenuOpen && (
          <div className="md:hidden bg-white border-b border-slate-200 shadow-lg absolute w-full">
            <div className="px-4 pt-2 pb-6 space-y-1">
              {wireframeData.navbar.links.map((link, idx) => (
                <Link
                  key={idx}
                  to={link.href}
                  className="block px-3 py-3 rounded-md text-base font-medium text-slate-700 hover:text-[#059669] hover:bg-emerald-50"
                  onClick={() => setIsMobileMenuOpen(false)}
                >
                  {link.label}
                </Link>
              ))}
              <div className="pt-4 pb-2">
                <Link to={wireframeData.navbar.cta_primary.href} onClick={() => setIsMobileMenuOpen(false)}>
                  <Button variant="primary" className="w-full justify-center">
                    {wireframeData.navbar.cta_primary.label}
                  </Button>
                </Link>
              </div>
            </div>
          </div>
        )}
      </section>

      {/* =====================================================================
          SECTION 2: SPLIT AUTH LAYOUT (HERO + FORM)
          ===================================================================== */}
      <section className="flex-grow flex flex-col lg:flex-row">
        
        {/* Left Side - Auth Form Container */}
        <div className="w-full lg:w-1/2 flex flex-col justify-center px-6 py-12 sm:px-12 lg:px-24 xl:px-32 bg-white relative z-10 shadow-[4px_0_24px_rgba(0,0,0,0.02)]">
          
          <div className="max-w-md w-full mx-auto">
            {/* Form Header */}
            <div className="mb-8">
              <Badge variant="success" className="mb-4">Secure Portal Access</Badge>
              <h1 className="font-display text-3xl sm:text-4xl font-bold mb-3 text-slate-900 tracking-tight">
                Welcome Back
              </h1>
              <p className="text-slate-500 text-base leading-relaxed">
                Log in to securely report corruption, track your existing complaints, and access transparency dashboards.
              </p>
            </div>

            {/* Role Tabs */}
            <div className="flex p-1 mb-8 bg-slate-100 rounded-lg">
              <button
                onClick={() => setUserRole('citizen')}
                className={`flex-1 py-2.5 text-sm font-medium rounded-md transition-all ${
                  userRole === 'citizen' 
                    ? 'bg-white text-slate-900 shadow-sm' 
                    : 'text-slate-500 hover:text-slate-700'
                }`}
              >
                Citizen Login
              </button>
              <button
                onClick={() => setUserRole('official')}
                className={`flex-1 py-2.5 text-sm font-medium rounded-md transition-all ${
                  userRole === 'official' 
                    ? 'bg-white text-slate-900 shadow-sm' 
                    : 'text-slate-500 hover:text-slate-700'
                }`}
              >
                Official Login
              </button>
            </div>
            
            {/* Form Content Area */}
            <Card className="p-6 sm:p-8 border-slate-200 shadow-sm">
              
              {/* Primary e-Pramaan CTA (from wireframe) */}
              <Button 
                variant="epramaan" 
                className="w-full mb-6 py-3"
                onClick={handleEpramaanLogin}
                icon={Fingerprint}
              >
                {wireframeData.hero.cta_primary.label}
              </Button>

              <div className="relative mb-6">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-slate-200"></div>
                </div>
                <div className="relative flex justify-center text-sm">
                  <span className="px-4 bg-white text-slate-500 font-medium">Or continue with</span>
                </div>
              </div>

              {/* Form */}
              <form onSubmit={handleSubmit} className="space-y-5">
                
                {/* Error Message Display */}
                {formError && (
                  <div className="p-3 text-sm font-medium text-red-800 bg-red-50 border border-red-200 rounded-lg flex items-start">
                    <AlertCircle className="w-5 h-5 mr-2 shrink-0 mt-0.5" />
                    <span>{formError}</span>
                  </div>
                )}

                {authMethod === 'password' ? (
                  <>
                    <Input
                      label={userRole === 'citizen' ? "Email Address or Mobile" : "Official ID / Email"}
                      id="identifier"
                      name="identifier"
                      type="text"
                      placeholder={userRole === 'citizen' ? "citizen@example.com" : "officer.id@kerala.gov.in"}
                      icon={Mail}
                      value={formData.identifier}
                      onChange={handleInputChange}
                      required
                    />
                    
                    <div className="space-y-1.5">
                      <div className="flex items-center justify-between">
                        <label htmlFor="password" className="block text-sm font-medium text-slate-700 font-body">
                          Password
                        </label>
                        <a href="#" className="text-sm font-medium text-[#059669] hover:text-[#047857]">
                          Forgot password?
                        </a>
                      </div>
                      <div className="relative">
                        <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                          <Lock className="h-5 w-5 text-slate-400" />
                        </div>
                        <input
                          id="password"
                          name="password"
                          type={showPassword ? "text" : "password"}
                          placeholder="••••••••"
                          className="block w-full pl-10 pr-10 py-2.5 rounded-lg border border-slate-300 focus:ring-[#059669] focus:border-[#059669] sm:text-sm font-body transition-colors"
                          value={formData.password}
                          onChange={handleInputChange}
                          required
                        />
                        <button
                          type="button"
                          className="absolute inset-y-0 right-0 pr-3 flex items-center text-slate-400 hover:text-slate-600"
                          onClick={() => setShowPassword(!showPassword)}
                        >
                          {showPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                        </button>
                      </div>
                    </div>
                  </>
                ) : (
                  <>
                    <Input
                      label="Mobile Number"
                      id="phone"
                      name="phone"
                      type="tel"
                      placeholder="Enter 10-digit mobile number"
                      icon={Smartphone}
                      value={formData.phone}
                      onChange={handleInputChange}
                      disabled={otpSent}
                      required
                    />
                    
                    {otpSent && (
                      <div className="animate-in fade-in slide-in-from-top-2 duration-300">
                        <Input
                          label="Enter 6-digit OTP"
                          id="otp"
                          name="otp"
                          type="text"
                          placeholder="• • • • • •"
                          className="text-center tracking-[0.5em] font-bold text-lg"
                          maxLength={6}
                          value={formData.otp}
                          onChange={handleInputChange}
                          required
                        />
                        <p className="text-xs text-slate-500 mt-2 text-center">
                          OTP sent to +91 {formData.phone}. <button type="button" className="text-[#059669] font-medium hover:underline" onClick={() => setOtpSent(false)}>Change number</button>
                        </p>
                      </div>
                    )}
                  </>
                )}

                {/* Submit Button */}
                {authMethod === 'otp' && !otpSent ? (
                  <Button 
                    type="button" 
                    variant="primary" 
                    className="w-full py-2.5" 
                    onClick={handleSendOTP}
                    isLoading={isLoading}
                  >
                    Send OTP
                  </Button>
                ) : (
                  <Button 
                    type="submit" 
                    variant="primary" 
                    className="w-full py-2.5"
                    isLoading={isLoading}
                    icon={authMethod === 'password' ? Lock : CheckCircle2}
                  >
                    {authMethod === 'password' ? 'Sign In Securely' : 'Verify & Login'}
                  </Button>
                )}
              </form>
              
              {/* Secondary CTA (from wireframe) */}
              <div className="mt-6 text-center">
                <button
                  type="button"
                  onClick={() => {
                    setAuthMethod(authMethod === 'password' ? 'otp' : 'password');
                    setFormError('');
                    setOtpSent(false);
                  }}
                  className="text-sm font-medium text-slate-600 hover:text-[#059669] transition-colors inline-flex items-center"
                >
                  {authMethod === 'password' ? (
                    <>
                      <Smartphone className="w-4 h-4 mr-2" />
                      {wireframeData.hero.cta_secondary.label}
                    </>
                  ) : (
                    <>
                      <Lock className="w-4 h-4 mr-2" />
                      Login with Password
                    </>
                  )}
                </button>
              </div>

            </Card>
            
            {/* Footer Links / Help */}
            <div className="mt-8 text-center text-sm text-slate-500">
              <p>
                Don't have an account?{' '}
                <Link to={wireframeData.navbar.cta_primary.href} className="text-[#059669] hover:underline font-medium transition-colors">
                  Register here
                </Link>
              </p>
            </div>
          </div>
        </div>

        {/* Right Side - Branded Hero & Trust Badges */}
        <div className="hidden lg:flex lg:w-1/2 relative bg-slate-900 overflow-hidden">
          {/* Background Image from Wireframe */}
          <img
            src={wireframeData.hero.image.src}
            alt={wireframeData.hero.image.alt}
            className="absolute inset-0 w-full h-full object-cover opacity-30 mix-blend-luminosity"
          />
          
          {/* Gradient Overlay for Brand Colors */}
          <div className="absolute inset-0 bg-gradient-to-br from-[#059669]/95 via-[#047857]/80 to-slate-900/95" />

          {/* Content Container */}
          <div className="relative z-10 flex flex-col justify-center p-16 xl:p-24 text-white w-full h-full">
            
            <div className="mb-16">
              <h2 className="font-display text-4xl xl:text-5xl font-bold mb-6 leading-tight tracking-tight">
                {wireframeData.hero.headline.split('for')[0]}<br />
                <span className="text-emerald-200">for {wireframeData.hero.headline.split('for')[1]}</span>
              </h2>
              <p className="text-lg xl:text-xl text-emerald-50/90 max-w-lg font-light leading-relaxed">
                {wireframeData.hero.sub}
              </p>
            </div>

            {/* Trust Badges - Glassmorphism Style */}
            <div className="space-y-5 max-w-lg">
              <div className="flex items-start gap-4 bg-white/10 p-5 rounded-2xl backdrop-blur-md border border-white/20 shadow-xl transition-transform hover:-translate-y-1 duration-300">
                <div className="bg-emerald-400/20 p-3 rounded-xl shrink-0">
                  <ShieldCheck className="w-7 h-7 text-emerald-300" />
                </div>
                <div>
                  <h3 className="font-display font-semibold text-lg text-white tracking-wide">
                    100% Anonymous Reporting
                  </h3>
                  <p className="text-emerald-50/80 text-sm mt-1.5 leading-relaxed">
                    Zero-knowledge proof architecture ensures your identity is never exposed, even to system administrators.
                  </p>
                </div>
              </div>

              <div className="flex items-start gap-4 bg-white/10 p-5 rounded-2xl backdrop-blur-md border border-white/20 shadow-xl transition-transform hover:-translate-y-1 duration-300">
                <div className="bg-emerald-400/20 p-3 rounded-xl shrink-0">
                  <Activity className="w-7 h-7 text-emerald-300" />
                </div>
                <div>
                  <h3 className="font-display font-semibold text-lg text-white tracking-wide">
                    AI-Driven Transparency
                  </h3>
                  <p className="text-emerald-50/80 text-sm mt-1.5 leading-relaxed">
                    Predictive algorithms analyze patterns to stop systemic corruption before it spreads across departments.
                  </p>
                </div>
              </div>
            </div>

            {/* Bottom decorative element */}
            <div className="absolute bottom-12 left-16 xl:left-24 flex items-center gap-3 text-emerald-200/60 text-sm font-medium tracking-wider uppercase">
              <Lock className="w-4 h-4" />
              <span>256-bit AES Encryption Active</span>
            </div>
          </div>
        </div>
      </section>

      {/* =====================================================================
          SECTION 3: FOOTER
          ===================================================================== */}
      <section className="bg-slate-950 text-slate-300 py-16 border-t border-slate-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-12 lg:gap-8">
            
            {/* Brand Column */}
            <div className="lg:col-span-2">
              <Link to="/" className="flex items-center gap-3 mb-6 group">
                <div className="bg-[#059669] p-2 rounded-lg group-hover:bg-[#047857] transition-colors">
                  <wireframeData.footer.brand.logo_icon className="h-6 w-6 text-white" />
                </div>
                <span className="font-display font-bold text-2xl tracking-tight text-white">
                  {wireframeData.footer.brand.name}
                </span>
              </Link>
              <p className="text-slate-400 text-sm leading-relaxed max-w-sm mb-8">
                {wireframeData.footer.brand.description}
              </p>
              <div className="flex space-x-4">
                {/* Social placeholders */}
                <a href="#" className="text-slate-500 hover:text-white transition-colors">
                  <span className="sr-only">Twitter</span>
                  <svg className="h-6 w-6" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                    <path d="M8.29 20.251c7.547 0 11.675-6.253 11.675-11.675 0-.178 0-.355-.012-.53A8.348 8.348 0 0022 5.92a8.19 8.19 0 01-2.357.646 4.118 4.118 0 001.804-2.27 8.224 8.224 0 01-2.605.996 4.107 4.107 0 00-6.993 3.743 11.65 11.65 0 01-8.457-4.287 4.106 4.106 0 001.27 5.477A4.072 4.072 0 012.8 9.713v.052a4.105 4.105 0 003.292 4.022 4.095 4.095 0 01-1.853.07 4.108 4.108 0 003.834 2.85A8.233 8.233 0 012 18.407a11.616 11.616 0 006.29 1.84" />
                  </svg>
                </a>
                <a href="#" className="text-slate-500 hover:text-white transition-colors">
                  <span className="sr-only">GitHub</span>
                  <svg className="h-6 w-6" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                    <path fillRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" clipRule="evenodd" />
                  </svg>
                </a>
              </div>
            </div>

            {/* Link Groups */}
            {wireframeData.footer.link_groups.map((group, idx) => (
              <div key={idx}>
                <h3 className="text-sm font-semibold text-white tracking-wider uppercase mb-4 font-display">
                  {group.title}
                </h3>
                <ul className="space-y-3">
                  {group.links.map((link, linkIdx) => (
                    <li key={linkIdx}>
                      {link.href.startsWith('tel:') || link.href.startsWith('mailto:') ? (
                        <a href={link.href} className="text-sm text-slate-400 hover:text-[#059669] transition-colors">
                          {link.label}
                        </a>
                      ) : (
                        <Link to={link.href} className="text-sm text-slate-400 hover:text-[#059669] transition-colors">
                          {link.label}
                        </Link>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>

          {/* Legal Section */}
          <div className="mt-16 pt-8 border-t border-slate-800 flex flex-col md:flex-row justify-between items-center gap-4">
            <p className="text-sm text-slate-500">
              {wireframeData.footer.legal.text}
            </p>
            <div className="flex space-x-6">
              {wireframeData.footer.legal.links.map((link, idx) => (
                <Link key={idx} to={link.href} className="text-sm text-slate-500 hover:text-white transition-colors">
                  {link.label}
                </Link>
              ))}
            </div>
          </div>
        </div>
      </section>

    </div>
  );
}
