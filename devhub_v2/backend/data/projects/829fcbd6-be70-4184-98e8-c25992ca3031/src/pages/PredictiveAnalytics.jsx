import React, { useMemo, useState } from 'react';
import { 
  Activity, 
  AlertTriangle, 
  ArrowRight, 
  BarChart3, 
  BrainCircuit, 
  Briefcase, 
  Calendar, 
  CheckCircle2, 
  ChevronRight, 
  Clock, 
  Crosshair, 
  Database, 
  FileText, 
  Filter, 
  LineChart, 
  Map, 
  MapPin, 
  Network, 
  Search, 
  ShieldAlert, 
  ShieldCheck, 
  Target, 
  TrendingDown, 
  TrendingUp, 
  Users, 
  Zap
} from 'lucide-react';
import AppShell from '../components/AppShell';
import PageHero from '../components/PageHero';
import StatCard from '../components/StatCard';
import { categories } from '../mockData';

// ============================================================================
// INLINE UI PRIMITIVES (Ensuring self-contained file)
// ============================================================================

const Card = ({ children, className = '', noPadding = false }) => (
  <div className={`bg-slate-900 border border-slate-800 rounded-xl shadow-lg overflow-hidden ${className}`}>
    {!noPadding ? <div className="p-6">{children}</div> : children}
  </div>
);

