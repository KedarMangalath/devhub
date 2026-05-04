import React, { useState, useMemo } from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { Map, ArrowDownWideNarrow, ArrowUpNarrowWide, AlertTriangle, Activity } from 'lucide-react';

// Fallback realistic data for Kerala districts if none provided via props
const defaultDistrictData = [
  { district: 'Thiruvananthapuram', count: 842, risk: 'High', trend: '+12%' },
  { district: 'Ernakulam', count: 756, risk: 'High', trend: '+8%' },
  { district: 'Kozhikode', count: 512, risk: 'Medium', trend: '-2%' },
  { district: 'Thrissur', count: 489, risk: 'Medium', trend: '+5%' },
  { district: 'Malappuram', count: 420, risk: 'Medium', trend: '+1%' },
  { district: 'Palakkad', count: 380, risk: 'Medium', trend: '-4%' },
  { district: 'Kollam', count: 310, risk: 'Low', trend: '-7%' },
  { district: 'Kannur', count: 290, risk: 'Low', trend: '0%' },
  { district: 'Alappuzha', count: 245, risk: 'Low', trend: '-1%' },
  { district: 'Kottayam', count: 210, risk: 'Low', trend: '-3%' },
  { district: 'Kasaragod', count: 180, risk: 'Low', trend: '+2%' },
  { district: 'Pathanamthitta', count: 150, risk: 'Low', trend: '-5%' },
  { district: 'Idukki', count: 120, risk: 'Low', trend: '-8%' },
  { district: 'Wayanad', count: 95, risk: 'Low', trend: '-10%' }
];

const getBarColor = (count) => {
  if (count >= 600) return '#DC2626'; // Red-600 for High Density
  if (count >= 300) return '#D97706'; // Amber-600 for Medium Density
  return '#059669'; // Emerald-600 for Low Density
};

const CustomTooltip = ({ active, payload }) => {
  if (active && payload && payload.length) {
    const data = payload[0].payload;
    const isHighRisk = data.risk === 'High';
    
    return (
      <div className="bg-card border border-border p-4 rounded-xl shadow-xl min-w-[200px]">
        <div className="flex items-center justify-between mb-2">
          <p className="font-display font-semibold text-foreground text-lg">{data.district}</p>
          {isHighRisk && <AlertTriangle className="w-4 h-4 text-red-500" />}
        </div>
        
        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">Active Reports</span>
            <span className="font-medium text-foreground">{data.count}</span>
          </div>
          
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">Risk Level</span>
            <span className={`font-medium ${
              data.risk === 'High' ? 'text-red-500' : 
              data.risk === 'Medium' ? 'text-amber-500' : 'text-emerald-500'
            }`}>
              {data.risk}
            </span>
          </div>

          <div className="flex items-center justify-between text-sm pt-2 border-t border-border">
            <span className="text-muted-foreground">30-Day Trend</span>
            <span className={`font-medium flex items-center gap-1 ${
              data.trend.startsWith('+') ? 'text-red-500' : 'text-emerald-500'
            }`}>
              <Activity className="w-3 h-3" />
              {data.trend}
            </span>
          </div>
        </div>
      </div>
    );
  }
  return null;
};

export default function StateHeatmapWidget({ data = defaultDistrictData }) {
  const [sortOrder, setSortOrder] = useState('desc');

  const chartData = useMemo(() => {
    const sourceData = data && data.length > 0 ? data : defaultDistrictData;
    return [...sourceData].sort((a, b) => {
      if (sortOrder === 'desc') return b.count - a.count;
      return a.count - b.count;
    });
  }, [data, sortOrder]);

  const toggleSort = () => {
    setSortOrder(prev => prev === 'desc' ? 'asc' : 'desc');
  };

  const totalComplaints = chartData.reduce((sum, item) => sum + item.count, 0);

  return (
    <div className="bg-card border border-border rounded-xl shadow-sm overflow-hidden flex flex-col h-full">
      {/* Widget Header */}
      <div className="p-5 border-b border-border flex items-center justify-between bg-secondary/30">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-primary/10 rounded-lg text-primary">
            <Map className="w-5 h-5" />
          </div>
          <div>
            <h3 className="font-display font-semibold text-foreground text-lg">District Density</h3>
            <p className="text-sm text-muted-foreground font-body">
              {totalComplaints.toLocaleString()} total active cases
            </p>
          </div>
        </div>
        <button
          onClick={toggleSort}
          className="p-2 hover:bg-secondary rounded-md transition-colors text-muted-foreground hover:text-foreground flex items-center gap-2 text-sm font-medium"
          title={`Sort ${sortOrder === 'desc' ? 'Ascending' : 'Descending'}`}
        >
          {sortOrder === 'desc' ? (
            <>
              <ArrowDownWideNarrow className="w-4 h-4" />
              <span className="hidden sm:inline">Highest First</span>
            </>
          ) : (
            <>
              <ArrowUpNarrowWide className="w-4 h-4" />
              <span className="hidden sm:inline">Lowest First</span>
            </>
          )}
        </button>
      </div>

      {/* Chart Area */}
      <div className="p-5 flex-grow min-h-[400px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={chartData}
            layout="vertical"
            margin={{ top: 5, right: 30, left: 40, bottom: 5 }}
            barSize={24}
          >
            <XAxis 
              type="number" 
              hide 
            />
            <YAxis 
              dataKey="district" 
              type="category" 
              axisLine={false} 
              tickLine={false}
              tick={{ fill: '#64748B', fontSize: 13, fontFamily: 'Inter' }}
              width={130}
            />
            <Tooltip 
              content={<CustomTooltip />} 
              cursor={{ fill: 'rgba(100, 116, 139, 0.05)' }}
            />
            <Bar 
              dataKey="count" 
              radius={[0, 4, 4, 0]}
              animationDuration={1000}
            >
              {chartData.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={getBarColor(entry.count)} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Legend */}
      <div className="px-5 py-4 border-t border-border bg-secondary/10 flex items-center justify-center gap-6 text-sm font-body">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-[#DC2626]"></div>
          <span className="text-muted-foreground">High (&gt;600)</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-[#D97706]"></div>
          <span className="text-muted-foreground">Medium (300-600)</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-[#059669]"></div>
          <span className="text-muted-foreground">Low (&lt;300)</span>
        </div>
      </div>
    </div>
  );
}