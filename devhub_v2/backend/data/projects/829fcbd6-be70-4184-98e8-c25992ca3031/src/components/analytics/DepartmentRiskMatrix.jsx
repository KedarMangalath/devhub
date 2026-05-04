import React, { useState, useMemo } from 'react';
import { ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ZAxis } from 'recharts';
import { AlertTriangle, Info, Filter, ShieldAlert, ShieldCheck, Shield } from 'lucide-react';

const defaultDepartments = [
  { id: 'd1', name: 'Public Works (PWD)', volume: 450, resolutionTime: 45, riskScore: 85, riskLevel: 'High' },
  { id: 'd2', name: 'Revenue Department', volume: 820, resolutionTime: 28, riskScore: 65, riskLevel: 'Medium' },
  { id: 'd3', name: 'Local Self Govt', volume: 610, resolutionTime: 35, riskScore: 72, riskLevel: 'High' },
  { id: 'd4', name: 'Motor Vehicles', volume: 340, resolutionTime: 15, riskScore: 30, riskLevel: 'Low' },
  { id: 'd5', name: 'Health Services', volume: 290, resolutionTime: 22, riskScore: 45, riskLevel: 'Medium' },
  { id: 'd6', name: 'Kerala Police', volume: 510, resolutionTime: 18, riskScore: 40, riskLevel: 'Low' },
  { id: 'd7', name: 'Civil Supplies', volume: 180, resolutionTime: 40, riskScore: 60, riskLevel: 'Medium' },
  { id: 'd8', name: 'Education Dept', volume: 220, resolutionTime: 12, riskScore: 25, riskLevel: 'Low' },
  { id: 'd9', name: 'Forest Department', volume: 95, resolutionTime: 55, riskScore: 80, riskLevel: 'High' },
  { id: 'd10', name: 'Excise Department', volume: 150, resolutionTime: 25, riskScore: 50, riskLevel: 'Medium' },
  { id: 'd11', name: 'Registration Dept', volume: 420, resolutionTime: 38, riskScore: 78, riskLevel: 'High' },
  { id: 'd12', name: 'Water Authority', volume: 310, resolutionTime: 42, riskScore: 68, riskLevel: 'Medium' }
];

const CustomTooltip = ({ active, payload }) => {
  if (active && payload && payload.length) {
    const data = payload[0].payload;
    
    const getRiskColor = (level) => {
      switch(level) {
        case 'High': return 'text-red-500 bg-red-500/10 border-red-500/20';
        case 'Medium': return 'text-amber-500 bg-amber-500/10 border-amber-500/20';
        case 'Low': return 'text-emerald-500 bg-emerald-500/10 border-emerald-500/20';
        default: return 'text-muted-foreground bg-secondary border-border';
      }
    };

    return (
      <div className="bg-card border border-border p-4 rounded-xl shadow-xl min-w-[240px]">
        <div className="flex justify-between items-start mb-3">
          <h4 className="font-display font-semibold text-foreground text-lg leading-tight pr-4">{data.name}</h4>
          <span className={`text-xs font-medium px-2 py-1 rounded-full border ${getRiskColor(data.riskLevel)}`}>
            {data.riskLevel} Risk
          </span>
        </div>
        
        <div className="space-y-2 text-sm">
          <div className="flex justify-between items-center py-1 border-b border-border/50">
            <span className="text-muted-foreground">Complaint Volume</span>
            <span className="font-semibold text-foreground">{data.volume}</span>
          </div>
          <div className="flex justify-between items-center py-1 border-b border-border/50">
            <span className="text-muted-foreground">Avg Resolution</span>
            <span className="font-semibold text-foreground">{data.resolutionTime} days</span>
          </div>
          <div className="flex justify-between items-center py-1">
            <span className="text-muted-foreground">AI Risk Score</span>
            <span className="font-semibold text-foreground">{data.riskScore}/100</span>
          </div>
        </div>
      </div>
    );
  }
  return null;
};