const Badge = ({ children, variant = 'default', className = '' }) => {
  const variants = {
    default: 'bg-slate-800 text-slate-300 border-slate-700',
    primary: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
    warning: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
    danger: 'bg-rose-500/10 text-rose-400 border-rose-500/20',
    info: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
  };
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${variants[variant]} ${className}`}>
      {children}
    </span>
  );
};

const Button = ({ children, variant = 'primary', size = 'md', className = '', icon: Icon, ...props }) => {
  const variants = {
    primary: 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-md shadow-emerald-900/20 border border-emerald-500',
    secondary: 'bg-slate-800 hover:bg-slate-700 text-white border border-slate-700',
    outline: 'bg-transparent hover:bg-slate-800 text-slate-300 border border-slate-700',
    ghost: 'bg-transparent hover:bg-slate-800 text-slate-400 border-transparent',
  };
  const sizes = {
    sm: 'px-3 py-1.5 text-xs',
    md: 'px-4 py-2 text-sm',
    lg: 'px-6 py-3 text-base',
  };
  return (
    <button 
      className={`inline-flex items-center justify-center rounded-lg font-medium transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-emerald-500/50 ${variants[variant]} ${sizes[size]} ${className}`}
      {...props}
    >
      {Icon && <Icon className={`w-4 h-4 ${children ? 'mr-2' : ''}`} />}
      {children}
    </button>
  );
};

const ProgressBar = ({ value, max = 100, colorClass = 'bg-emerald-500', className = '' }) => {
  const percentage = Math.min(100, Math.max(0, (value / max) * 100));
  return (
    <div className={`h-2 w-full bg-slate-800 rounded-full overflow-hidden ${className}`}>
      <div 
        className={`h-full rounded-full transition-all duration-1000 ease-out ${colorClass}`} 
        style={{ width: `${percentage}%` }}
      />
    </div>
  );
};

// ============================================================================
// MOCK DATA (Specific to Predictive Analytics)
// ============================================================================

const predictiveKPIs = [
  { id: 'kpi-1', label: 'AI Anomalies Detected', value: '342', trend: '+12%', icon: 'BrainCircuit', tone: 'warning' },
  { id: 'kpi-2', label: 'Predicted Hotspots', value: '14', trend: '+2', icon: 'Map', tone: 'danger' },
  { id: 'kpi-3', label: 'Risk Model Accuracy', value: '94.2%', trend: '+1.5%', icon: 'Target', tone: 'success' },
  { id: 'kpi-4', label: 'Preventative Actions', value: '89', trend: '+24%', icon: 'ShieldCheck', tone: 'info' },
];

const departmentRisks = [
  { id: 'dept-1', name: 'Public Works (PWD)', score: 88, trend: 'up', primaryFactor: 'Contract Allocation Irregularities', activeAlerts: 12, budgetAtRisk: '₹4.2Cr' },
  { id: 'dept-2', name: 'Revenue Department', score: 76, trend: 'up', primaryFactor: 'Land Registration Delays', activeAlerts: 8, budgetAtRisk: '₹1.1Cr' },
  { id: 'dept-3', name: 'Motor Vehicles (MVD)', score: 65, trend: 'down', primaryFactor: 'Checkpost Bribery', activeAlerts: 4, budgetAtRisk: '₹45L' },
  { id: 'dept-4', name: 'Local Self Govt (LSGD)', score: 82, trend: 'up', primaryFactor: 'Building Permit Extortion', activeAlerts: 15, budgetAtRisk: '₹2.8Cr' },
  { id: 'dept-5', name: 'Health Services', score: 45, trend: 'down', primaryFactor: 'Equipment Procurement', activeAlerts: 2, budgetAtRisk: '₹80L' },
  { id: 'dept-6', name: 'Civil Supplies', score: 58, trend: 'stable', primaryFactor: 'Ration Distribution Leakage', activeAlerts: 5, budgetAtRisk: '₹1.5Cr' },
];

const trendForecastData = [
  { month: 'Jan', actual: 120, predicted: 115 },
  { month: 'Feb', actual: 145, predicted: 130 },
  { month: 'Mar', actual: 135, predicted: 140 },
  { month: 'Apr', actual: 160, predicted: 155 },
  { month: 'May', actual: 185, predicted: 170 },
  { month: 'Jun', actual: 210, predicted: 190 },
  { month: 'Jul', actual: null, predicted: 220 }, // Future
  { month: 'Aug', actual: null, predicted: 245 }, // Future
  { month: 'Sep', actual: null, predicted: 230 }, // Future
];

const aiAlerts = [
  { id: 'alt-1', title: 'Syndicate Activity Detected', description: 'Pattern of 14 similar complaints across 3 districts suggests coordinated extortion in LSGD building permits.', severity: 'critical', time: '2 hours ago', type: 'Pattern Recognition' },
  { id: 'alt-2', title: 'Anomalous Tender Approval', description: 'PWD contract #4421 approved 400% faster than historical average for vendor "Apex Infra".', severity: 'high', time: '5 hours ago', type: 'Process Anomaly' },
  { id: 'alt-3', title: 'Sudden Spike in Anonymous Reports', description: '32 new anonymous reports filed against Thrissur RTO in the last 48 hours.', severity: 'high', time: '1 day ago', type: 'Volume Spike' },
  { id: 'alt-4', title: 'Sentiment Shift: Negative', description: 'NLP analysis of citizen feedback shows a 45% drop in trust sentiment regarding Civil Supplies in Kozhikode.', severity: 'medium', time: '2 days ago', type: 'NLP Analysis' },
  { id: 'alt-5', title: 'Resource Bottleneck Predicted', description: 'Current investigation velocity in Revenue Dept will lead to a 60-day backlog by next month.', severity: 'medium', time: '3 days ago', type: 'Predictive Modeling' },
];

const geoHotspots = [
  { id: 'geo-1', district: 'Thiruvananthapuram', riskLevel: 'High', score: 85, primaryIssue: 'PWD Contract Fraud', activeCases: 142, trend: 'up' },
  { id: 'geo-2', district: 'Ernakulam', riskLevel: 'High', score: 82, primaryIssue: 'LSGD Permit Extortion', activeCases: 118, trend: 'up' },
  { id: 'geo-3', district: 'Kozhikode', riskLevel: 'Medium', score: 68, primaryIssue: 'Revenue Dept Delays', activeCases: 84, trend: 'stable' },
  { id: 'geo-4', district: 'Thrissur', riskLevel: 'Medium', score: 62, primaryIssue: 'MVD Checkpost Issues', activeCases: 56, trend: 'down' },
];

const resourceRecommendations = [
  { id: 'rec-1', action: 'Deploy Special Audit Team', target: 'PWD, Thiruvananthapuram', reason: '88% risk score with ₹4.2Cr budget at risk. High probability of systemic fraud.', impact: 'High', status: 'pending' },
  { id: 'rec-2', action: 'Initiate Covert Surveillance', target: 'LSGD, Ernakulam', reason: 'Pattern of 15 linked extortion complaints detected by AI.', impact: 'High', status: 'approved' },
  { id: 'rec-3', action: 'Reallocate 3 Investigators', target: 'Revenue Dept, Kozhikode', reason: 'Predicted backlog of 60 days. Current staff capacity exceeded by 140%.', impact: 'Medium', status: 'pending' },
  { id: 'rec-4', action: 'Automated Warning Notice', target: 'MVD Checkposts (Statewide)', reason: 'Seasonal spike in bribery complaints predicted for upcoming festival season.', impact: 'Low', status: 'rejected' },
];

// ============================================================================
// MAIN PAGE COMPONENT
// ============================================================================

export default function PredictiveAnalytics() {
  // Local State
  const [timeframe, setTimeframe] = useState('30d');
  const [searchQuery, setSearchQuery] = useState('');
  const [activeTab, setActiveTab] = useState('overview');
  const [actionStates, setActionStates] = useState(
    resourceRecommendations.reduce((acc, rec) => ({ ...acc, [rec.id]: rec.status }), {})
  );

  // Handlers
  const handleAction = (id, newStatus) => {
    setActionStates(prev => ({ ...prev, [id]: newStatus }));
  };

  // Filtered Data
  const filteredDepartments = useMemo(() => {
    return departmentRisks.filter(dept => 
      dept.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      dept.primaryFactor.toLowerCase().includes(searchQuery.toLowerCase())
    );
  }, [searchQuery]);

  return (
    <AppShell>
      {/* Dark Theme Wrapper for Analytics Dashboard */}
      <div className="min-h-screen bg-slate-950 text-slate-300 font-body selection:bg-emerald-500/30">
        
        {/* HERO SECTION */}
        <PageHero 
          title="Predictive Analytics Engine"
          sub="AI-driven insights, risk forecasting, and proactive resource allocation to combat systemic corruption before it escalates."
          badge={{ text: "C3MS AI Core Active", icon: BrainCircuit }}
          breadcrumbs={[
            { label: 'Dashboard', href: '/dashboard' },
            { label: 'Predictive Analytics', href: '/analytics' }
          ]}
        />

        {/* MAIN CONTENT CONTAINER */}
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 -mt-8 relative z-10">
          
          {/* CONTROL BAR */}
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-8 bg-slate-900/80 backdrop-blur-md p-4 rounded-xl border border-slate-800 shadow-lg">
            <div className="flex items-center gap-2 overflow-x-auto w-full sm:w-auto pb-2 sm:pb-0">
              <Button 
                variant={activeTab === 'overview' ? 'primary' : 'ghost'} 
                size="sm" 
                onClick={() => setActiveTab('overview')}
                icon={BarChart3}
              >
                Overview
              </Button>
              <Button 
                variant={activeTab === 'risk' ? 'primary' : 'ghost'} 
                size="sm" 
                onClick={() => setActiveTab('risk')}
                icon={AlertTriangle}
              >
                Risk Matrix
              </Button>
              <Button 
                variant={activeTab === 'geo' ? 'primary' : 'ghost'} 
                size="sm" 
                onClick={() => setActiveTab('geo')}
                icon={Map}
              >
                Geo-Spatial
              </Button>
            </div>

            <div className="flex items-center gap-3 w-full sm:w-auto">
              <div className="relative w-full sm:w-64">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                <input 
                  type="text" 
                  placeholder="Search departments..." 
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-9 pr-4 py-2 text-sm text-slate-200 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 transition-colors"
                />
              </div>
              <select 
                value={timeframe}
                onChange={(e) => setTimeframe(e.target.value)}
                className="bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 transition-colors appearance-none cursor-pointer"
              >
                <option value="7d">Last 7 Days</option>
                <option value="30d">Last 30 Days</option>
                <option value="90d">Last 90 Days</option>
              </select>
            </div>
          </div>

          {/* SECTION 1: KPI GRID */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
            {predictiveKPIs.map(kpi => (
              <StatCard 
                key={kpi.id}
                label={kpi.label}
                value={kpi.value}
                trend={kpi.trend}
                icon={kpi.icon}
                tone={kpi.tone}
                className="!bg-slate-900 !border-slate-800 !text-slate-200 [&_h3]:!text-slate-400 [&_div.text-3xl]:!text-white"
              />
            ))}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 mb-8">
            
            {/* SECTION 2: DEPARTMENT RISK MATRIX (Spans 2 columns) */}
            <div className="lg:col-span-2 space-y-6">
              <div className="flex items-center justify-between">
                <h2 className="text-xl font-display font-semibold text-white flex items-center gap-2">
                  <Network className="w-5 h-5 text-emerald-500" />
                  Department Risk Matrix
                </h2>
                <Badge variant="primary">Updated 5 mins ago</Badge>
              </div>
              
              <Card noPadding>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead className="bg-slate-950/50 border-b border-slate-800 text-slate-400">
                      <tr>
                        <th className="px-6 py-4 font-medium">Department</th>
                        <th className="px-6 py-4 font-medium">Risk Score</th>
                        <th className="px-6 py-4 font-medium">Primary Risk Factor</th>
                        <th className="px-6 py-4 font-medium text-right">Budget at Risk</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/50">
                      {filteredDepartments.length > 0 ? filteredDepartments.map((dept) => (
                        <tr key={dept.id} className="hover:bg-slate-800/20 transition-colors">
                          <td className="px-6 py-4">
                            <div className="font-medium text-slate-200">{dept.name}</div>
                            <div className="text-xs text-slate-500 mt-1 flex items-center gap-1">
                              <AlertTriangle className="w-3 h-3" /> {dept.activeAlerts} active alerts
                            </div>
                          </td>
                          <td className="px-6 py-4">
                            <div className="flex items-center gap-3">
                              <span className={`font-bold ${dept.score >= 80 ? 'text-rose-400' : dept.score >= 60 ? 'text-amber-400' : 'text-emerald-400'}`}>
                                {dept.score}
                              </span>
                              <div className="w-24">
                                <ProgressBar 
                                  value={dept.score} 
                                  colorClass={dept.score >= 80 ? 'bg-rose-500' : dept.score >= 60 ? 'bg-amber-500' : 'bg-emerald-500'} 
                                />
                              </div>
                              {dept.trend === 'up' ? <TrendingUp className="w-4 h-4 text-rose-400" /> : 
                               dept.trend === 'down' ? <TrendingDown className="w-4 h-4 text-emerald-400" /> : 
                               <TrendingUp className="w-4 h-4 text-slate-500 rotate-90" />}
                            </div>
                          </td>
                          <td className="px-6 py-4 text-slate-400">{dept.primaryFactor}</td>
                          <td className="px-6 py-4 text-right font-mono text-slate-300">{dept.budgetAtRisk}</td>
                        </tr>
                      )) : (
                        <tr>
                          <td colSpan="4" className="px-6 py-8 text-center text-slate-500">
                            No departments match your search.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </Card>

              {/* SECTION 3: PREDICTIVE TREND CHART */}
              <div className="mt-8">
                <h2 className="text-xl font-display font-semibold text-white flex items-center gap-2 mb-6">
                  <LineChart className="w-5 h-5 text-emerald-500" />
                  Complaint Volume Forecast
                </h2>
                <Card>
                  <div className="flex items-center justify-between mb-6 text-sm">
                    <div className="flex gap-4">
                      <div className="flex items-center gap-2">
                        <div className="w-3 h-3 rounded-full bg-emerald-500"></div>
                        <span className="text-slate-400">Actual Volume</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="w-3 h-3 rounded-full bg-slate-700 border border-slate-500 border-dashed"></div>
                        <span className="text-slate-400">AI Predicted</span>
                      </div>
                    </div>
                    <Badge variant="default">94% Confidence Interval</Badge>
                  </div>
                  
                  {/* CSS-based Bar Chart */}
                  <div className="h-64 flex items-end gap-2 sm:gap-4 pt-4 border-b border-slate-800 pb-2">
                    {trendForecastData.map((data, idx) => {
                      const maxVal = 300; // Arbitrary max for scaling
                      const actualHeight = data.actual ? (data.actual / maxVal) * 100 : 0;
                      const predictedHeight = (data.predicted / maxVal) * 100;
                      const isFuture = data.actual === null;

                      return (
                        <div key={idx} className="flex-1 flex flex-col justify-end items-center group relative h-full">
                          {/* Tooltip */}
                          <div className="absolute -top-10 bg-slate-800 text-white text-xs py-1 px-2 rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap z-10 pointer-events-none">
                            {isFuture ? `Predicted: ${data.predicted}` : `Actual: ${data.actual} | Pred: ${data.predicted}`}
                          </div>
                          
                          <div className="w-full max-w-[40px] relative flex items-end justify-center h-full">
                            {/* Predicted Bar (Background) */}
                            <div 
                              className={`absolute bottom-0 w-full rounded-t-sm transition-all duration-500 ${isFuture ? 'bg-slate-800 border border-slate-700 border-dashed' : 'bg-slate-800/50'}`}
                              style={{ height: `${predictedHeight}%` }}
                            />
                            {/* Actual Bar (Foreground) */}
                            {!isFuture && (
                              <div 
                                className="absolute bottom-0 w-full bg-emerald-500 rounded-t-sm transition-all duration-500 shadow-[0_0_10px_rgba(16,185,129,0.3)]"
                                style={{ height: `${actualHeight}%` }}
                              />
                            )}
                          </div>
                          <span className={`text-xs mt-3 ${isFuture ? 'text-slate-500 italic' : 'text-slate-400'}`}>
                            {data.month}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </Card>
              </div>
            </div>

            {/* RIGHT COLUMN */}
            <div className="space-y-8">
              
              {/* SECTION 4: AI ALERTS FEED */}
              <div>
                <div className="flex items-center justify-between mb-6">
                  <h2 className="text-xl font-display font-semibold text-white flex items-center gap-2">
                    <Zap className="w-5 h-5 text-amber-500" />
                    Live AI Alerts
                  </h2>
                  <Button variant="ghost" size="sm">View All</Button>
                </div>
                
                <div className="space-y-4">
                  {aiAlerts.map((alert) => (
                    <Card key={alert.id} className="relative overflow-hidden group hover:border-slate-700 transition-colors">
                      {/* Severity Indicator Line */}
                      <div className={`absolute left-0 top-0 bottom-0 w-1 ${
                        alert.severity === 'critical' ? 'bg-rose-500' : 
                        alert.severity === 'high' ? 'bg-amber-500' : 'bg-blue-500'
                      }`} />
                      
                      <div className="flex justify-between items-start mb-2">
                        <Badge variant={
                          alert.severity === 'critical' ? 'danger' : 
                          alert.severity === 'high' ? 'warning' : 'info'
                        }>
                          {alert.type}
                        </Badge>
                        <span className="text-xs text-slate-500 flex items-center gap-1">
                          <Clock className="w-3 h-3" /> {alert.time}
                        </span>
                      </div>
                      
                      <h3 className="text-slate-200 font-medium mb-1 group-hover:text-emerald-400 transition-colors">
                        {alert.title}
                      </h3>
                      <p className="text-sm text-slate-400 line-clamp-2">
                        {alert.description}
                      </p>
                    </Card>
                  ))}
                </div>
              </div>

              {/* SECTION 5: GEOGRAPHIC HOTSPOTS */}
              <div>
                <h2 className="text-xl font-display font-semibold text-white flex items-center gap-2 mb-6">
                  <MapPin className="w-5 h-5 text-rose-500" />
                  Emerging Hotspots
                </h2>
                
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-1 gap-4">
                  {geoHotspots.map((spot) => (
                    <Card key={spot.id} className="flex items-center justify-between p-4">
                      <div>
                        <h3 className="text-slate-200 font-medium flex items-center gap-2">
                          {spot.district}
                          {spot.trend === 'up' && <TrendingUp className="w-3 h-3 text-rose-400" />}
                        </h3>
                        <p className="text-xs text-slate-500 mt-1">{spot.primaryIssue}</p>
                      </div>
                      <div className="text-right">
                        <div className={`text-lg font-bold ${spot.riskLevel === 'High' ? 'text-rose-400' : 'text-amber-400'}`}>
                          {spot.score}
                        </div>
                        <div className="text-xs text-slate-500">Risk Score</div>
                      </div>
                    </Card>
                  ))}
                </div>
              </div>

            </div>
          </div>

          {/* SECTION 6: RESOURCE ALLOCATION RECOMMENDATIONS */}
          <div className="mt-12 mb-8">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h2 className="text-2xl font-display font-semibold text-white flex items-center gap-2">
                  <Users className="w-6 h-6 text-emerald-500" />
                  AI Resource Recommendations
                </h2>
                <p className="text-slate-400 text-sm mt-1">Actionable insights to optimize investigation deployment based on predictive risk models.</p>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {resourceRecommendations.map((rec) => {
                const status = actionStates[rec.id];
                return (
                  <Card key={rec.id} className={`transition-all duration-300 ${status === 'approved' ? 'border-emerald-500/50 bg-emerald-900/10' : status === 'rejected' ? 'opacity-50 grayscale' : ''}`}>
                    <div className="flex justify-between items-start mb-4">
                      <div className="flex items-center gap-3">
                        <div className={`p-2 rounded-lg ${rec.impact === 'High' ? 'bg-rose-500/20 text-rose-400' : 'bg-amber-500/20 text-amber-400'}`}>
                          <Crosshair className="w-5 h-5" />
                        </div>
                        <div>
                          <h3 className="text-slate-200 font-medium">{rec.action}</h3>
                          <p className="text-sm text-slate-400">{rec.target}</p>
                        </div>
                      </div>
                      <Badge variant={rec.impact === 'High' ? 'danger' : 'warning'}>{rec.impact} Impact</Badge>
                    </div>
                    
                    <div className="bg-slate-950/50 rounded-lg p-3 mb-4 border border-slate-800/50">
                      <p className="text-sm text-slate-300 flex items-start gap-2">
                        <BrainCircuit className="w-4 h-4 text-emerald-500 mt-0.5 shrink-0" />
                        {rec.reason}
                      </p>
                    </div>

                    <div className="flex items-center justify-end gap-3 pt-2 border-t border-slate-800">
                      {status === 'pending' ? (
                        <>
                          <Button variant="ghost" size="sm" onClick={() => handleAction(rec.id, 'rejected')}>
                            Dismiss
                          </Button>
                          <Button variant="primary" size="sm" onClick={() => handleAction(rec.id, 'approved')} icon={CheckCircle2}>
                            Approve Action
                          </Button>
                        </>
                      ) : (
                        <span className={`text-sm font-medium flex items-center gap-1 ${status === 'approved' ? 'text-emerald-400' : 'text-slate-500'}`}>
                          {status === 'approved' ? <CheckCircle2 className="w-4 h-4" /> : null}
                          {status.charAt(0).toUpperCase() + status.slice(1)}
                        </span>
                      )}
                    </div>
                  </Card>
                );
              })}
            </div>
          </div>

        </div>
      </div>
    </AppShell>
  );
}
