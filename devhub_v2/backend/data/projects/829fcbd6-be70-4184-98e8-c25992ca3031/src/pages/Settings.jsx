import { useState, useEffect } from 'react';
import DashboardSidebar from '../components/layout/DashboardSidebar';
import { 
  User, 
  Lock, 
  Bell, 
  Shield, 
  Save, 
  ShieldCheck, 
  LogOut, 
  FileText, 
  Menu, 
  X, 
  Camera, 
  Smartphone, 
  Mail, 
  Globe, 
  Key, 
  EyeOff, 
  Eye,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Laptop,
  Activity
} from 'lucide-react';
import { userProfile } from '../mockData.js';

// ============================================================================
// INLINE UI PRIMITIVES & MOCK DATA
// ============================================================================

const auditLogsData = [
  { id: 'al-1', action: 'Login Successful', ip: '192.168.1.45', location: 'Thiruvananthapuram, KL', date: '2023-10-26T08:30:00Z', status: 'success' },
  { id: 'al-2', action: 'Password Changed', ip: '192.168.1.45', location: 'Thiruvananthapuram, KL', date: '2023-10-20T14:15:00Z', status: 'success' },
  { id: 'al-3', action: 'Failed Login Attempt', ip: '45.22.11.99', location: 'Unknown', date: '2023-10-19T02:10:00Z', status: 'warning' },
  { id: 'al-4', action: '2FA Enabled', ip: '192.168.1.45', location: 'Thiruvananthapuram, KL', date: '2023-10-15T10:05:00Z', status: 'success' },
  { id: 'al-5', action: 'Profile Updated', ip: '192.168.1.45', location: 'Thiruvananthapuram, KL', date: '2023-10-10T11:20:00Z', status: 'success' },
  { id: 'al-6', action: 'Data Export Requested', ip: '192.168.1.45', location: 'Thiruvananthapuram, KL', date: '2023-09-28T16:40:00Z', status: 'info' },
];

const activeSessionsData = [
  { id: 'sess-1', device: 'MacBook Pro 16"', browser: 'Chrome 118.0', location: 'Thiruvananthapuram, KL', ip: '192.168.1.45', lastActive: 'Current Session', isCurrent: true, icon: Laptop },
  { id: 'sess-2', device: 'iPhone 13 Pro', browser: 'Safari Mobile', location: 'Kochi, KL', ip: '117.204.14.22', lastActive: '2 hours ago', isCurrent: false, icon: Smartphone },
];

// Inline Toggle Component
const Toggle = ({ enabled, onChange, label, description }) => (
  <div className="flex items-center justify-between py-4">
    <div className="flex flex-col pr-4">
      <span className="text-sm font-medium text-slate-900 font-body">{label}</span>
      {description && <span className="text-sm text-slate-500 font-body mt-0.5">{description}</span>}
    </div>
    <button
      type="button"
      className={`${
        enabled ? 'bg-emerald-600' : 'bg-slate-200'
      } relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-emerald-600 focus:ring-offset-2`}
      role="switch"
      aria-checked={enabled}
      onClick={() => onChange(!enabled)}
    >
      <span
        aria-hidden="true"
        className={`${
          enabled ? 'translate-x-5' : 'translate-x-0'
        } pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out`}
      />
    </button>
  </div>
);

// Inline Input Component
const InputGroup = ({ label, type = "text", id, value, onChange, placeholder, icon: Icon, disabled = false }) => (
  <div className="space-y-1.5">
    <label htmlFor={id} className="block text-sm font-medium text-slate-700 font-body">
      {label}
    </label>
    <div className="relative rounded-md shadow-sm">
      {Icon && (
        <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
          <Icon className="h-5 w-5 text-slate-400" aria-hidden="true" />
        </div>
      )}
      <input
        type={type}
        name={id}
        id={id}
        value={value}
        onChange={onChange}
        disabled={disabled}
        className={`block w-full rounded-lg border-slate-300 py-2.5 font-body text-slate-900 focus:border-emerald-500 focus:ring-emerald-500 sm:text-sm border ${Icon ? 'pl-10' : 'pl-3'} ${disabled ? 'bg-slate-50 text-slate-500 cursor-not-allowed' : 'bg-white'}`}
        placeholder={placeholder}
      />
    </div>
  </div>
);