export default function DepartmentRiskMatrix({ departments = defaultDepartments }) {
  const [activeFilter, setActiveFilter] = useState('All');

  const filters = [
    { id: 'All', label: 'All Departments', icon: Filter },
    { id: 'High', label: 'High Risk', icon: ShieldAlert },
    { id: 'Medium', label: 'Medium Risk', icon: Shield },
    { id: 'Low', label: 'Low Risk', icon: ShieldCheck }
  ];

  const filteredData = useMemo(() => {
    if (activeFilter === 'All') return departments;
    return departments.filter(d => d.riskLevel === activeFilter);
  }, [departments, activeFilter]);

  const highRiskData = filteredData.filter(d => d.riskLevel === 'High');
  const mediumRiskData = filteredData.filter(d => d.riskLevel === 'Medium');
  const lowRiskData = filteredData.filter(d => d.riskLevel === 'Low');

  return (
    <div className="bg-card border border-border rounded-2xl shadow-sm p-6 w-full flex flex-col h-full">
      <div className="flex flex-col lg:flex-row justify-between items-start lg:items-center mb-8 gap-6">
        <div>
          <h3 className="font-display text-xl font-bold text-foreground flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-primary" />
            Department Risk Matrix
          </h3>
          <p className="text-muted-foreground text-sm mt-1 max-w-md">
            AI-driven analysis mapping complaint volume against resolution delays to identify systemic bottlenecks.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2 bg-secondary/50 p-1 rounded-lg border border-border/50">
          {filters.map((filter) => {
            const Icon = filter.icon;
            const isActive = activeFilter === filter.id;
            return (
              <button
                key={filter.id}
                onClick={() => setActiveFilter(filter.id)}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-all duration-200 ${
                  isActive 
                    ? 'bg-background text-foreground shadow-sm border border-border' 
                    : 'text-muted-foreground hover:text-foreground hover:bg-background/50 border border-transparent'
                }`}
              >
                <Icon className={`w-4 h-4 ${
                  isActive && filter.id === 'High' ? 'text-red-500' :
                  isActive && filter.id === 'Medium' ? 'text-amber-500' :
                  isActive && filter.id === 'Low' ? 'text-emerald-500' : ''
                }`} />
                {filter.label}
              </button>
            );
          })}
        </div>
      </div>

      <div className="flex-grow min-h-[400px] w-full relative">
        {/* Quadrant Backgrounds for visual context */}
        <div className="absolute inset-0 pointer-events-none grid grid-cols-2 grid-rows-2 opacity-[0.02] z-0">
          <div className="bg-emerald-500 border-r border-b border-foreground/10"></div>
          <div className="bg-amber-500 border-b border-foreground/10"></div>
          <div className="bg-blue-500 border-r border-foreground/10"></div>
          <div className="bg-red-500"></div>
        </div>

        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="currentColor" className="text-border/50" vertical={false} />
            
            <XAxis 
              type="number" 
              dataKey="volume" 
              name="Complaint Volume" 
              stroke="currentColor" 
              className="text-muted-foreground text-xs"
              tick={{ fill: 'currentColor', opacity: 0.7 }}
              tickLine={false}
              axisLine={{ strokeOpacity: 0.2 }}
              label={{ value: 'Total Complaint Volume', position: 'insideBottom', offset: -15, fill: 'currentColor', opacity: 0.7, fontSize: 12 }}
            />
            
            <YAxis 
              type="number" 
              dataKey="resolutionTime" 
              name="Resolution Time" 
              stroke="currentColor" 
              className="text-muted-foreground text-xs"
              tick={{ fill: 'currentColor', opacity: 0.7 }}
              tickLine={false}
              axisLine={{ strokeOpacity: 0.2 }}
              label={{ value: 'Avg Resolution Time (Days)', angle: -90, position: 'insideLeft', offset: -5, fill: 'currentColor', opacity: 0.7, fontSize: 12 }}
            />
            
            <ZAxis 
              type="number" 
              dataKey="riskScore" 
              range={[100, 800]} 
              name="Risk Score" 
            />
            
            <Tooltip 
              content={<CustomTooltip />} 
              cursor={{ strokeDasharray: '3 3', stroke: 'currentColor', strokeOpacity: 0.2 }} 
            />
            
            {/* Render separate scatters to control colors without needing Cell import */}
            <Scatter 
              name="High Risk" 
              data={highRiskData} 
              fill="#ef4444" 
              fillOpacity={0.7}
              stroke="#b91c1c"
              strokeWidth={2}
            />
            <Scatter 
              name="Medium Risk" 
              data={mediumRiskData} 
              fill="#f59e0b" 
              fillOpacity={0.7}
              stroke="#b45309"
              strokeWidth={2}
            />
            <Scatter 
              name="Low Risk" 
              data={lowRiskData} 
              fill="#10b981" 
              fillOpacity={0.7}
              stroke="#047857"
              strokeWidth={2}
            />
          </ScatterChart>
        </ResponsiveContainer>
      </div>

      <div className="mt-6 flex items-start gap-3 bg-primary/5 p-4 rounded-xl border border-primary/10">
        <Info className="w-5 h-5 text-primary shrink-0 mt-0.5" />
        <p className="text-sm text-muted-foreground leading-relaxed">
          <strong className="text-foreground font-medium">How to read this matrix:</strong> Departments in the top-right quadrant (High Volume, High Resolution Time) represent the highest systemic risk and require immediate administrative intervention. Bubble size indicates the AI-calculated overall risk score based on historical anomalies.
        </p>
      </div>
    </div>
  );
}