// ============================================================================
// MAIN PAGE COMPONENT
// ============================================================================

export default function Settings() {
  // State Management
  const [activeTab, setActiveTab] = useState('profile');
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [toast, setToast] = useState({ show: false, message: '', type: 'success' });
  
  // Form States
  const [profileData, setProfileData] = useState({
    fullName: userProfile.name,
    email: userProfile.email,
    phone: '+91 98765 43210',
    department: userProfile.department,
    role: userProfile.role,
    location: userProfile.location
  });

  const [securityData, setSecurityData] = useState({
    currentPassword: '',
    newPassword: '',
    confirmPassword: '',
    twoFactorEnabled: userProfile.preferences.twoFactorEnabled
  });

  const [privacyData, setPrivacyData] = useState({
    zkpEnabled: true,
    shareAnalytics: false,
    publicProfile: false,
    blockchainVisibility: 'anonymous'
  });

  const [notificationData, setNotificationData] = useState({
    emailAlerts: true,
    smsAlerts: false,
    pushNotifications: true,
    marketingEmails: false,
    caseUpdates: true,
    aiFlags: true
  });

  // Handlers
  const showToast = (message, type = 'success') => {
    setToast({ show: true, message, type });
    setTimeout(() => setToast({ show: false, message: '', type: 'success' }), 3000);
  };

  const handleProfileSave = (e) => {
    e.preventDefault();
    showToast('Profile information updated successfully.');
  };

  const handleSecuritySave = (e) => {
    e.preventDefault();
    if (securityData.newPassword !== securityData.confirmPassword) {
      showToast('New passwords do not match.', 'error');
      return;
    }
    showToast('Security settings updated successfully.');
    setSecurityData({ ...securityData, currentPassword: '', newPassword: '', confirmPassword: '' });
  };

  const handlePrivacySave = () => {
    showToast('Privacy preferences saved.');
  };

  const handleNotificationSave = () => {
    showToast('Notification preferences updated.');
  };

  // Wireframe Data
  const wireframeData = {
    navbar: {
      logo: { text: "Vigilance C3MS", icon: ShieldCheck },
      links: [
        { label: "Dashboard", url: "/dashboard" },
        { label: "My Reports", url: "/reports" },
        { label: "Department Risk", url: "/departments" },
        { label: "Settings", url: "/settings" }
      ],
      cta: { label: "Secure Logout", url: "/logout", icon: LogOut }
    },
    hero: {
      headline: "Secure Your Identity and Manage Your Vigilance Preferences",
      sub: "Control your anonymity levels, configure real-time notification alerts for your active reports, and review your blockchain-verified activity logs to ensure complete transparency and safety.",
      cta_primary: { label: "Update Security Settings", url: "#security-preferences", icon: Lock },
      cta_secondary: { label: "Review Audit Logs", url: "#audit-history", icon: FileText },
      image: {
        src: "https://images.unsplash.com/photo-1550751827-4bd374c3f58b?w=800&q=80",
        alt: "Abstract representation of secure blockchain data and identity protection"
      }
    }
  };

  const tabs = [
    { id: 'profile', label: 'Profile', icon: User },
    { id: 'security', label: 'Security', icon: Lock },
    { id: 'privacy', label: 'Anonymity & Privacy', icon: Shield },
    { id: 'notifications', label: 'Notifications', icon: Bell },
    { id: 'audit', label: 'Audit Logs', icon: Activity },
  ];

  return (
    <div className="flex h-screen bg-[#F8FAFC] overflow-hidden font-body">
      {/* SECTION 1: Dashboard Sidebar */}
      <div className="hidden md:block z-20">
        <DashboardSidebar />
      </div>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col h-screen overflow-hidden relative">
        
        {/* Toast Notification */}
        {toast.show && (
          <div className={`absolute top-4 right-4 z-50 flex items-center gap-2 px-4 py-3 rounded-lg shadow-lg border animate-in slide-in-from-top-5 fade-in duration-300 ${
            toast.type === 'success' ? 'bg-emerald-50 border-emerald-200 text-emerald-800' : 'bg-rose-50 border-rose-200 text-rose-800'
          }`}>
            {toast.type === 'success' ? <CheckCircle2 className="w-5 h-5 text-emerald-600" /> : <AlertTriangle className="w-5 h-5 text-rose-600" />}
            <span className="text-sm font-medium">{toast.message}</span>
          </div>
        )}

        {/* SECTION 2: Mobile Navbar (from wireframe) */}
        <header className="md:hidden bg-white border-b border-slate-200 px-4 py-3 flex items-center justify-between z-20">
          <div className="flex items-center gap-2">
            <div className="bg-emerald-600 p-1.5 rounded-md">
              <wireframeData.navbar.logo.icon className="w-5 h-5 text-white" />
            </div>
            <span className="font-display font-bold text-lg text-slate-900">{wireframeData.navbar.logo.text}</span>
          </div>
          <button onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)} className="text-slate-500 hover:text-slate-900">
            {isMobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
          </button>
        </header>

        {/* Mobile Menu Dropdown */}
        {isMobileMenuOpen && (
          <div className="md:hidden absolute top-[60px] left-0 right-0 bg-white border-b border-slate-200 shadow-lg z-30 px-4 py-4 space-y-2">
            {wireframeData.navbar.links.map((link, idx) => (
              <a key={idx} href={link.url} className="block px-3 py-2 rounded-md text-base font-medium text-slate-700 hover:text-emerald-600 hover:bg-emerald-50">
                {link.label}
              </a>
            ))}
            <div className="pt-4 mt-4 border-t border-slate-100">
              <a href={wireframeData.navbar.cta.url} className="flex items-center gap-2 px-3 py-2 rounded-md text-base font-medium text-rose-600 hover:bg-rose-50">
                <wireframeData.navbar.cta.icon className="w-5 h-5" />
                {wireframeData.navbar.cta.label}
              </a>
            </div>
          </div>
        )}

        <main className="flex-1 overflow-y-auto scrollbar-hide">
          
          {/* SECTION 3: Settings Hero (from wireframe) */}
          <section className="relative bg-slate-900 py-16 sm:py-20 px-4 sm:px-6 lg:px-8 overflow-hidden">
            <div className="absolute inset-0 z-0">
              <img 
                src={wireframeData.hero.image.src} 
                alt={wireframeData.hero.image.alt}
                className="w-full h-full object-cover opacity-20 mix-blend-luminosity"
              />
              <div className="absolute inset-0 bg-gradient-to-t from-slate-900 via-slate-900/80 to-transparent" />
            </div>
            
            <div className="relative z-10 max-w-5xl mx-auto">
              <h1 className="text-3xl sm:text-4xl md:text-5xl font-display font-bold text-white tracking-tight mb-4 max-w-3xl">
                {wireframeData.hero.headline}
              </h1>
              <p className="text-lg text-slate-300 font-body max-w-2xl mb-8 leading-relaxed">
                {wireframeData.hero.sub}
              </p>
              <div className="flex flex-col sm:flex-row gap-4">
                <button 
                  onClick={() => setActiveTab('security')}
                  className="inline-flex items-center justify-center gap-2 bg-emerald-600 hover:bg-emerald-500 text-white px-6 py-3 rounded-lg font-medium transition-colors shadow-lg shadow-emerald-900/20"
                >
                  <wireframeData.hero.cta_primary.icon className="w-5 h-5" />
                  {wireframeData.hero.cta_primary.label}
                </button>
                <button 
                  onClick={() => setActiveTab('audit')}
                  className="inline-flex items-center justify-center gap-2 bg-slate-800 hover:bg-slate-700 text-white border border-slate-700 px-6 py-3 rounded-lg font-medium transition-colors"
                >
                  <wireframeData.hero.cta_secondary.icon className="w-5 h-5" />
                  {wireframeData.hero.cta_secondary.label}
                </button>
              </div>
            </div>
          </section>

          <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8 -mt-8 relative z-20">
            
            {/* SECTION 4: Tabs Navigation */}
            <div className="bg-white rounded-t-xl border-b border-slate-200 shadow-sm overflow-x-auto scrollbar-hide">
              <nav className="flex space-x-1 px-2 pt-2" aria-label="Tabs">
                {tabs.map((tab) => {
                  const isActive = activeTab === tab.id;
                  return (
                    <button
                      key={tab.id}
                      onClick={() => setActiveTab(tab.id)}
                      className={`
                        flex items-center gap-2 px-4 py-3 text-sm font-medium rounded-t-lg transition-colors whitespace-nowrap
                        ${isActive 
                          ? 'bg-slate-50 text-emerald-700 border-b-2 border-emerald-600' 
                          : 'text-slate-500 hover:text-slate-700 hover:bg-slate-50'
                        }
                      `}
                    >
                      <tab.icon className={`w-4 h-4 ${isActive ? 'text-emerald-600' : 'text-slate-400'}`} />
                      {tab.label}
                    </button>
                  );
                })}
              </nav>
            </div>

            {/* Tab Content Container */}
            <div className="bg-white rounded-b-xl shadow-sm border border-t-0 border-slate-200 min-h-[500px]">
              
              {/* SECTION 5: Profile Form */}
              {activeTab === 'profile' && (
                <div className="p-6 sm:p-8 animate-in fade-in duration-300">
                  <div className="mb-8">
                    <h2 className="text-xl font-display font-semibold text-slate-900">Personal Information</h2>
                    <p className="text-sm text-slate-500 mt-1">Update your photo and personal details here.</p>
                  </div>

                  <form onSubmit={handleProfileSave} className="space-y-8">
                    {/* Avatar Upload */}
                    <div className="flex items-center gap-6">
                      <div className="relative">
                        <img 
                          src={userProfile.avatar} 
                          alt="Profile" 
                          className="w-24 h-24 rounded-full object-cover border-4 border-slate-50 shadow-sm"
                        />
                        <button type="button" className="absolute bottom-0 right-0 bg-white p-1.5 rounded-full border border-slate-200 shadow-sm text-slate-600 hover:text-emerald-600 transition-colors">
                          <Camera className="w-4 h-4" />
                        </button>
                      </div>
                      <div>
                        <div className="flex gap-3">
                          <button type="button" className="px-4 py-2 bg-white border border-slate-300 rounded-md text-sm font-medium text-slate-700 hover:bg-slate-50 transition-colors">
                            Change
                          </button>
                          <button type="button" className="px-4 py-2 bg-white border border-slate-300 rounded-md text-sm font-medium text-rose-600 hover:bg-rose-50 transition-colors">
                            Remove
                          </button>
                        </div>
                        <p className="text-xs text-slate-500 mt-2">JPG, GIF or PNG. Max size of 800K</p>
                      </div>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                      <InputGroup 
                        label="Full Name" 
                        id="fullName" 
                        icon={User}
                        value={profileData.fullName} 
                        onChange={(e) => setProfileData({...profileData, fullName: e.target.value})} 
                      />
                      <InputGroup 
                        label="Email Address" 
                        id="email" 
                        type="email"
                        icon={Mail}
                        value={profileData.email} 
                        onChange={(e) => setProfileData({...profileData, email: e.target.value})} 
                      />
                      <InputGroup 
                        label="Phone Number" 
                        id="phone" 
                        icon={Smartphone}
                        value={profileData.phone} 
                        onChange={(e) => setProfileData({...profileData, phone: e.target.value})} 
                      />
                      <InputGroup 
                        label="Location" 
                        id="location" 
                        icon={Globe}
                        value={profileData.location} 
                        onChange={(e) => setProfileData({...profileData, location: e.target.value})} 
                      />
                      <div className="sm:col-span-2">
                        <InputGroup 
                          label="Department / Organization" 
                          id="department" 
                          value={profileData.department} 
                          disabled={true}
                        />
                        <p className="text-xs text-slate-500 mt-1.5 flex items-center gap-1">
                          <Lock className="w-3 h-3" /> Department changes require administrator approval.
                        </p>
                      </div>
                    </div>

                    <div className="pt-6 border-t border-slate-200 flex justify-end gap-3">
                      <button type="button" className="px-5 py-2.5 bg-white border border-slate-300 rounded-lg text-sm font-medium text-slate-700 hover:bg-slate-50 transition-colors">
                        Cancel
                      </button>
                      <button type="submit" className="px-5 py-2.5 bg-emerald-600 text-white rounded-lg text-sm font-medium hover:bg-emerald-700 transition-colors flex items-center gap-2 shadow-sm">
                        <Save className="w-4 h-4" />
                        Save Changes
                      </button>
                    </div>
                  </form>
                </div>
              )}

              {/* SECTION 6: Security Panel */}
              {activeTab === 'security' && (
                <div className="p-6 sm:p-8 animate-in fade-in duration-300 space-y-10">
                  
                  {/* Password Change */}
                  <div>
                    <div className="mb-6">
                      <h2 className="text-xl font-display font-semibold text-slate-900">Password & Authentication</h2>
                      <p className="text-sm text-slate-500 mt-1">Manage your password and secure your account.</p>
                    </div>
                    
                    <form onSubmit={handleSecuritySave} className="max-w-md space-y-5">
                      <InputGroup 
                        label="Current Password" 
                        id="currentPassword" 
                        type="password"
                        icon={Key}
                        value={securityData.currentPassword} 
                        onChange={(e) => setSecurityData({...securityData, currentPassword: e.target.value})} 
                      />
                      <InputGroup 
                        label="New Password" 
                        id="newPassword" 
                        type="password"
                        icon={Lock}
                        value={securityData.newPassword} 
                        onChange={(e) => setSecurityData({...securityData, newPassword: e.target.value})} 
                      />
                      <InputGroup 
                        label="Confirm New Password" 
                        id="confirmPassword" 
                        type="password"
                        icon={Lock}
                        value={securityData.confirmPassword} 
                        onChange={(e) => setSecurityData({...securityData, confirmPassword: e.target.value})} 
                      />
                      <button type="submit" className="mt-2 px-5 py-2.5 bg-slate-900 text-white rounded-lg text-sm font-medium hover:bg-slate-800 transition-colors shadow-sm">
                        Update Password
                      </button>
                    </form>
                  </div>

                  <hr className="border-slate-200" />

                  {/* 2FA Settings */}
                  <div>
                    <h3 className="text-lg font-display font-semibold text-slate-900 mb-4">Two-Factor Authentication (2FA)</h3>
                    <div className="bg-slate-50 border border-slate-200 rounded-xl p-5">
                      <Toggle 
                        label="Enable Authenticator App" 
                        description="Use an app like Google Authenticator or Authy to generate one-time codes."
                        enabled={securityData.twoFactorEnabled}
                        onChange={(val) => setSecurityData({...securityData, twoFactorEnabled: val})}
                      />
                      {securityData.twoFactorEnabled && (
                        <div className="mt-4 p-4 bg-emerald-50 border border-emerald-100 rounded-lg flex items-start gap-3">
                          <ShieldCheck className="w-5 h-5 text-emerald-600 mt-0.5" />
                          <div>
                            <p className="text-sm font-medium text-emerald-900">2FA is currently active</p>
                            <p className="text-sm text-emerald-700 mt-1">Your account is protected by an additional layer of security.</p>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>

                  <hr className="border-slate-200" />

                  {/* Active Sessions */}
                  <div>
                    <h3 className="text-lg font-display font-semibold text-slate-900 mb-4">Active Sessions</h3>
                    <p className="text-sm text-slate-500 mb-4">These are the devices that have logged into your account. Revoke any sessions that you do not recognize.</p>
                    
                    <div className="border border-slate-200 rounded-xl overflow-hidden">
                      <ul className="divide-y divide-slate-200">
                        {activeSessionsData.map((session) => (
                          <li key={session.id} className="p-4 flex items-center justify-between hover:bg-slate-50 transition-colors">
                            <div className="flex items-center gap-4">
                              <div className="p-2 bg-slate-100 rounded-lg text-slate-600">
                                <session.icon className="w-6 h-6" />
                              </div>
                              <div>
                                <p className="text-sm font-medium text-slate-900 flex items-center gap-2">
                                  {session.device}
                                  {session.isCurrent && (
                                    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-emerald-100 text-emerald-800">
                                      Current
                                    </span>
                                  )}
                                </p>
                                <p className="text-xs text-slate-500 mt-0.5">
                                  {session.browser} • {session.location} • {session.ip}
                                </p>
                              </div>
                            </div>
                            {!session.isCurrent && (
                              <button className="text-sm font-medium text-rose-600 hover:text-rose-700 px-3 py-1.5 rounded-md hover:bg-rose-50 transition-colors">
                                Revoke
                              </button>
                            )}
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>

                </div>
              )}

              {/* SECTION 7: Anonymity & Privacy */}
              {activeTab === 'privacy' && (
                <div className="p-6 sm:p-8 animate-in fade-in duration-300">
                  <div className="mb-8">
                    <h2 className="text-xl font-display font-semibold text-slate-900">Anonymity & Privacy Controls</h2>
                    <p className="text-sm text-slate-500 mt-1">Manage how your identity is protected and data is shared within the C3MS network.</p>
                  </div>

                  <div className="space-y-6 max-w-3xl">
                    <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
                      <div className="flex items-start gap-4 mb-6">
                        <div className="p-3 bg-indigo-50 rounded-lg text-indigo-600">
                          <EyeOff className="w-6 h-6" />
                        </div>
                        <div>
                          <h3 className="text-base font-semibold text-slate-900">Zero-Knowledge Proof (ZKP) Identity</h3>
                          <p className="text-sm text-slate-500 mt-1">
                            When enabled, your identity is cryptographically shielded. Investigators can verify your credentials without ever seeing your actual name or contact details.
                          </p>
                        </div>
                      </div>
                      <div className="border-t border-slate-100 pt-2">
                        <Toggle 
                          label="Enable ZKP Shielding" 
                          enabled={privacyData.zkpEnabled}
                          onChange={(val) => {
                            setPrivacyData({...privacyData, zkpEnabled: val});
                            handlePrivacySave();
                          }}
                        />
                      </div>
                    </div>

                    <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
                      <h3 className="text-base font-semibold text-slate-900 mb-4">Data Sharing Preferences</h3>
                      <div className="space-y-2 divide-y divide-slate-100">
                        <Toggle 
                          label="Share Anonymous Analytics" 
                          description="Help improve the Predictive AI by sharing anonymized usage patterns."
                          enabled={privacyData.shareAnalytics}
                          onChange={(val) => {
                            setPrivacyData({...privacyData, shareAnalytics: val});
                            handlePrivacySave();
                          }}
                        />
                        <Toggle 
                          label="Public Directory Visibility" 
                          description="Allow your profile to be found by other verified officers in the directory."
                          enabled={privacyData.publicProfile}
                          onChange={(val) => {
                            setPrivacyData({...privacyData, publicProfile: val});
                            handlePrivacySave();
                          }}
                        />
                      </div>
                    </div>

                    <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
                      <h3 className="text-base font-semibold text-slate-900 mb-4">Blockchain Ledger Visibility</h3>
                      <p className="text-sm text-slate-500 mb-4">Choose how your actions are recorded on the immutable public ledger.</p>
                      
                      <div className="space-y-3">
                        {['anonymous', 'pseudonymous', 'public'].map((option) => (
                          <label key={option} className={`flex items-center p-4 border rounded-lg cursor-pointer transition-colors ${privacyData.blockchainVisibility === option ? 'border-emerald-500 bg-emerald-50/50' : 'border-slate-200 hover:bg-slate-50'}`}>
                            <input 
                              type="radio" 
                              name="blockchainVisibility" 
                              value={option}
                              checked={privacyData.blockchainVisibility === option}
                              onChange={(e) => {
                                setPrivacyData({...privacyData, blockchainVisibility: e.target.value});
                                handlePrivacySave();
                              }}
                              className="h-4 w-4 text-emerald-600 focus:ring-emerald-500 border-slate-300"
                            />
                            <div className="ml-3">
                              <span className="block text-sm font-medium text-slate-900 capitalize">{option}</span>
                              <span className="block text-xs text-slate-500 mt-0.5">
                                {option === 'anonymous' && 'Actions are recorded with a rotating hash. Impossible to trace back to you.'}
                                {option === 'pseudonymous' && 'Actions are tied to a static wallet address. Traceable only by system admins.'}
                                {option === 'public' && 'Your full name and department are written to the ledger for maximum transparency.'}
                              </span>
                            </div>
                          </label>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* SECTION 8: Notifications */}
              {activeTab === 'notifications' && (
                <div className="p-6 sm:p-8 animate-in fade-in duration-300">
                  <div className="mb-8">
                    <h2 className="text-xl font-display font-semibold text-slate-900">Notification Preferences</h2>
                    <p className="text-sm text-slate-500 mt-1">Choose what events you want to be notified about and how.</p>
                  </div>

                  <div className="max-w-3xl space-y-8">
                    {/* Channels */}
                    <div>
                      <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider mb-4">Delivery Channels</h3>
                      <div className="bg-white border border-slate-200 rounded-xl overflow-hidden divide-y divide-slate-100">
                        <div className="px-6">
                          <Toggle 
                            label="Email Notifications" 
                            description="Receive alerts at rajesh.kumar@vigilance.kerala.gov.in"
                            enabled={notificationData.emailAlerts}
                            onChange={(val) => { setNotificationData({...notificationData, emailAlerts: val}); handleNotificationSave(); }}
                          />
                        </div>
                        <div className="px-6">
                          <Toggle 
                            label="SMS Alerts" 
                            description="Receive critical alerts via text message to +91 98765 43210"
                            enabled={notificationData.smsAlerts}
                            onChange={(val) => { setNotificationData({...notificationData, smsAlerts: val}); handleNotificationSave(); }}
                          />
                        </div>
                        <div className="px-6">
                          <Toggle 
                            label="Push Notifications" 
                            description="Receive alerts in your browser and mobile app"
                            enabled={notificationData.pushNotifications}
                            onChange={(val) => { setNotificationData({...notificationData, pushNotifications: val}); handleNotificationSave(); }}
                          />
                        </div>
                      </div>
                    </div>

                    {/* Event Types */}
                    <div>
                      <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider mb-4">Event Types</h3>
                      <div className="bg-white border border-slate-200 rounded-xl overflow-hidden divide-y divide-slate-100">
                        <div className="px-6">
                          <Toggle 
                            label="Case Status Updates" 
                            description="When a complaint you are tracking changes status (e.g., Pending to Investigating)"
                            enabled={notificationData.caseUpdates}
                            onChange={(val) => { setNotificationData({...notificationData, caseUpdates: val}); handleNotificationSave(); }}
                          />
                        </div>
                        <div className="px-6">
                          <Toggle 
                            label="AI Predictive Alerts" 
                            description="When the system flags a high-risk anomaly in your jurisdiction"
                            enabled={notificationData.aiFlags}
                            onChange={(val) => { setNotificationData({...notificationData, aiFlags: val}); handleNotificationSave(); }}
                          />
                        </div>
                        <div className="px-6">
                          <Toggle 
                            label="System & Security Announcements" 
                            description="Important updates regarding C3MS platform maintenance or security"
                            enabled={notificationData.marketingEmails}
                            onChange={(val) => { setNotificationData({...notificationData, marketingEmails: val}); handleNotificationSave(); }}
                          />
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* SECTION 9: Audit Logs */}
              {activeTab === 'audit' && (
                <div className="p-6 sm:p-8 animate-in fade-in duration-300">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
                    <div>
                      <h2 className="text-xl font-display font-semibold text-slate-900">Security Audit Logs</h2>
                      <p className="text-sm text-slate-500 mt-1">A complete, immutable record of your account activity.</p>
                    </div>
                    <button className="inline-flex items-center justify-center gap-2 px-4 py-2 bg-white border border-slate-300 rounded-lg text-sm font-medium text-slate-700 hover:bg-slate-50 transition-colors shadow-sm">
                      <FileText className="w-4 h-4" />
                      Export CSV
                    </button>
                  </div>

                  <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
                    <div className="overflow-x-auto">
                      <table className="min-w-full divide-y divide-slate-200">
                        <thead className="bg-slate-50">
                          <tr>
                            <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Action</th>
                            <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Date & Time</th>
                            <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">IP Address</th>
                            <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Location</th>
                            <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Status</th>
                          </tr>
                        </thead>
                        <tbody className="bg-white divide-y divide-slate-200">
                          {auditLogsData.map((log) => (
                            <tr key={log.id} className="hover:bg-slate-50/50 transition-colors">
                              <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-slate-900">
                                {log.action}
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-500">
                                {new Date(log.date).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })}
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-500 font-mono">
                                {log.ip}
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-500">
                                {log.location}
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap">
                                <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium capitalize
                                  ${log.status === 'success' ? 'bg-emerald-100 text-emerald-800' : 
                                    log.status === 'warning' ? 'bg-amber-100 text-amber-800' : 
                                    'bg-blue-100 text-blue-800'}`}>
                                  {log.status}
                                </span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    <div className="bg-slate-50 px-6 py-3 border-t border-slate-200 flex items-center justify-between">
                      <span className="text-sm text-slate-500">Showing 6 of 124 records</span>
                      <div className="flex gap-2">
                        <button className="px-3 py-1 border border-slate-300 rounded text-sm text-slate-600 bg-white hover:bg-slate-50 disabled:opacity-50" disabled>Previous</button>
                        <button className="px-3 py-1 border border-slate-300 rounded text-sm text-slate-600 bg-white hover:bg-slate-50">Next</button>
                      </div>
                    </div>
                  </div>

                  {/* SECTION 10: Danger Zone (Appended to Audit or Security, placed here for flow) */}
                  <div className="mt-12 pt-8 border-t border-rose-100">
                    <h3 className="text-lg font-display font-semibold text-rose-600 mb-2">Danger Zone</h3>
                    <p className="text-sm text-slate-500 mb-4">Irreversible actions regarding your account data.</p>
                    <div className="bg-rose-50 border border-rose-200 rounded-xl p-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                      <div>
                        <h4 className="text-sm font-bold text-rose-900">Deactivate Account</h4>
                        <p className="text-sm text-rose-700 mt-1 max-w-xl">
                          Once you deactivate your account, you will lose access to all assigned cases. Your historical actions will remain on the blockchain ledger for audit purposes.
                        </p>
                      </div>
                      <button className="shrink-0 px-4 py-2 bg-rose-600 text-white rounded-lg text-sm font-medium hover:bg-rose-700 transition-colors shadow-sm">
                        Deactivate Account
                      </button>
                    </div>
                  </div>

                </div>
              )}

            </div>
          </div>
          
          {/* Footer spacer */}
          <div className="h-12"></div>
        </main>
      </div>
    </div>
  );
}